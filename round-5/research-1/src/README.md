# Is our redundancy safety metric already taken? (iter-5 prior-art closure pass)

A dated (2026-09-22), web-only research artifact for the Qwen3-4B mechanistic safety-metric study. It answers three questions before the paper is written:

1. **Saturation.** Are any of the 12 candidate per-checkpoint readouts (W1–W8, G1–G4) already published?
2. **Target.** Is over-refusal still unused as the *target* of a per-checkpoint internal readout?
3. **Dimensionality.** Has anyone factor-analysed a family of internal safety scores?

It also re-pins the AMS baseline tool, fixes the bibliography and writes the must-not-claim ledger. It loads no models and costs $0.

**Headline:**
- No candidate is CLOSED.
- Over-refusal-as-target is OPEN.
- No factor analysis of internal safety scores exists, so the P1 bound would be a contribution.
- The AMS batch-8 padding bug is measured at up to 5.28σ.

## Layout
| path | what |
|---|---|
| `research_out.json` | final answer, 51 sources, follow-ups (the deliverable) |
| `research_report.md` | long form: answer + every table in full |
| `saturation_table.json` | W1–W8, G1–G4 verdicts in the iter-4 cell_table row shape |
| `target_cell_table.json` | 14 papers × 6 columns, over-refusal-as-target (copy of `blockT/`) |
| `ams_spec_iter5.json` | AMS eight facts with code-line evidence + measured padding ruling |
| `references_iter5.bib` | 61 entries, amended from iter-4's 54 |
| `bib_changelog.json` | one record per touched entry |
| `must_not_claim.json` | 23 fence items with owner and quote |
| `research_verification.json` | quote re-verification, deletions, absence claims, beyond-horizon items |
| `inputs/` | `candidate_definitions.md`, `carryover.json` (Block 0 intake) |
| `blockS/` | lane outputs: `lane_SA.json` (circuits/self-repair), `lane_SBC.json` (redundancy/geometry), handbook silence greps |
| `blockT/`, `blockD/` | over-refusal table; dimensionality analysis (`dimensionality.json`), with their search logs |
| `blockA/` | tokenizer configs, PyPI/GitHub drift checks, transformers default |
| `blockB/` | arXiv id batch resolution, bib metadata fetches |
| `blockP/` | `answer.md`, `contribution_branches.md` |
| `searchlog/` | one file per query family (literal query, mode, date, hits) |
| `verify/` | collected quotes/absences and their re-fetch results |
| `*.py` | `build_saturation.py`, `collect_quotes.py`, `verify_quotes.py`, `verify_absences.py`, `build_out.py`, `assemble.py`, `build_report.py` |

## How to run / rebuild

Web access goes through the `aii-web-tools` skill scripts. Rebuild the outputs from the block files in this order:
```bash
python3 build_saturation.py      # merge lanes -> saturation_table.json
python3 collect_quotes.py        # gather every quote + absence claim
python3 verify_quotes.py         # re-fetch each quote against its own URL
python3 verify_absences.py       # reproduce zero-matches with positive controls
python3 build_out.py             # verification ledger + source list
python3 assemble.py              # research_out.json + struct output
python3 build_report.py          # research_report.md
```
Re-running `verify_*.py` hits the live web, so results can drift with the date.

## Restoring removed files
Nothing is marked `delete` in `.aii/manifest.yaml`. Every file here is text or JSON under the 10 MB floor, and there is no cache, venv or checkpoint to restore.
