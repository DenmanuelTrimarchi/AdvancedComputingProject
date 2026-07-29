# results/

`results/aggregate/` holds disclosure-reviewed, anonymised JSON/CSV/Markdown
outputs and **is committed to Git**.

**Status: real evaluation completed 28 July 2026** (rerun against the raw,
authors-distributed CPLFW `images.rar` image set; an earlier 27 July 2026 run
used the pre-aligned `cp-aligned.zip` copy — see `docs/DATASET_PROVENANCE.md`
for why), following the ethics/DPIA gate confirmation recorded in
`docs/ETHICS_AND_BIOMETRICS.md`, against the real LFW and CPLFW datasets
described in `docs/DATASET_PROVENANCE.md`. See
`results/aggregate/FINAL_EVALUATION_REPORT.md` for the full write-up. Any
individual field still reading `"status": "not_run"` with `null` values (there
should be none as of this run) must never be read as zero and must never be
presented as a real benchmark result — see `docs/EVALUATION_PROTOCOL.md`.

`results/raw/` and `results/pair_scores/` are git-ignored. Anything with a
real image path in it — most importantly the gallery manifest produced by
`scripts/create_gallery_manifest.py` — belongs there, never under
`results/aggregate/`.

`results/report_evidence/` holds the report evidence pack — nine figures,
eleven rendered command-evidence images (screenshots 01-11), four further
manual screenshots (12-15, never fabricated), `REPORT_EVIDENCE_INDEX.md`,
`SCREENSHOT_INDEX.md` and a SHA-256 manifest — generated from
`results/aggregate/*` by `scripts/generate_report_evidence.py`. Committed,
and aggregate-only: no raw image, embedding, identity or absolute path. Its
`logs/` subdirectory is git-ignored (it is the raw local record behind the
rendered images). GitHub Actions is not among the screenshots — validation
is local (see `docs/REPRODUCIBILITY.md`).

`results/historical/` holds superseded results, kept only so a reader can see
what changed and why — never a current finding. See
`results/historical/README.md`.

Files produced by a full run of `scripts/run_complete_experiment.py` (the
last five are generated automatically from the first five, not hand-written):

```text
results/aggregate/calibrated_threshold.json
results/aggregate/lfw_development_metrics.json
results/aggregate/lfw_final_metrics.json
results/aggregate/cplfw_metrics.json
results/aggregate/duplicate_gallery_metrics.json
results/aggregate/run_manifest.json
results/aggregate/metrics_summary.csv
results/aggregate/confusion_matrices.csv
results/aggregate/roc_points.csv
results/aggregate/FINAL_EVALUATION_REPORT.md
```
