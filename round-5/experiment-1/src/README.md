# Wide screen of 15 second-order safety readouts (iteration 5, run_YqmEFECOIR3D)

A pre-registered screen of fifteen **second-order, single-model activation readouts** of safety —
quantities about how a model *uses* its refusal/request axis rather than how large that axis is —
scored beside the field's incumbent bars (final-layer logit gap BL1, AMS σ, the iteration-4
N-candidates, the mandatory difference-in-means floor, a prompting ceiling, two text bars), frozen
by a SHA-256 hash chain, and then confirmed **once** on 12 held-out checkpoints produced blind by a
sibling artifact.

Everything is cross-fitted (directions and the band `b*` are fit on one prompt fold and scored on
the other, then the folds are swapped and averaged) and every candidate reads **activations or
weights of one model** — logit and text quantities appear only as bars.

## Headline results

**No candidate passes the registered bar.** All 11 frozen survivors fail selection clause (ii): at
n = 12 (MDE 0.73) no paired checkpoint-bootstrap CI on |ρ| − |ρ_BL1_easy| excludes zero, and no
partial ρ given BL1_easy and AMS excludes zero. **The competing one-coordinate bound (P1) also
fails**: the 15 × 48 candidate matrix has effective rank 7.16 (entropy; 5.32 participation) and the
leading checkpoint-space singular vector has |cos| = 0.645 with z(BL1_easy).

What the run does deliver is a measured trade-off, on evidence the screen never touched:

| quantity (held-out panel) | ρ with over-refusal | ρ with harmful compliance | n | MDE |
|---|---|---|---|---|
| W3 positional redundancy ratio | **−0.943** | +0.754 | 6 | 0.92 |
| G4 BL1-orthogonal Fisher separation | **−0.815** | +0.643 | 12 | 0.73 |
| plain difference-in-means (FLOOR) | −0.683 | +0.728 | 12 | 0.73 |
| G3 used-ness | −0.673 | +0.767 | 12 | 0.73 |
| AMS Tier-1 σ (incumbent) | +0.657 | −0.696 | 6 | 0.92 |
| C13_peak_d (iteration-4 bar) | −0.450 | +0.193 | 12 | 0.73 |
| N1 (iteration-4 bar) | +0.375 | −0.510 | 12 | 0.73 |
| **BL1_easy final-layer logit gap** | **+0.152** | −0.387 | 12 | 0.73 |

1. Self-fitted **activation** readouts predict held-out over-refusal; the **logit gap does not**
   (+0.15). AMS σ lands at +0.66 — the *opposite* sign to every activation candidate.
2. The **difference-in-means floor already reaches −0.68**, so the new second-order candidates buy
   little over the field's simplest baseline; the reproducible gap is between the activation class
   and the logit/AMS class.
3. **Every observed sign is opposite to the registered expectation.** Higher harm-separation means
   *less* over-refusal and *more* harmful compliance: these readouts locate a checkpoint on the
   refusal/permissiveness trade-off; they do not measure "more safety".
4. **Specificity vs sensitivity.** On 24 behaviourally graded no-op edits the five GEOMETRIC
   candidates (G1–G4, A3) and W2 raise **zero** false alarms where BL1_easy raises 11 (exact McNemar
   p = 0.00098 for the geometric five; W2 0 vs 7 on its 14 evaluable pairs, p = 0.0156). The other
   write-handle candidates are *not* more specific: W1 alarms on 6 no-ops where BL1 alarms on 1
   (p = 0.125) and W7 on 2 vs 1 (p = 1.0). Yet the same candidates detect at most **3 of 10** real
   safety-changing edits (G3 3, G1 2, G4 2, A3 1, G2 0, W1/W2/W7 0). Sensitivity, not specificity, is
   the binding failure, and the trade-off runs *through* the activation class.
5. **Commissioned four-way Qwen3-4B comparison** (`results/screen/quartet_headlines.json`):
   abliteration *rotates* the request axis (|cos| with the instruct model 0.98, 0.77, 0.36, 0.015,
   0.13, 0.22 over the six depth bands) and the child still separates harmful from benign along its
   **own** axis (d = 4.83 at B4) while the parent's axis has gone blind on it (d = 0.22) — the direct
   argument for self-fitted, parent-free readouts. The official SafeRL fine-tune keeps the axis
   (|cos| ≥ 0.87 everywhere) and sharpens it (d 6.63 vs 5.78); instruction tuning *creates* it
   (Base↔instruct |cos| ≤ 0.53); a non-safety STaR fine-tune rotates far less (0.43 at B4).
   Contrary to the inherited claim, abliteration also *shrinks* the axis (~40% at B4–B6).

Limitations we measured rather than assumed: the activation-patching validation disagrees with the
first-order ablation per item (+0.53 / −0.54 / +0.40 on the three declared checkpoints); W2 is
fold-unstable and NaN on every held-out row; the W-family normaliser degenerates on base models with
no refusal behaviour; two survivors (G3, A1) are RANK_UNSTABLE across prompt/fold/band draws; the
48-row screen panel contains only **7 independent lineages**, and under a lineage-cluster bootstrap
G4's and W3's margins over BL1_easy *do* exclude zero — reported as a sensitivity, not as a pass.

## Pipeline (stage order proved by `results/hashchain.jsonl`, verified in `results/chain_verification_final.json`)

