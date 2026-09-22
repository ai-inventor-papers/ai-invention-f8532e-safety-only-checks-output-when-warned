#!/usr/bin/env python3
"""Write arrays/<tag>/JOIN_README.md -- THE JOIN CONTRACT -- for every harvested tag.

This is the file that makes a later scorer GPU-free: for each saved array it states exactly
which second-order quantity is computable FROM it, and it computes none of them. Nothing here
reads or writes a candidate value, a ranking or a correlation.

Idempotent; safe to re-run after each harvest.

    python3 join_readme.py [--tag TAG ...]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

WS = Path(__file__).resolve().parent.parent
ARRAYS = WS / "arrays"


def npy_header(p: Path) -> tuple[tuple[int, ...] | None, str | None]:
    try:
        with p.open("rb") as f:
            if f.read(6) != b"\x93NUMPY":
                return None, None
            major = f.read(1)[0]
            f.read(1)
            hlen = int.from_bytes(f.read(2 if major == 1 else 4), "little")
            hdr = f.read(hlen).decode("latin1")
        d = eval(hdr, {"__builtins__": {}}, {"False": False, "True": True})  # noqa: S307
        return tuple(d.get("shape", ())), str(d.get("descr"))
    except (OSError, ValueError, SyntaxError, KeyError, TypeError):
        return None, None


TEMPLATE = """# JOIN CONTRACT — `{tag}`

`{repo}` @ `{rev}` · L = {L} layers (so **L+1 = {L1}** hidden indices, 0 = embedding output,
i+1 = output of block i) · d = {d} · params {params} · tie_word_embeddings = `{tie}` ·
forward batching = `{batching}`

This directory is **substrate only**. It holds activations, a direction bank and a
forward-only intervention grid. It contains **no candidate score, no ranking and no
correlation** — by design, because the sibling screen artifact freezes its candidate list
before it opens anything here. Below, each array is paired with what a later GPU-free scorer
could compute *from* it. **None of those quantities is computed in this artifact.**

## Bands are fractions of depth, never layer indices

Band `b` (1..6) = blocks `[floor((b-1)L/6), floor(bL/6))`. L differs across the panel
(640/1024/1152/2048/2560/3072/3840 hidden sizes; 18–54 layers), so any join across
checkpoints must use the band index, never an absolute layer number.

## Base arrays

| file | shape | dtype | what it is | what it supports computing |
|---|---|---|---|---|
| `A_prompt.npy` | {sh_A_prompt} | {dt_A_prompt} | last-prompt-token residual at every layer over the frozen 256 prompt-site stimuli (`assets/stimuli.json`, `y=1` harmful) | a prompt-site read of any direction; the recognition axis; per-layer separation |
| `A_prompt_p1/p2/p3.npy` | {sh_A_prompt_p1} | {dt_A_prompt_p1} | the same stimuli under three EXPRESSION-ONLY perturbations (p1 plain render, p2 helpful system prompt, p3 the same weights cast to float16) | expression-invariance of any prompt-site readout: it must move under a template change only as much as behaviour does |
| `A_dec.npy` / `A_dec_tok1.npy` | {sh_A_dec} | {dt_A_dec} | decode-site residuals: mean over generated positions before the first EOS, and the FIRST generated position | a decode-site readout, and the prompt-site vs decode-site contrast |
| `dec_ntok.npy` | {sh_dec_ntok} | {dt_dec_ntok} | tokens actually generated per row before EOS | the denominator for any decode-site mean; a degenerate-generation filter |
| `A_c11.npy` | {sh_A_c11} | {dt_A_c11} | 64 graded-severity prompts (`assets/c11_items.json`) | severity monotonicity of a readout |
| `A_ams.npy` | {sh_A_ams} | {dt_A_ams} | the 96 rows of `ams_prompts()` (3 concepts × 16 pairs × 2 polarities) in that exact order, RAW text with NO chat template, as the AMS code path pins | the AMS Tier-1 separation sigma, the published baseline instrument, side by side with any activation readout (`results/ams_baseline.json`) |
| `A_cells96.npy` | {sh_A_cells96} | {dt_A_cells96} | the 96 XSTest 2×2 cells (`assets/cells.json`), chat-templated | a cell-level read of the 2×2 design; NOT the AMS row set |
| `WU_ref/WU_hed/WU_ctl.npy` | {sh_WU_ref} / {sh_WU_hed} / {sh_WU_ctl} | {dt_WU_ref} | unembedding rows for refusal / hedge / control tokens, resolved through THIS checkpoint's own tokenizer (kept counts in `meta.json`, never padded) | the LOGIT-ONLY baseline: refusal-token mass, and the logit gap |
| `r_refusal/r_hedge/r_control/r_fullV_final.npy` | {sh_r_refusal} | {dt_r_refusal} | per-layer logit-lens drives on the 256 stimuli | a logit-lens trajectory; where refusal drive appears in depth |
| `norms.npy` | {sh_norms} | {dt_norms} | residual norms | dimensionless ratios, so a readout is not a norm artefact |

