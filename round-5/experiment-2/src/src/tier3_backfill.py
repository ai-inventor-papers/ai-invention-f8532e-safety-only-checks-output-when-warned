#!/usr/bin/env python3
"""Back-fill the TIER-3 arrays and the AMS baseline onto already-harvested tags.

The sweep ran `harvest --tier2` for wall-clock reasons, which leaves out four things the plan
asks for and which no later step can reconstruct without the model:

  A_c11.npy          64 graded-severity prompts               -> severity monotonicity
  A_ams.npy          the 96 AMS concept cells                 -> the AMS separation instrument
  A_prompt_p1/p2.npy the two EXPRESSION-ONLY render arms       -> template/system-prompt invariance
  A_prompt_p3.npy    the same weights recast to float16        -> a numerics-only perturbation

and, from A_ams, the AMS Tier-1 sigma, which is a BASELINE INSTRUMENT the activation substrate
is meant to sit beside (not a candidate score).

Everything is computed with the pipeline's own functions at batch 1, so the numerics match the
tier-1/2 arrays of the same tag exactly. The ORDER GATE still applies: a tag is touched only if
it already has a DONE harvest, which it could only have obtained through a committed
graded_truth. MANIFEST.sha256.json and meta.json are rewritten; DONE is left in place.

    python tier3_backfill.py [--tags T...] [--deadline-utc ISO] [--max-tags N]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "src"))

from loguru import logger  # noqa: E402

import pipeline as PL  # noqa: E402

NEEDED = ("A_c11.npy", "A_ams.npy", "A_cells96.npy", "A_prompt_p1.npy", "A_prompt_p2.npy",
          "A_prompt_p3.npy")


def missing(tag_dir: Path) -> list[str]:
    """Absent arrays, plus A_ams whenever it was not produced from the AMS prompt set.

    The sweep's tier-3 block built A_ams.npy from assets/cells.json (the 96 XSTest 2x2 cells).
    That is the WRONG row set for the AMS instrument: ams_reimpl.ams_tier1 needs the 96 rows of
    ams_prompts() (3 concepts x 16 pairs x 2 polarities) in that exact order, and passing the
    cells raised KeyError('concept'). Both are kept -- A_ams.npy from ams_prompts(), the cell
    set under its own name A_cells96.npy -- so an A_ams that predates this fix is rewritten."""
    out = [n for n in NEEDED if not (tag_dir / n).exists()]
    meta = PL.jload(tag_dir / "meta.json") if (tag_dir / "meta.json").exists() else {}
    if (tag_dir / "A_ams.npy").exists() and meta.get("ams_row_set") != "ams_prompts":
        out.append("A_ams.npy")
    return sorted(set(out))


def descriptor(tag: str) -> dict | None:
    """The sweep row (panel) or the Part-B arm row, so the lease can be sized."""
    for t, row in PL.sweep_index().items():
        if t == tag:
            return row
    meta = PL.jload(PL.ARRAYS / tag / "meta.json") if (PL.ARRAYS / tag / "meta.json").exists() else {}
    if meta.get("repo"):
        return {"repo": meta["repo"], "revision_sha": meta.get("revision_sha"),
                "trust_remote_code": bool(meta.get("trust_remote_code")),
                "bf16_gb": (meta.get("n_params") or 0) * 2 / 2**30 or None}
    return None


def backfill_one(tag: str) -> dict:
    from lease import vram_lease
    out_dir = PL.ARRAYS / tag
    need = missing(out_dir)
    if not need:
        return {"tag": tag, "skipped": "already complete"}
    if not (out_dir / "DONE").exists():
        return {"tag": tag, "skipped": "no DONE harvest (never passed the order gate)"}
    row = descriptor(tag)
    if not row:
        return {"tag": tag, "skipped": "no descriptor"}
    if str(row.get("repo", "")).startswith("partb-local/"):
        return {"tag": tag, "skipped": "Part-B arm: its weights live in private/ and are deleted"}

    t_all = time.time()
    rec: dict = {"tag": tag, "repo": row["repo"], "missing_before": need}
    lease_mib = PL.lease_mib_for(row.get("bf16_gb"))
    with vram_lease(mib=lease_mib, artifact=f"exp2_tier3_{tag}") as grant:
        PL.set_memory_fraction(lease_mib)
        model, tok, load_info, _errs, t_dl, t_load = PL.acquire_model(
            row["repo"], row.get("revision_sha"), bool(row.get("trust_remote_code")))
        try:
            batch = 1                      # padding-free, one kernel path, as in the harvest
            stimuli = PL.jload(PL.ASSETS / "stimuli.json")["rows"]
            add_special = PL.render_one(tok, "x")[2]
            texts = [PL.render_one(tok, r["text"])[0] for r in stimuli]

            if "A_c11.npy" in need:
                t0 = time.time()
                c11 = PL.jload(PL.ASSETS / "c11_items.json")["items"]
                PL.atomic_npy(out_dir / "A_c11.npy", PL.simple_prompt_harvest(
                    model, tok, [PL.render_one(tok, x["prompt"])[0] for x in c11],
                    batch, add_special))
                rec["t_c11_s"] = round(time.time() - t0, 1)
            if "A_ams.npy" in need:
                # AMS is code-pinned to RAW TEXT with NO chat template and the last position,
                # so the rows are ams_prompts() verbatim and in its order.
                t0 = time.time()
                sys.path.insert(0, str(WS / "src" / "vendor"))
                import ams_reimpl
                aps = ams_reimpl.ams_prompts()
                PL.atomic_npy(out_dir / "A_ams.npy", PL.simple_prompt_harvest(
                    model, tok, [a["text"] for a in aps], batch, True))
                rec["t_ams_s"] = round(time.time() - t0, 1)
                rec["ams_rows"] = len(aps)
            if "A_cells96.npy" in need:
                t0 = time.time()
                cells = PL.jload(PL.ASSETS / "cells.json")["cells"]
                PL.atomic_npy(out_dir / "A_cells96.npy", PL.simple_prompt_harvest(
                    model, tok, [PL.render_one(tok, c["plain_prompt"])[0] for c in cells],
                    batch, add_special))
                rec["t_cells96_s"] = round(time.time() - t0, 1)
            for name, sys_p, plain in (("A_prompt_p1.npy", None, True),
                                       ("A_prompt_p2.npy", "You are a helpful assistant.", False)):
                if name in need:
                    t0 = time.time()
                    tx = ([r["text"] + "\n" for r in stimuli] if plain
                          else [PL.render_one(tok, r["text"], sys_p)[0] for r in stimuli])
                    PL.atomic_npy(out_dir / name, PL.simple_prompt_harvest(
                        model, tok, tx, batch, plain or add_special))
                    rec[f"t_{name[:-4]}_s"] = round(time.time() - t0, 1)
            if "A_prompt_p3.npy" in need:                     # LAST: mutates the loaded weights
                t0 = time.time()
                before = str(next(model.parameters()).dtype)
                model.half()
                PL.atomic_npy(out_dir / "A_prompt_p3.npy", PL.simple_prompt_harvest(
                    model, tok, texts, batch, add_special))
                rec["t_p3_fp16_s"] = round(time.time() - t0, 1)
                rec["p3"] = f"same weights recast {before} -> float16"
            rec["max_memory_allocated_mib"] = PL.peak_mib()
        finally:
            PL.unload(model)
            PL.delete_snapshot(row["repo"])

    # ---- the AMS baseline instrument, computed offline from the array just written
    rec["ams"] = ams_sigma(out_dir)

    meta_p = out_dir / "meta.json"
    meta = PL.jload(meta_p) if meta_p.exists() else {}
    meta.setdefault("tiers", {})["tier3"] = True
    meta["ams_row_set"] = "ams_prompts"
    meta["ams_rendering"] = "raw text, NO chat template, last position (AMS code-pinned)"
    meta["A_cells96_row_set"] = "assets/cells.json cells (the 96 XSTest 2x2 cells)"
    meta["tier3_backfill"] = rec
    meta["ams_sigma_bs1"] = (rec.get("ams") or {}).get("overall_sigma")
    meta["ams_sigma_bs8"] = None
    meta["ams_sigma_bs8_note"] = (
        "NOT COMPUTED. The released AMS CLI captures activations with padding=True at batch 8 and "
        "no padding_side, so pad positions can be read; that is the hazard the research pass "
        "flagged. This artifact captures EVERY forward padding-free (batch 1), so the batch-8 "
        "variant does not exist here and its absence is a property of the capture, not a gap in "
        "the instrument. The batch-1 number is the one the AMS code path defines without the bug.")
    meta["n5_perturbations"] = {"p1": "plain render", "p2": "helpful system prompt",
                                "p3": rec.get("p3", "same weights recast to float16")}
    PL.jdump(meta_p, meta)
    PL.write_manifest(out_dir)
    rec["t_total_s"] = round(time.time() - t_all, 1)
    logger.info(f"TIER3 BACKFILL {tag}: {len(need)} array(s) in {rec['t_total_s']:.0f}s, "
                f"ams_sigma_bs1={meta['ams_sigma_bs1']}")
    return rec


def ams_sigma(out_dir: Path) -> dict:
    """AMS Tier-1 sigma from the harvested A_ams.npy. A BASELINE INSTRUMENT, not a candidate."""
    import numpy as np
    try:
        sys.path.insert(0, str(WS / "src" / "vendor"))
        import ams_reimpl
        A = np.load(out_dir / "A_ams.npy")
        L = int(PL.jload(out_dir / "meta.json").get("n_layers"))
        res = ams_reimpl.ams_tier1(A, ams_reimpl.ams_prompts(), L)
        keep = {k: v for k, v in res.items() if isinstance(v, (int, float, str, bool))}
        per = {k: (v.get("sigma") if isinstance(v, dict) else v)
               for k, v in (res.get("per_concept", {}) or {}).items()}
        keep["per_concept"] = per
        # ams_tier1 returns mean_sigma (a reimpl convenience) and overall_level (worst-of
        # CRITICAL > WARNING > PASS across concepts, replicating SafetyReport.overall_level).
        # The instrument column is the MINIMUM concept sigma, which is what drives that level.
        vals = [v for v in per.values() if isinstance(v, (int, float))]
        keep["min_concept_sigma"] = min(vals) if vals else None
        keep["overall_sigma"] = keep["min_concept_sigma"]
        keep["mean_sigma"] = res.get("mean_sigma")
        keep["overall_level"] = res.get("overall_level")
        return keep
    except Exception as exc:                       # noqa: BLE001 -- instrument, never fatal
        logger.warning(f"ams_tier1 failed for {out_dir.name}: {exc!r}")
        return {"error": repr(exc)[:300]}


@logger.catch(reraise=True)
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="*", default=None)
    ap.add_argument("--max-tags", type=int, default=99)
    ap.add_argument("--deadline-utc", default=None)
    ns = ap.parse_args()
    PL.setup_logging("tier3_backfill")
    PL.gpu_setup()
    tags = ns.tags or sorted(d.name for d in PL.ARRAYS.iterdir()
                             if d.is_dir() and (d / "DONE").exists() and missing(d))
    out = []
    for tag in tags[:ns.max_tags]:
        if ns.deadline_utc and PL.utc_now() >= ns.deadline_utc:
            logger.warning("deadline reached; stopping back-fill")
            break
        try:
            out.append(backfill_one(tag))
        except Exception as exc:                   # noqa: BLE001
            logger.exception(f"backfill failed for {tag}")
            PL.deviation("tier3_backfill_failed", f"{tag}: {exc!r}"[:400], "harvest")
            out.append({"tag": tag, "error": repr(exc)[:300]})
        PL.empty_cache()
    PL.jdump(PL.RESULTS / "tier3_backfill.json",
             {"utc": PL.utc_now(), "n": len(out), "rows": out})
    done = sum(1 for r in out if r.get("t_total_s"))
    print(f"tier3 back-fill: {done}/{len(out)} tag(s) completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
