# Evaluation protocol

Status: **preregistered design.** Whether real benchmark numbers exist yet
depends on whether `scripts/run_complete_experiment.py` (or the individual
experiment scripts) has actually been run against real LFW/CPLFW data — see
`results/README.md` for the current status of `results/aggregate/*.json`.

## The validation / held-out boundary

This is the single methodological guarantee the rest of this document
exists to protect, and it is enforced in code
(`src/face_verification/calibration.py`), not only here:

1. **Calibrate** on `pairsDevTrain.txt` only (`scripts/calibrate_lfw.py`).
   `calibration.calibrate()` raises `CalibrationError` if asked to run on
   anything not labelled the `"validation"` split.
2. **Develop** on `pairsDevTest.txt` (`scripts/evaluate_lfw.py --split dev`).
   Candidate thresholds are evaluated, never recomputed, here. One threshold
   is frozen using a documented rule (default: maximum balanced accuracy on
   this split; pass `--operating-strategy` to `calibrate_lfw.py` to choose a
   different rule up front).
3. **Finalise** on `pairs.txt` (`scripts/evaluate_lfw.py --split final`) and
   on `pairs_CPLFW.txt` (`scripts/evaluate_cplfw.py`), using the already
   -frozen threshold artifact. `calibration.require_frozen_threshold()`
   refuses to run either script against a threshold artifact whose `status`
   is not `"frozen"`.
4. **Gallery** (`scripts/create_gallery_manifest.py` /
   `evaluate_duplicate_gallery.py`) excludes every image referenced by the
   calibration protocol from the gallery pool.

## Experiment 1 — threshold calibration (LFW `pairsDevTrain.txt`)

Produces a threshold for each of: maximum balanced accuracy, maximum F1,
equal error rate, and target false-match rates of 0.001, 0.01 and 0.05
(`src/face_verification/metrics.select_threshold`). All candidates are
recorded in one artifact (`results/aggregate/calibrated_threshold.json`);
one is selected as the operating threshold.

## Experiment 2 — development validation (LFW `pairsDevTest.txt`)

Evaluates the frozen candidate thresholds without changing them. Reports:
accuracy, precision, recall, F1, ROC-AUC, false match rate, false non-match
rate, true match rate, equal error rate, confusion matrix, face-extraction
failure rate, and embedding-time statistics (see `results/aggregate/lfw_development_metrics.json`).

## Experiment 3 — final LFW evaluation (`pairs.txt`)

The untouched, official ten-fold LFW protocol (6,000 pairs). Uses the frozen
threshold from Experiment 1 without recalibration. This is the headline LFW
verification result.

## Experiment 4 — CPLFW generalisation

Uses the *same* frozen LFW threshold — no separate CPLFW calibration.
Answers: does a threshold calibrated on ordinary LFW pairs remain reliable
when pose differs substantially between the two images? Reports the change
in accuracy, FMR, FNMR, F1, EER, face-extraction failure rate and processing
latency relative to Experiment 3.

## Experiment 5 — real 1:N duplicate-profile gallery

Built from real LFW images not used in calibration
(`src/face_verification/gallery_evaluator.py`):

- one image per gallery identity represents an existing registered profile;
- a second image of the same identity is a duplicate-registration probe;
- an identity absent from the gallery is a legitimate unknown probe;
- every image occupies exactly one manifest role (enforced —
  `GalleryError` if violated);
- the manifest is deterministic given a fixed seed
  (`config.DEFAULT_RANDOM_SEED`);
- manifest entries use opaque, one-way identifiers
  (`privacy.opaque_id`) — never a real identity name.

Reports duplicate detection rate, false duplicate-review rate, rank-1
identification rate, true duplicate miss rate, and gallery-search timing.
**A result above threshold opens a human-review case. It is never
interpreted as evidence of scam activity, and nothing in this repository
bans, rejects or accuses an identity based on it.**

## Face-extraction failures

Zero-face and multi-face detections are recorded as their own explicit
failure categories (`verification_evaluator.EvaluationResult.failures`) and
reported as an explicit failure rate alongside the accuracy metrics — they
are never quietly excluded from the pair/probe count the way a naive
implementation might drop them.

## Synthetic vs. real evidence

Every artifact this pipeline writes states plainly, via its
`artifact_type`/`status`/`note` fields, whether it reflects a real benchmark
run or is a `not_run` placeholder (see `results/README.md`). The unit tests
under `tests/` use synthetic fixture vectors exclusively and are never cited
as biometric accuracy evidence — they establish only that the calculation
and control logic (metrics math, partition isolation, model-hash
verification, gallery determinism) behaves as specified.
