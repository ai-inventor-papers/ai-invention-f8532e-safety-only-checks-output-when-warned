"""The harvest sweep: ONE long-lived process over the panel, resumable, deadline-aware.

Priority order (Section 12) so an overrun truncates the tail, not the core:
  1  the commissioned Qwen3-4B arm (instruct, abliterated, Base, SafeRL, CohenQu)
  2  the small effective pairs + granite (the NULL-EDIT specificity control) + random-init
  3  SmolLM3 and Phi-4-mini
  4  the leaked-seal ANOMALOUS controls, base arms, TinyLlama

NEVER lets one checkpoint kill the sweep: every failure is captured with its traceback.
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import (  # noqa: E402
    ASSETS, DEVIATIONS, HARVEST, RESULTS, WS, Deadline, jdump, jload, jload_maybe,
    set_all_seeds, setup_logging, slug,
)
from harvest import harvest_one  # noqa: E402
from loguru import logger  # noqa: E402
from panel import PAIRS, RANDOM_INIT, SINGLES  # noqa: E402


def build_queue(max_priority: int = 4) -> list[dict]:
    """(repo, tag, priority, template_mode, random_init, do_c_harvest)."""
    q: list[dict] = []
    seen: set[str] = set()

    def add(repo, tag, prio, *, mode="chat", rand=False, c=True, role="", family=""):
        key = tag or slug(repo)
        if key in seen:
            return
        seen.add(key)
        q.append(dict(repo=repo, tag=key, priority=prio, template_mode=mode,
                      random_init=rand, do_c_harvest=c, role=role, family=family))

    for p in PAIRS:
        if p["priority"] > max_priority:
            continue
        # HARDWARE CUT (registered deviation, fallback #5): the C-harvest is DROPPED for
        # every checkpoint. This box has no GPU, 2 visible cores and an external load
        # average of ~39 on 24 cores, and the 96-cell teacher-forced harvest measured
        # ~1.8x the cost of the whole prompt harvest per checkpoint. X5 and X11 are
        # therefore NOT COMPUTED and are reported as such; X1/X2/X3/X8/X10 survive on the
        # prompt harvest plus the weight summary alone, which is exactly the registered
        # fallback order (X5 is the first candidate to drop because it is the only one
        # needing per-position tensors).
        c = False
        add(p["parent"], None, p["priority"], c=c, role="parent", family=p["family"])
        add(p["child"], None, p["priority"], c=c, role="child", family=p["family"])
    for s in SINGLES:
        if s["priority"] > max_priority:
            continue
        modes = s.get("template_modes", ("chat",))
        for m in modes:
            tag = slug(s["repo"]) + ("" if m == "chat" else f"--{m}")
            add(s["repo"], tag, s["priority"], mode=m, c=False,
                role=s.get("role", ""), family=s["family"])
    for r in RANDOM_INIT:
        if r["priority"] > max_priority:
            continue
        add(r["repo"], r["tag"], r["priority"], rand=True, c=False,
            role="random_init", family="randinit")
    # EXPLICIT ORDER (Section 12, re-cut for a CPU-only box under heavy external load):
    # the four COMMISSIONED Qwen3-4B checkpoints first -- they are the deliverable the run
    # was asked for -- then the small effective pairs and the granite NULL-EDIT control
    # that E1 needs, then the E2 non-safety-fine-tune control, then the tail.
    # ORDER v2, revised at 04:22 after the WEIGHT FINGERPRINTS landed.
    #
    # The fingerprint is a weights-only DIAGNOSTIC that is excluded from every metric, but it
    # determines which pairs share a STRATUM, and E1(a) requires >= 4 EFFECTIVE pairs WITHIN
    # ONE stratum. Measured strata: P1, P2, P4 = A_GLOBAL_RANK1; P0 = B_PER_LAYER_RANK1
    # (alone); P3 = C_OTHER_OPERATOR (alpha 3.53, rank-1 share 0.078 -- not a rank-one
    # abliteration at all); P6 granite = C (1 of 80 matrices edited). So stratum A has three
    # effective members in hand and the Phi pair P5 is the one that can take it to the
    # registered minimum of four, while P3 is a stratum-C singleton that can only ever feed
    # the labelled pooled-across-strata secondary row.
    #
    # This reorders WHICH CHECKPOINTS GET HARVESTED FIRST under a wall clock. It changes no
    # threshold, no definition and no outcome, and it is recorded in deviations.
    ORDER = [
        # the four COMMISSIONED Qwen3-4B checkpoints -- the deliverable that was asked for
        "Qwen--Qwen3-4B",
        "mlabonne--Qwen3-4B-abliterated",
        "Qwen--Qwen3-4B-Base",
        "Qwen--Qwen3-4B-SafeRL",
        # stratum-A effective pairs, cheapest first, + the random-init arm
        "Qwen--Qwen3-0.6B",
        "huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2",
        "RandInit-Qwen3-0.6B",
        "Qwen--Qwen3-1.7B",
        "huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2",
        # the NULL-EDIT specificity control -- E1(b) needs it, NEVER drop
        "ibm-granite--granite-3.2-2b-instruct",
        "Damien420--granite-3.2-2b-instruct-abliterated",
        # the remaining stratum-A pairs: these are what can take E1(a) to 4 within one stratum
        "HuggingFaceTB--SmolLM3-3B",
        "mlx-community--SmolLM3-3B-abliterated-bf16",
        "microsoft--Phi-4-mini-instruct",
        "lunahr--Phi-4-mini-instruct-abliterated",
        # stratum-C singleton: feeds only the pooled secondary row
        "Qwen--Qwen2.5-1.5B-Instruct",
        "Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3",
        # E2's non-safety fine-tune control
        "CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6",
        # the leaked-seal ANOMALOUS controls and the rest of the E3 family panel
        "stabilityai--stablelm-2-1_6b-chat",
        "hereticness--heretic_stablelm-2-1_6b-chat",
        "HuggingFaceTB--SmolLM2-1.7B-Instruct",
        "venkycs--SmolLM2-1.7B-Instruct-Abliterated",
        "TinyLlama--TinyLlama-1.1B-Chat-v1.0",
        "allenai--OLMo-2-0425-1B-Instruct",
        "allenai--OLMo-2-0425-1B",
        "Qwen--Qwen3-4B-Base--plain",
    ]
    rank = {t: i for i, t in enumerate(ORDER)}
    q.sort(key=lambda x: (rank.get(x["tag"], 999), x["priority"], x["tag"]))
    return q


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="restrict to these tags")
    ap.add_argument("--max-priority", type=int, default=4)
    ap.add_argument("--deadline-min", type=float, default=110.0)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    setup_logging("sweep")
    set_all_seeds()
    dl = Deadline(args.deadline_min)

    prereg = jload(WS / "prereg.json")
    cfg = dict(prereg["config"])
    stim = jload(ASSETS / "stimuli.json")
    cells_doc = jload(ASSETS / "cells.json")
    tsets = jload(ASSETS / "token_sets.json")

    cfg["token_sets"] = {k: v for k, v in tsets.items() if k != "meta"}
    cfg["x5_cell_index"] = cells_doc["x5_cell_index"]

    stimuli = stim["rows"]
    cells = [
        dict(c, prompt_text=None, full_text=None) for c in cells_doc["cells"]
    ]

    q = build_queue(args.max_priority)
    if args.only:
        q = [e for e in q if e["tag"] in set(args.only)]
    if args.limit:
        q = q[: args.limit]
    logger.info(f"QUEUE ({len(q)}): " + ", ".join(f"{e['tag']}[p{e['priority']}]" for e in q))

    failures = jload_maybe(RESULTS / "harvest_failures.json", []) or []
    timings = jload_maybe(RESULTS / "harvest_timings.json", {}) or {}

    for i, e in enumerate(q):
        if not dl.have(1.0):
            DEVIATIONS.add("gate", "harvest deadline reached",
                           f"stopped before {e['tag']}; {len(q) - i} checkpoints not harvested",
                           remaining=[x["tag"] for x in q[i:]])
            break
        done = HARVEST / e["tag"] / "DONE"
        if done.exists():
            m = jload_maybe(HARVEST / e["tag"] / "meta.json", {})
            timings[e["tag"]] = (m or {}).get("timings", {})
            logger.info(f"[{i+1}/{len(q)}] SKIP {e['tag']} (DONE)")
            continue
        logger.info(f"[{i+1}/{len(q)}] HARVEST {e['tag']} "
                    f"(p{e['priority']}, {dl.remaining_min():.0f} min left)")
        t0 = time.time()
        try:
            local_cells = _render_cells(e["repo"], cells, e["template_mode"]) \
                if e["do_c_harvest"] else None
            meta = harvest_one(
                e["repo"], cfg, stimuli, local_cells,
                template_mode=e["template_mode"], tag=e["tag"],
                random_init=e["random_init"], do_c_harvest=e["do_c_harvest"],
            )
            meta["role"] = e["role"]
            meta["family"] = e["family"]
            meta["priority"] = e["priority"]
            jdump(meta, HARVEST / e["tag"] / "meta.json")
            timings[e["tag"]] = meta.get("timings", {})
        except Exception as exc:  # noqa: BLE001 - one checkpoint must never kill the sweep
            tb = traceback.format_exc()
            failures.append({"tag": e["tag"], "repo": e["repo"], "error": repr(exc),
                             "traceback": tb[-4000:], "elapsed_s": time.time() - t0})
            jdump(failures, RESULTS / "harvest_failures.json")
            DEVIATIONS.add("harvest_failed", e["tag"], repr(exc)[:400])
            logger.error(f"FAILED {e['tag']}: {exc}")
        finally:
            gc.collect()
            jdump(timings, RESULTS / "harvest_timings.json")

    jdump(failures, RESULTS / "harvest_failures.json")
    jdump(timings, RESULTS / "harvest_timings.json")
    done_tags = sorted(p.parent.name for p in HARVEST.glob("*/DONE"))
    logger.info(f"SWEEP END: {len(done_tags)} harvested, {len(failures)} failed, "
                f"{dl.elapsed_min():.1f} min elapsed")
    jdump({"harvested": done_tags, "n_failed": len(failures),
           "elapsed_min": dl.elapsed_min()}, RESULTS / "sweep_status.json")
    return 0


def _render_cells(repo: str, cells: list[dict], mode: str) -> list[dict]:
    """Render prompt/full text with THAT model's own chat template (3.4 / fallback 6).

    Window offsets are recomputed from the CELL TEXT inside c_harvest, never from the
    stored Qwen token spans.
    """
    from transformers import AutoTokenizer

    from harvest import render_prompt

    tok = AutoTokenizer.from_pretrained(repo)
    out = []
    for c in cells:
        p = render_prompt(tok, c["plain_prompt"], mode)
        out.append(dict(c, prompt_text=p, full_text=p + c["continuation"]))
    del tok
    return out


if __name__ == "__main__":
    raise SystemExit(main())