| Stage | Script | Output |
|---|---|---|
| P0 inventory / reuse / regression | recon step, `src/bars.py`, `src/regression_check.py`, `src/validate_bars.py` | `results/asset_inventory.json`, `results/deviations.json`, `results/bars_validation.json` (11 bars reproduce iteration 4 on 51/51 tags, max rel diff 4e-8), `results/regression_check.json` (band convention verified: direction cosines reproduce to <1e-6) |
| Unit tests T1–T13 | `src/unit_tests.py`, `src/rowhooks.py` self-test | `results/unit_tests.json` (12/13; T11 = bf16 padding noise), `results/unit_tests_rowhooks.json` |
| S1 prereg, frozen before any candidate value | `src/prereg.py`, `src/amend.py` | `results/prereg.json` + `.sha256` (689216f4…, 00:49:37Z), 7 amendments in `results/prereg_amendments_b{1..4}.json` |
| S2.1 panel rule | `src/panel.py` | `results/panel.json` (48 of 72 graded rows) |
| S2.2 Tier A (array-only) | `src/tierA.py`, `src/quartet.py`, `src/a3_decomp.py` | `results/screen/tierA/*.json` (54), `quartet_tierA.json`, `a3_variance_decomposition.json`, `pair_boot_tierA.json` |
| S2.4 Tier B (GPU intervention) | `src/tierB.py`, `src/rowhooks.py`, `src/interv.py` | `results/screen/ckpt_*.json` (42 OK, 6 INTERVENTION_MISSING) + `_items.npz` |
| S2.6 assemble | `src/assemble_screen.py` | `results/screen_table.json` (810 rows, 1302 bars) |
| S3 pre-screen + effective rank (own process, open() audit) | `src/prescreen.py` | `results/prescreen.json` (4 dropped / 11 kept), `results/rank_analysis.json`, `logs/s3_open_audit.txt` |
| S4 freeze | `src/freeze.py` | `results/survivor.json` + `.sha256` (8f0b7db5…, 03:06:19Z), `results/order_proof.json` |
| S5 held-out join (opened 04:31Z) | `run_s5.sh`, `src/s5_prepare.py`, `src/confirm_harvest_all.py`, `src/confirm_score.py`, `src/join.py`, `src/pair_audit.py` | `results/confirmation.json`, `results/pair_audit.json`, `results/confirm/*` |
| Sensitivities | `src/cluster_sensitivity.py`, `src/confirm_cluster_sensitivity.py`, `src/stability_flags.py` | `results/cluster_sensitivity.json`, `results/confirm_cluster_sensitivity.json`, `results/stability_flags.json` |
| S6 outputs | `method.py` | `method_out.json` (+ `full_`/`mini_`/`preview_`), 14 datasets |

Digests: `results/screen_headlines.json`, `results/confirm_headlines.json`,
`results/screen/quartet_headlines.json`, `results/confirm_bar_comparison.json`.
Deviations and amendments: `results/deviations*.json` (including 13 orchestrator-level entries) and
`results/prereg_amendments.json` (a cumulative, unchained view of the four chained batches).

## Layout

- `method.py` — final assembly into the exp_gen_sol_out schema.
- `src/` — all code; `src/SPEC_*.md` implementation specs; `src/ASSETS.md` verified asset facts;
  `src/reuse/` copies of iteration-2/3/4 modules (originals never edited).
- `results/` — every deliverable (JSON; per-item arrays as `.npz`), including the hash chain.
- `logs/` — run logs, the S3 open() audit, the pre-reissue chain, a backup of the Tier-B records.
- `env/`, `restore.sh` — pinned requirements and the environment rebuild.

## How to run

```bash
bash restore.sh gpu && bash restore.sh ams          # rebuild .venv_gpu / .venv_ams
PY=.venv_gpu/bin/python
$PY src/unit_tests.py
$PY src/prereg.py            # refuses to overwrite an existing freeze
$PY src/panel.py && $PY src/tierA.py --all && $PY src/tierA.py --pair-boot
$PY src/quartet.py && $PY src/a3_decomp.py
$PY src/tierB.py --queue results/tierB_queue.json   # GPU, 4.5 GB flock lease
$PY src/assemble_screen.py && $PY src/prescreen.py && $PY src/freeze.py
bash run_s5.sh                                      # only after results/survivor.sha256 exists
$PY src/cluster_sensitivity.py && $PY src/confirm_cluster_sensitivity.py && $PY src/stability_flags.py
$PY method.py
```

## Restoring removed files

Per `.aii/manifest.yaml`, these are deleted after the round and rebuilt with:

- `.venv_gpu/` → `bash restore.sh gpu` (torch 2.9.1+cu128, transformers 5.17, `env/requirements_gpu.txt`)
- `.venv_ams/` → `bash restore.sh ams` (`ams-scanner[cli]==0.1.3`, `torch==2.9.1+cpu`)
- `cache/` → rebuilt on demand by `src/tierA.py` / `src/bars_partial.py`
- `results/confirm_harvest/` → `.venv_gpu/bin/python src/confirm_harvest_all.py` (the scored values
  are kept in `results/confirm/ckpt_*.json`)
- `hf_cache/` → empty by design: this artifact used the run's shared HF cache; every model is
  re-downloadable from the Hub by the repo id recorded in each `meta.json`.
