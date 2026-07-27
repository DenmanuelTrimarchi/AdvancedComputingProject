# results/

`results/aggregate/` holds disclosure-reviewed, anonymised JSON/CSV/Markdown
outputs and **is committed to Git**.

**Status: real evaluation completed 27 July 2026**, following the ethics/DPIA
gate confirmation recorded in `docs/ETHICS_AND_BIOMETRICS.md`, against the
real LFW and CPLFW datasets described in `docs/DATASET_PROVENANCE.md`. See
`results/aggregate/FINAL_EVALUATION_REPORT.md` for the full write-up. Any
individual field still reading `"status": "not_run"` with `null` values (there
should be none as of this run) must never be read as zero and must never be
presented as a real benchmark result — see `docs/EVALUATION_PROTOCOL.md`.

`results/raw/` and `results/pair_scores/` are git-ignored. Anything with a
real image path in it — most importantly the gallery manifest produced by
`scripts/create_gallery_manifest.py` — belongs there, never under
`results/aggregate/`.

Files produced by a full run of `scripts/run_complete_experiment.py`:

```text
results/aggregate/calibrated_threshold.json
results/aggregate/lfw_development_metrics.json
results/aggregate/lfw_final_metrics.json
results/aggregate/cplfw_metrics.json
results/aggregate/duplicate_gallery_metrics.json
```

A hand-written `FINAL_EVALUATION_REPORT.md` summarising all of the above for
the dissertation should also live in `results/aggregate/` once real numbers
exist.