## Direction bank — fitted from THIS checkpoint's own activations, parent-free

| file | shape | what it is | what it supports computing |
|---|---|---|---|
| `dirs_F.npy` | {sh_dirs_F} | per-band harmful-vs-benign request axis, unit-normalised band-mean difference-in-means at the last prompt token | the site-local read/write direction per band |
| `dirs_N6.npy` | {sh_dirs_N6} | per-band XSTest benign-twin axis | the over-refusal-relevant axis, distinct from raw harmfulness |
| `dirs_R.npy` | {sh_dirs_R} | matched random directions per band, Gram–Schmidt orthogonalised against BOTH F and N6, seeded `sha256(seed+tag+band)` | the null distribution for any direction-specific claim |
| `fit_halves.npy` | {sh_fit_halves} | the TWO split-half fits of F per band | direction stability = the cosine between the halves. **The halves are saved; the cosine is NOT taken here.** |

## Intervention grid — `cells/<cell_id>/`, catalogue in `cells_index.json`

An intervention projects a direction out of the residual stream at every layer of a band, at a
SITE (`P` = last prompt token, `A` = all prompt positions), then continues the forward pass.
The 32 prompts (16 harmful / 16 hard-benign) and their hash are in `cells_32.json`; row order
is preserved exactly.

Cell families: `arm0` (no intervention, both sites) · `C2` site-local 6 bands × {{F, N6}} ×
{{P, A}} · `C3` matched-displacement random controls · `C4` the nested cumulative ladder
S1={{B4}} … S6={{B1..B6}}. Per cell: `proj.npy` (projection of each layer's residual onto the
fixed K-direction bank; for site A two slices, position-mean and last token), `norms.npy`,
`logits.npy` (softmax mass on WU_ref / WU_hed / WU_ctl at the next-token position),
`topk_ids.npy` / `topk_probs.npy`, and `full.npy` (the whole residual, f16) for arm0, the C2
F/N6 cells and the C4 ladder cells only.

**The R cells are MATCHED-DISPLACEMENT, not matched-norm-direction**: the edit is
`h ← h − (h·f̂)·r̂`, so the displacement magnitude equals the F cell's `|h·f̂|` token by token
(verified by selftest T3d at 1.0002×). Projecting out a random *unit* direction would remove
only `|h·r̂|`, which is negligible in high dimension, and would not be a matched control.

What the grid supports computing, and this artifact does not:

- a **site-local write-gain** statistic: contrast `proj.npy` of a C2 cell against `arm0` at
  layers ABOVE the ablated band, net of the C3 cells at identical displacement;
- a **redundancy-depth** statistic: the C4 ladder S1→S6 read as the cumulative change in
  refusal-token mass in `logits.npy` relative to `arm0`;
