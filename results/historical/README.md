# results/historical/

Superseded results, kept only so a reader can see what changed and why.
**Nothing here is a current finding.** Every file carries
`"status": "superseded"` and names the artifact that replaced it.

Do not cite a number from this directory in the report except as an
explicitly-labelled historical comparison.

| File | What it was | Why superseded |
|---|---|---|
| `cplfw_aligned_metrics_2026-07-27.json` | The 27 July 2026 CPLFW evaluation, scored against the pre-aligned `cp-aligned.zip` image set (93.86% accuracy, 54.38% extraction failure) | `images.rar` had never been extracted (no RAR tool installed). Replaced by the raw-image rerun on 28 July 2026 — see `results/aggregate/cplfw_metrics.json` and `docs/DATASET_PROVENANCE.md`. |

The aligned *image files* themselves were not deleted either; they are
retained untouched at a private, gitignored backup location outside this
repository.
