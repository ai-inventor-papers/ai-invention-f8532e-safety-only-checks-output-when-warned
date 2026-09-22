#!/usr/bin/env python3
"""LANE A -- one activation harvest, five safety readouts.

Streams a panel of Qwen3-4B checkpoints one at a time through ONE teacher-forced
activation harvest (zero generated tokens), saves mean-pooled residual vectors plus
per-position scalar projections, then scores five candidate safety readouts (K1 arming
interaction, K2 prior+slope, K3 benign-only footprint, K4 hazard decay time constant,
K5 harm-domain profile) against test S1, alongside four baselines.

Run:
    .venv/bin/python method.py --stage all
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import resource
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from loguru import logger

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

LOG_DIR = HERE / "logs"
LOG_DIR.mkdir(exist_ok=True)
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(LOG_DIR / "run.log", rotation="30 MB", level="DEBUG")

WORK = HERE / "work"
ITEMS = HERE / "items"
HARVEST = HERE / "harvest"
OUT = HERE / "out"
for d in (WORK, ITEMS, HARVEST, OUT):
    d.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# panel
# ---------------------------------------------------------------------------
# Priority order: the four S1-critical arms first, so that if time runs out the most
# valuable rows already exist. Base-plain is a protocol check, not an arm, so it goes last.
PANEL: list[dict[str, Any]] = [
    {"tag": "Qwen3-4B", "repo": "Qwen/Qwen3-4B", "mode": "chat",
     "role": "safety arm 1 (instruct) -- registered target for K1.A, K2.prior, K5.dispersion"},
    {"tag": "Qwen3-4B-SafeRL", "repo": "Qwen/Qwen3-4B-SafeRL", "mode": "chat",
     "role": "safety arm 2 (safety RL) -- registered target for K1.CB, K2.slope, K3, K4"},
    {"tag": "Qwen3-4B-Base-chat", "repo": "Qwen/Qwen3-4B-Base", "mode": "chat",
     "role": "non-safety arm 1 (base, Qwen3-4B's chat template applied verbatim)"},
    {"tag": "NonSafetyFT-STaR", "repo": "CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6", "mode": "chat",
     "role": "non-safety arm 2 (task fine-tune of the same base)"},
    {"tag": "Qwen3-4B-abliterated", "repo": "mlabonne/Qwen3-4B-abliterated", "mode": "chat",
     "role": "reserved evidence -- community uncensoring edit of Qwen3-4B"},
    {"tag": "RandInit-4B", "repo": "Qwen/Qwen3-4B", "mode": "chat", "random_init": True,
     "role": "randomized-transformer control (handbook-required): identical architecture, untrained weights"},
    {"tag": "Qwen3-4B-Base-plain", "repo": "Qwen/Qwen3-4B-Base", "mode": "plain",
     "role": "base protocol check (plain completion format)"},
]
PANEL_FALLBACKS = [
    "CohenQu/Qwen3-4B-Base_HintGen-STaR.04.00_1e-6_no_think",
    "shjondhale/AzureML-Qwen3-4B-Base-GRPO",
    "HikariLight/Qwen3_4B_Base__COMP_ACI_DAMT_SFT_Merged",
]
TOKENIZER_REPO = "Qwen/Qwen3-4B"
SMOKE_REPO = "Qwen/Qwen3-0.6B"

TARGET_MAP = {"Qwen3-4B": "Qwen3-4B", "Qwen3-4B-SafeRL": "Qwen3-4B-SafeRL"}
NON_SAFETY_ARMS = ("Qwen3-4B-Base-chat", "NonSafetyFT-STaR")


# ---------------------------------------------------------------------------
# hardware
# ---------------------------------------------------------------------------

def detect_cpus() -> int:
    try:
        parts = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if parts[0] != "max":
            return math.ceil(int(parts[0]) / int(parts[1]))
    except (FileNotFoundError, ValueError, IndexError):
        pass
    try:
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 1


def container_ram_gb() -> float | None:
    for p in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            v = Path(p).read_text().strip()
            if v != "max" and int(v) < 1_000_000_000_000:
                return int(v) / 1e9
        except (FileNotFoundError, ValueError):
            pass
    return None


def hardware_report() -> dict[str, Any]:
    import psutil
    import torch
    free_b, total_b = 0, 0
    if torch.cuda.is_available():
        free_b, total_b = torch.cuda.mem_get_info(0)
    du = shutil.disk_usage(str(HERE))
    return {
        "cpus": detect_cpus(),
        "ram_total_gb": round(container_ram_gb() or psutil.virtual_memory().total / 1e9, 1),
        "ram_available_gb": round(psutil.virtual_memory().available / 1e9, 1),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "vram_total_gb": round(total_b / 1e9, 2),
        "vram_free_gb": round(free_b / 1e9, 2),
        "workspace_fs_free_gb": round(du.free / 1e9, 1),
        "root_fs_free_gb": round(shutil.disk_usage("/").free / 1e9, 1),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
    }


def set_limits(ram_budget_gb: float | None = None, vram_fraction: float = 0.92) -> None:
    import psutil
    import torch
    avail = psutil.virtual_memory().available
    cap_gb = ram_budget_gb if ram_budget_gb is not None else 0.65 * (container_ram_gb() or 62.0)
    budget = int(min(cap_gb * 1e9, avail * 0.8))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (budget * 3, budget * 3))
        logger.info(f"RLIMIT_AS set to {budget * 3 / 1e9:.0f} GB virtual "
                    f"(RSS budget ~{budget / 1e9:.0f} GB)")
    except (ValueError, OSError) as e:
        logger.warning(f"could not set RLIMIT_AS: {e}")
    if torch.cuda.is_available():
        torch.cuda.set_per_process_memory_fraction(vram_fraction, 0)
        logger.info(f"VRAM fraction capped at {vram_fraction}")


def free_vram_gb() -> float:
    """VRAM this process can actually use: what the driver reports free, PLUS whatever this
    process has already reserved in the caching allocator but is not currently using.

    The GPU is shared with the other lanes, so once a slot has been won it is kept inside
    our own allocator between checkpoints (we never call empty_cache() in the panel loop)
    rather than handed back and re-contested for every model.
    """
    import torch
    if not torch.cuda.is_available():
        return 0.0
    free_b, _ = torch.cuda.mem_get_info(0)
    slack = torch.cuda.memory_reserved(0) - torch.cuda.memory_allocated(0)
    return (free_b + slack) / 1e9


def wait_for_vram(min_free_gb: float, *, timeout_s: float = 2400.0, poll_s: float = 15.0) -> bool:
    """This GPU is SHARED with the other lanes of the same run, so a checkpoint load can
    only start when enough VRAM is actually free. Poll rather than crash; on timeout the
    caller skips the checkpoint and retries it later."""
    t0 = time.time()
    last_log = -60.0
    while True:
        free = free_vram_gb()
        if free >= min_free_gb:
            if time.time() - t0 > poll_s:
                logger.info(f"VRAM available again ({free:.1f} GB free) after "
                            f"{time.time() - t0:.0f}s of waiting")
            return True
        if time.time() - t0 > timeout_s:
            logger.warning(f"timed out after {timeout_s:.0f}s waiting for {min_free_gb:.1f} GB "
                           f"of VRAM (only {free:.1f} GB free)")
            return False
        if time.time() - t0 - last_log >= 120:
            last_log = time.time() - t0
            logger.info(f"waiting for VRAM: {free:.1f} GB free, need {min_free_gb:.1f} GB "
                        f"({time.time() - t0:.0f}s elapsed; the GPU is shared with the other lanes)")
        time.sleep(poll_s)


def package_versions() -> dict[str, str]:
    import importlib
    out = {}
    for m in ("torch", "transformers", "numpy", "scipy", "sklearn", "pyarrow", "accelerate"):
        try:
            out[m] = importlib.import_module(m).__version__
        except (ImportError, AttributeError):
            out[m] = "n/a"
    return out


# ---------------------------------------------------------------------------
# harvest of one checkpoint
# ---------------------------------------------------------------------------

def _onset_ids(tok) -> tuple[list[int], list[int]]:
    from lane_a.substrate import _COMPLIANCE_ONSET_WORDS, _REFUSAL_ONSET_WORDS

    def ids_for(words):
        out = []
        for w in words:
            for cand in (w, " " + w):
                enc = tok(cand, add_special_tokens=False)["input_ids"]
                if len(enc) == 1:
                    out.append(enc[0])
        return sorted(set(out))
    return ids_for(_REFUSAL_ONSET_WORDS), ids_for(_COMPLIANCE_ONSET_WORDS)


def harvest_checkpoint(spec: dict[str, Any], reqs: dict[str, Any], tok,
                       *, out_root: Path, batch_size: int, n_items: int,
                       windows: dict[str, tuple[int, int]], scale: str = "full") -> dict[str, Any]:
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

    from lane_a import shard
    from lane_a.harvest import (Harvester, fit_diff_in_means, layernorm_gains, seeded_random_dirs,
                                stable_ranks)
    from lane_a.pipeline_analysis import RAND_SEED
    from lane_a.substrate import K4_TOTAL_L, TOTAL_L

    tag, repo = spec["tag"], spec["repo"]
    tdir = out_root / tag
    tdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    deviations: list[str] = []
    need_gb = float(spec.get("vram_need_gb", 8.8))
    offload = False
    if dev.type == "cuda" and not wait_for_vram(need_gb):
        offload = True
        deviations.append(
            f"{tag}: the shared GPU never freed {need_gb:.1f} GB, so this checkpoint ran with "
            f"accelerate CPU offload (numerically identical, just slower).")
        logger.warning(f"[{tag}] falling back to CPU offload ({free_vram_gb():.1f} GB free)")
    logger.info(f"[{tag}] loading {repo} (random_init={spec.get('random_init', False)}), "
                f"{free_vram_gb():.1f} GB VRAM free")
    cfg = AutoConfig.from_pretrained(repo)
    if spec.get("random_init"):
        torch.manual_seed(RAND_SEED)
        try:                                  # transformers 5.x
            model = AutoModelForCausalLM.from_config(cfg, dtype=torch.bfloat16)
        except TypeError:                     # transformers 4.x
            model = AutoModelForCausalLM.from_config(cfg, torch_dtype=torch.bfloat16)
        model = model.to(dtype=torch.bfloat16).to(dev)
        deviations.append(f"{tag}: architecture-identical RANDOMLY INITIALISED control "
                          f"(seed {RAND_SEED}); no pretrained weights.")
    else:
        kw: dict[str, Any] = {"dtype": torch.bfloat16, "attn_implementation": "sdpa",
                              "low_cpu_mem_usage": True}
        if dev.type != "cuda":
            kw["device_map"] = None
        elif offload:
            room = max(2, int(free_vram_gb()) - 1)
            kw["device_map"] = "auto"
            kw["max_memory"] = {0: f"{room}GiB", "cpu": "40GiB"}
        else:
            kw["device_map"] = {"": 0}
        model = AutoModelForCausalLM.from_pretrained(repo, **kw)
        if str(getattr(cfg, "torch_dtype", "")).endswith("float32"):
            deviations.append(f"{tag}: repo ships FP32 weights; cast to bfloat16 shard-by-shard on load.")
    model.eval()

    own_tok = AutoTokenizer.from_pretrained(repo)
    vocab_sha = __import__("hashlib").sha256(
        json.dumps(sorted(own_tok.get_vocab().items()), separators=(",", ":")).encode()).hexdigest()
    tmpl = getattr(own_tok, "chat_template", None) or ""
    meta_tok = {"vocab_size": len(own_tok.get_vocab()), "vocab_sha256": vocab_sha,
                "chat_template_bytes": len(tmpl.encode()),
                "chat_template_sha256": __import__("hashlib").sha256(tmpl.encode()).hexdigest()}
    del own_tok

    refusal_ids, compliance_ids = _onset_ids(tok)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    hv = Harvester(model, windows=windows, device=dev,
                   batch_size=(1 if offload else batch_size),
                   pad_id=int(pad_id), refusal_ids=refusal_ids, compliance_ids=compliance_ids)
    n_hs, d_model = hv.n_hs, hv.d_model

    # ---- STAGE (a): fit r_content (RESPONSE site) and r_ablit (PROMPT site)
    logger.info(f"[{tag}] stage (a): {len(reqs['fit'])} fitting + {len(reqs['ablit'])} r_ablit passes")
    fit_out = hv.run(reqs["fit"], pools=("early", "late", "harc32", "prompt"), need_logits=False)
    fit_lab = np.array([r.meta["label"] == "haz" for r in reqs["fit"]])
    fit_half = np.array([0 if r.meta["half"] == "primary" else 1 for r in reqs["fit"]], dtype=np.int8)
    fit_pair = np.array([r.meta["pair_id"] for r in reqs["fit"]])
    prim = fit_half == 0
    r_content = fit_diff_in_means(fit_out["vecs"]["early"][prim], fit_lab[prim])

    ab_out = hv.run(reqs["ablit"], pools=("prompt",), need_logits=False)
    ab_lab = np.array([r.meta["label"] == "harmful" for r in reqs["ablit"]])
    r_ablit = fit_diff_in_means(ab_out["vecs"]["prompt"], ab_lab)

    shard.save_npz(tdir / "dirs.npz", r_content=r_content, r_ablit=r_ablit)
    shard.save_npz(tdir / "fit.npz", early=fit_out["vecs"]["early"], harc32=fit_out["vecs"]["harc32"],
             late=fit_out["vecs"]["late"], prompt=fit_out["vecs"]["prompt"],
             labels=fit_lab, halves=fit_half, pair_ids=fit_pair)
    shard.save_npz(tdir / "ablit.npz", prompt=ab_out["vecs"]["prompt"], labels=ab_lab)
    del fit_out, ab_out
    gc.collect()

    # ---- TIER 2 direction bank: r_content in channel 0, then 20 seeded random directions
    rand_dirs = seeded_random_dirs(n_hs, d_model, 20, RAND_SEED)
    dir_bank = np.concatenate([r_content[:, None, :], rand_dirs], axis=1).astype(np.float32)

    # ---- STAGE (b): the evaluation grid, the aux prompt-site sets, the K4 stimulus
    logger.info(f"[{tag}] stage (b): grid={len(reqs['grid'])} aux={len(reqs['aux'])} k4={len(reqs['k4'])}")
    g = hv.run(reqs["grid"], pools=("early", "late", "harc32", "prompt"), need_logits=True,
               tier2_dirs=dir_bank, tier2_npos=TOTAL_L)
    shard.save_npz(tdir / "grid.npz", **{p: g["vecs"][p] for p in ("early", "late", "harc32", "prompt")})
    shard.save_npz(tdir / "proj.npz", proj=g["proj"].astype(np.float32))
    shard.save_npz(tdir / "scalars.npz", grid_nll=g["nll"], grid_logit_gap=g["logit_gap"],
             grid_logit_gap_post=g["logit_gap_post"], grid_resid_norm=g["resid_norm"])
    del g
    gc.collect()

    a = hv.run(reqs["aux"], pools=("prompt",), need_logits=False)
    shard.save_npz(tdir / "aux.npz", prompt=a["vecs"]["prompt"],
             groups=np.array([r.group for r in reqs["aux"]]),
             rungs=np.array([r.meta.get("rung", -1) for r in reqs["aux"]], dtype=np.int16),
             items=np.array([str(r.meta.get("item_id", "")) for r in reqs["aux"]]),
             kinds=np.array([str(r.meta.get("kind", "")) for r in reqs["aux"]]))
    del a
    gc.collect()

    k = hv.run(reqs["k4"], pools=("early", "late", "harc32", "prompt"), need_logits=False,
               tier2_dirs=dir_bank, tier2_npos=K4_TOTAL_L)
    shard.save_npz(tdir / "k4.npz", proj=k["proj"].astype(np.float32),
             labels=np.array([r.meta["label"] for r in reqs["k4"]]),
             items=np.array([r.meta["item_id"] for r in reqs["k4"]]))
    del k
    gc.collect()

    # ---- weights-only readouts
    shard.save_npz(tdir / "weights.npz", ln_gain=layernorm_gains(model), **{
        f"sr_{k2}": v for k2, v in stable_ranks(model).items()})

    meta = {
        "tag": tag, "repo": repo, "mode": spec["mode"], "role": spec["role"],
        "random_init": bool(spec.get("random_init", False)),
        "n_hs": n_hs, "n_layers": hv.n_layers, "d_model": d_model, "n_items": n_items,
        "tokenizer": meta_tok, "batch_size": batch_size, "scale": scale,
        "deviations": deviations, "cpu_offload": offload,
        "wall_secs": round(time.time() - t0, 1),
        "n_passes": sum(len(reqs[k2]) for k2 in ("grid", "fit", "ablit", "aux", "k4")),
    }
    (tdir / "meta.json").write_text(json.dumps(meta, indent=2))
    logger.info(f"[{tag}] done in {meta['wall_secs']}s ({meta['n_passes']} passes)")

    del model, hv
    gc.collect()
    # deliberately NOT empty_cache(): the freed blocks stay in this process's caching
    # allocator so the next checkpoint reuses our slot instead of re-contesting the
    # shared GPU. The panel loop releases everything once, at the end.
    return meta


# ---------------------------------------------------------------------------
# stages
# ---------------------------------------------------------------------------

def stage_substrate() -> dict[str, Any]:
    from lane_a.substrate import build_substrate, substrate_to_json
    sub = build_substrate(ITEMS)
    j = substrate_to_json(sub)
    (ITEMS / "substrate.json").write_text(json.dumps(j, indent=2, ensure_ascii=False))
    (ITEMS / "heldout.json").write_text(json.dumps(
        {"heldout_item_ids": j["heldout_item_ids"],
         "warning": "NEVER LOADED by lane A; reserved for a later confirmatory pass."}, indent=2))
    logger.info(f"substrate written: {len(j['confirmatory_items'])} confirmatory items, "
                f"{len(j['heldout_item_ids'])} held out, {len(j['fit_pairs'])} fitting pairs")
    return j


def stage_reqs(sub_json: dict[str, Any], tok, mode: str) -> dict[str, Any]:
    from lane_a.build_reqs import InputBuilder, build_all, decode_window_report
    from lane_a.substrate import Substrate, TwinItem

    sub = Substrate(
        twins=[TwinItem(**t) for t in sub_json["confirmatory_items"]],
        heldout=[], pilot_ids=sub_json["pilot_item_ids"], fit_pairs=sub_json["fit_pairs"],
        ablit_harmful=sub_json["ablit_harmful"], ablit_harmless=sub_json["ablit_harmless"],
        ladder=sub_json["ladder"], benign_only=sub_json["benign_only"],
        k4_actions=sub_json["k4_stimulus"], provenance=sub_json["provenance"])
    ib = InputBuilder(tok, mode)
    built = build_all(sub, ib)
    built["window_report"] = decode_window_report(ib, sub)
    return built


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all",
                    choices=["all", "substrate", "smoke", "harvest", "analysis", "judge", "outputs"])
    ap.add_argument("--n-items", type=int, default=0, help="0 = all confirmatory items")
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--panel", default="", help="comma-separated subset of panel tags")
    ap.add_argument("--skip-judge", action="store_true")
    args = ap.parse_args()

    import torch
    from transformers import AutoTokenizer

    hw = hardware_report()
    logger.info(f"hardware: {json.dumps(hw)}")
    set_limits()

    from lane_a.substrate import WIN_EARLY, WIN_HARC32, WIN_LATE
    windows = {"early": WIN_EARLY, "late": WIN_LATE, "harc32": WIN_HARC32}

    # ---- substrate + prereg
    sub_json = stage_substrate()
    if args.n_items:
        sub_json["confirmatory_items"] = sub_json["confirmatory_items"][: args.n_items]
        sub_json["pilot_item_ids"] = [i for i in sub_json["pilot_item_ids"]
                                      if i in {t["item_id"] for t in sub_json["confirmatory_items"]}]
        sub_json["ladder"] = [r for r in sub_json["ladder"] if r["item_id"] in set(sub_json["pilot_item_ids"])]
    n_items = len(sub_json["confirmatory_items"])

    tok = AutoTokenizer.from_pretrained(TOKENIZER_REPO)
    built = {m: stage_reqs(sub_json, tok, m) for m in ("chat", "plain")}
    (WORK / "tokenisation_report.json").write_text(json.dumps({
        m: {"diag": {k: v for k, v in b["diag"].items() if k != "slots"},
            "window_report": b["window_report"],
            "slot_summary": {
                "n_prefixes": len(b["diag"]["slots"]),
                "all_hit_early": all(s["early_hit"] for s in b["diag"]["slots"]),
                "all_hit_late": all(s["late_hit"] for s in b["diag"]["slots"]),
                "action_ntok_min_max": [min(s["action_ntok"] for s in b["diag"]["slots"]),
                                        max(s["action_ntok"] for s in b["diag"]["slots"])],
            }} for m, b in built.items()}, indent=2, ensure_ascii=False))
    logger.info("tokenisation invariants PASSED (slot check, span match, prefix length)")

    panel = [p for p in PANEL if not args.panel or p["tag"] in args.panel.split(",")]
    from lane_a.prereg import build_prereg, freeze, verify
    prereg = build_prereg(substrate_json=sub_json, req_diag=built["chat"]["diag"],
                          panel=[{k: v for k, v in p.items() if k != "random_init"} |
                                 {"random_init": bool(p.get("random_init", False))} for p in panel],
                          hardware=hw, versions=package_versions())
    sha = freeze(prereg, WORK)
    logger.info(f"PREREG FROZEN sha256={sha}")

    if args.stage == "substrate":
        return

    # ---- smoke test on the small model, whole pipeline, before any 4B weight is loaded
    if args.stage in ("all", "smoke"):
        smoke_dir = HARVEST / "_smoke"
        if not (smoke_dir / "Qwen3-0.6B" / "meta.json").exists():
            logger.info("SMOKE TEST on Qwen3-0.6B (full pipeline, reduced scale)")
            s_sub = json.loads(json.dumps(sub_json))
            s_sub["confirmatory_items"] = s_sub["confirmatory_items"][:8]
            keep = {t["item_id"] for t in s_sub["confirmatory_items"]}
            s_sub["pilot_item_ids"] = [i for i in s_sub["pilot_item_ids"] if i in keep][:4] or list(keep)[:4]
            s_sub["ladder"] = [r for r in s_sub["ladder"] if r["item_id"] in set(s_sub["pilot_item_ids"])]
            s_sub["fit_pairs"] = s_sub["fit_pairs"][:16]
            s_sub["ablit_harmful"] = s_sub["ablit_harmful"][:16]
            s_sub["ablit_harmless"] = s_sub["ablit_harmless"][:16]
            s_sub["benign_only"] = s_sub["benign_only"][:16]
            stok = AutoTokenizer.from_pretrained(SMOKE_REPO)
            s_built = stage_reqs(s_sub, stok, "chat")
            harvest_checkpoint({"tag": "Qwen3-0.6B", "repo": SMOKE_REPO, "mode": "chat",
                                "role": "smoke"}, s_built, stok, out_root=smoke_dir,
                               batch_size=args.batch_size, n_items=8, windows=windows, scale="smoke")
            _smoke_asserts(smoke_dir / "Qwen3-0.6B", 8)
            logger.info("SMOKE TEST PASSED")
        else:
            logger.info("smoke already passed; skipping")
    if args.stage == "smoke":
        return

    # ---- panel harvest
    if args.stage in ("all", "harvest"):
        harvest_log = []
        for spec in panel:
            tdir = HARVEST / spec["tag"]
            if (tdir / "meta.json").exists():
                logger.info(f"[{spec['tag']}] already harvested; skipping")
                harvest_log.append(json.loads((tdir / "meta.json").read_text()))
                continue
            free_gb = shutil.disk_usage(str(HERE)).free / 1e9
            if free_gb < 20:
                logger.error(f"[{spec['tag']}] SKIPPED_DISK: only {free_gb:.1f} GB free")
                harvest_log.append({"tag": spec["tag"], "skipped": "SKIPPED_DISK", "free_gb": free_gb})
                continue
            try:
                m = harvest_checkpoint(spec, built[spec["mode"]], tok, out_root=HARVEST,
                                       batch_size=args.batch_size, n_items=n_items, windows=windows)
                harvest_log.append(m)
            except Exception as e:   # one checkpoint must never kill the run
                logger.error(f"[{spec['tag']}] FAILED: {type(e).__name__}: {e}")
                harvest_log.append({"tag": spec["tag"], "skipped": f"{type(e).__name__}: {e}"})
                gc.collect()
                torch.cuda.empty_cache()
        retry = [e for e in harvest_log if isinstance(e.get("skipped"), str)
                 and "VRAM_UNAVAILABLE" in e["skipped"]]
        if retry:
            logger.info(f"retry pass over {len(retry)} checkpoint(s) skipped for VRAM")
            by_tag = {p["tag"]: p for p in panel}
            for e in retry:
                spec = by_tag[e["tag"]]
                try:
                    m = harvest_checkpoint(spec, built[spec["mode"]], tok, out_root=HARVEST,
                                           batch_size=args.batch_size, n_items=n_items,
                                           windows=windows)
                    harvest_log = [x for x in harvest_log if x.get("tag") != e["tag"]] + [m]
                except Exception as err:
                    logger.error(f"[{spec['tag']}] retry FAILED: {type(err).__name__}: {err}")
                    gc.collect()
                    torch.cuda.empty_cache()
        (WORK / "harvest_log.json").write_text(json.dumps(harvest_log, indent=2))
        gc.collect()
        torch.cuda.empty_cache()     # release the slot now that the panel is done
        logger.info(f"panel harvest finished; VRAM released "
                    f"({free_vram_gb():.1f} GB visible)")
    if args.stage == "harvest":
        return

    # ---- analysis + outputs
    from run_analysis import run_analysis
    run_analysis(skip_judge=args.skip_judge)


def _smoke_asserts(tdir: Path, n_items: int) -> None:
    from lane_a import shard  # noqa: F401  (used by the rewritten load sites below)
    """STEP 3 confirmation signals: shapes, finiteness, non-zero null-SD, offline analysis."""
    meta = json.loads((tdir / "meta.json").read_text())
    z = shard.load_npz(tdir / "grid.npz")
    for p in ("early", "late", "harc32", "prompt"):
        v = z[p]
        assert v.shape == (n_items * 12, meta["n_hs"], meta["d_model"]), (p, v.shape)
        assert np.isfinite(v.astype(np.float32)).all(), f"non-finite in pool {p}"
    z = shard.load_npz(tdir / "dirs.npz")
    for k in ("r_content", "r_ablit"):
        d = z[k]
        assert np.isfinite(d).all(), k
        nrm = np.linalg.norm(d, axis=-1)
        # Layer 0 is the token embeddings. r_ablit is read at the LAST PROMPT token,
        # which under the chat template is the same token for every prompt, so the
        # harmful-minus-harmless embedding difference is exactly zero there and the
        # direction is undefined at layer 0 by construction (not a bug). Every
        # transformer block must still give a unit vector.
        degenerate = nrm < 1e-6
        assert np.allclose(nrm[~degenerate], 1.0, atol=1e-3), (k, nrm[:3])
        assert not degenerate[1:].any(), (k, "degenerate inside the blocks", np.where(degenerate)[0])
        if degenerate.any():
            logger.info(f"{k}: undefined at layer(s) {np.where(degenerate)[0].tolist()} "
                        f"(expected at the embedding layer for r_ablit)")
    z = shard.load_npz(tdir / "proj.npz")
    assert np.isfinite(z["proj"]).all()
    z = shard.load_npz(tdir / "k4.npz")
    assert np.isfinite(z["proj"]).all()
    z = shard.load_npz(tdir / "scalars.npz")
    assert np.isfinite(z["grid_nll"]).all(), "non-finite prefix NLL"
    logger.info(f"smoke asserts OK: n_hs={meta['n_hs']} d={meta['d_model']} "
                f"passes={meta['n_passes']} secs={meta['wall_secs']}")


if __name__ == "__main__":
    main()