- a **specificity** statistic: the same contrasts on the benign half of `cells_32.json`;
- a **direction-vs-magnitude** test: any F/N6 effect must exceed its matched-displacement C3
  null, which is what makes the effect attributable to the direction rather than to the kick.

## Provenance and gating

`meta.json` carries the repo, revision sha, depth, width, dtype, tie_word_embeddings,
chat-template sha, trust_remote_code, load format, transformers version, the 6-tensor
`weight_fingerprint` AND `weight_sha_full` (the fingerprint cannot see q/v LoRA merges),
per-stage timings, the WU kept counts and the peak VRAM. `MANIFEST.sha256.json` hashes every
file, and `DONE` is written last.

This directory exists only because `{tag}` appeared in a `graded_truth_s<N>.json` whose sha256
was already in `logs/chain.jsonl` when the harvest started — the ORDER GATE. The behaviour was
graded before the activations were read, never the other way round, and
`src/hygiene_check.py all` re-audits that ordering.

_Generated {utc} by `src/join_readme.py`._
"""


def write_for(tag_dir: Path) -> bool:
    meta: dict[str, Any] = {}
    mp = tag_dir / "meta.json"
    if mp.exists():
        try:
            meta = json.loads(mp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            meta = {}
    names = ["A_prompt", "A_prompt_p1", "A_dec", "dec_ntok", "A_c11", "A_ams", "A_cells96",
             "WU_ref", "WU_hed", "WU_ctl", "r_refusal", "norms", "dirs_F", "dirs_N6", "dirs_R",
             "fit_halves"]
    fmt: dict[str, Any] = {}
    for n in names:
        sh, dtp = npy_header(tag_dir / f"{n}.npy")
        fmt[f"sh_{n}"] = str(list(sh)) if sh else "—"
        fmt[f"dt_{n}"] = (dtp or "—")
    L = meta.get("n_layers")
    body = TEMPLATE.format(
        tag=tag_dir.name, repo=meta.get("repo", "?"), rev=str(meta.get("revision_sha"))[:12],
        L=L if L is not None else "?", L1=(L + 1) if isinstance(L, int) else "?",
        d=meta.get("hidden_size", "?"), params=meta.get("n_params", "?"),
        tie=meta.get("tie_word_embeddings"), batching=meta.get("harvest_batching", "?"),
        utc=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **fmt)
    tmp = tag_dir / "JOIN_README.md.tmp"
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, tag_dir / "JOIN_README.md")
    _refresh_manifest_entry(tag_dir, "JOIN_README.md")
    return True


def _refresh_manifest_entry(tag_dir: Path, rel: str) -> None:
    """Re-hash this file in MANIFEST.sha256.json if the manifest already lists it.

    Rewriting a listed file without this leaves its recorded sha256 stale, which
    results/manifest_verification.json then reports as a drift. The manifest must always
    describe what is on disk."""
    import hashlib
    mp = tag_dir / "MANIFEST.sha256.json"
    f = tag_dir / rel
    if not mp.exists() or not f.exists():
        return
    try:
        man = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    files = man.get("files") if isinstance(man.get("files"), dict) else man
    if not isinstance(files, dict) or rel not in files:
        return
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    ent = files[rel]
    if isinstance(ent, dict):
        ent["sha256"] = h
        if "bytes" in ent:
            ent["bytes"] = f.stat().st_size
    else:
        files[rel] = h
    mp.write_text(json.dumps(man, indent=1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", nargs="*", default=None)
    ns = ap.parse_args()
    dirs = [ARRAYS / t for t in ns.tag] if ns.tag else sorted(
        d for d in ARRAYS.iterdir() if d.is_dir() and (d / "DONE").exists())
    n = 0
    for d in dirs:
        if d.is_dir():
            write_for(d)
            n += 1
    print(f"JOIN_README.md written for {n} tag(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
