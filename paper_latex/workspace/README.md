# Specificity and Causality Audits for Activation-Based Safety Readouts

Publication-ready LaTeX paper compiled to PDF.

## Layout

- `paper.tex` — LaTeX source (11pt, letterpaper, 1in margins, natbib)
- `paper.pdf` — Compiled 18-page PDF
- `references.bib` — 31 BibTeX entries fetched from Semantic Scholar
- `figures/` — 5 pre-generated figures:
  - `fig_overview_v0.jpg` — Concept diagram of the three-experiment design
  - `fig_specificity_v0.pdf` — False-alarm vs sensitivity scatter plot
  - `fig_displacement_v0.pdf` — Displacement comparison bar chart
  - `fig_causal_grid_v0.pdf` — Causal grid heatmaps (instruct + SafeRL)
  - `fig_probe_v0.pdf` — Probe AUROC survival under directional lesion

## How to Compile

```bash
pdflatex -interaction=nonstopmode paper.tex
bibtex paper
pdflatex -interaction=nonstopmode paper.tex
pdflatex -interaction=nonstopmode paper.tex
```

## Restoring Removed Files

No files were marked for deletion. All outputs are text, code, or small figures.
