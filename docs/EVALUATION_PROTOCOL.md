# Evaluation protocol

Status: **executed.** `scripts/run_complete_experiment.py` ran against real
LFW data and the raw (`images.rar`) CPLFW image set on 28 July 2026 (an
earlier 27 July 2026 run used the pre-aligned `cp-aligned.zip` CPLFW copy —
see `docs/DATASET_PROVENANCE.md`), following the ethics/DPIA gate
confirmation in `docs/ETHICS_AND_BIOMETRICS.md`. See
`results/aggregate/FINAL_EVALUATION_REPORT.md` for the results and
`results/README.md` for the current status of each `results/aggregate/*.json`
file.

## The validation / held-out boundary

This is the single methodological guarantee the rest of this document
exists to protect, and it is enforced in code
(`src/face_verification/calibration.py`), not only here:

1. **Calibrate** on `pairsDevTrain.txt` only (`scripts/calibrate_lfw.py`).
   `calibration.calibrate()` raises `CalibrationError` if asked to run on
   anything not labelled the `"validation"` split.
2. **Develop** on `pairsDevTest.txt` (`scripts/evaluate_lfw.py --split dev`).
   Candidate thresholds are evaluated, never recomputed, here. Exactly one is
   then frozen — automatically, with no CLI override — by a fixed
   deterministic rule: maximum balanced accuracy on this split, ties broken
   by lower development-split false match rate, then by candidate name (see
   `face_verification.calibration.SELECTION_RULE`). The winning candidate's
   name (e.g. `"balanced_accuracy"`, `"f1"`, `"eer"`, `"target_fmr_0.01"`) is
   recorded as `operating_strategy` in the frozen artifact — it is an output
   of this step, not an input to it.
3. **Finalise** on `pairs.txt` (`scripts/evaluate_lfw.py --split final`) and
   on `pairs_CPLFW.txt` (`scripts/evaluate_cplfw.py`), using the already
   -frozen threshold artifact. `calibration.require_frozen_threshold()`
   refuses to run either script against a threshold artifact whose `status`
   is not `"frozen"`.
4. **Gallery** (`scripts/create_gallery_manifest.py` /
   `evaluate_duplicate_gallery.py`) excludes every image referenced by the
   calibration protocol from the gallery pool.

## Experiment 1 — threshold calibration (LFW `pairsDevTrain.txt`)

Produces a candidate threshold for each of: maximum balanced accuracy,
maximum F1, equal error rate, and target false-match rates of 0.001, 0.01
and 0.05 (`src/face_verification/metrics.select_threshold`). All candidates
are recorded in one artifact (`results/aggregate/calibrated_threshold.json`)
with `status: "candidates"`. This stage never selects a winner — selection
happens only in Experiment 2, against a different, held-out split.

## Experiment 2 — development validation (LFW `pairsDevTest.txt`)

Evaluates every Experiment-1 candidate threshold against `pairsDevTest.txt`
and selects exactly one, by the fixed rule in the validation/held-out
boundary section above. Only after this selection is the threshold artifact
updated in place to `status: "frozen"`. Reports: accuracy, precision,
recall, F1, ROC-AUC, false match rate, false non-match rate, true match
rate, equal error rate, confusion matrix, face-extraction failure rate, and
embedding-time statistics (see
`results/aggregate/lfw_development_metrics.json`).

## Experiment 3 — final LFW evaluation (`pairs.txt`)

The untouched, official ten-fold LFW protocol (6,000 pairs). Uses the
threshold selected and frozen in Experiment 2 without recalibration — the
candidates Experiment 1 generated are never used directly. This is the
headline LFW verification result.

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

On the raw CPLFW protocol this is the dominant finding. Of the 6,000 raw
CPLFW protocol pairs, 3,515 produced valid similarity scores and 2,485
failed during face extraction. The extraction-failure rate was therefore
**41.42%** (2,485 ÷ 6,000). These failed pairs were retained in the protocol
total and reported separately rather than being silently discarded.

The 2,485 failures comprised 974 zero-face detections on the left image,
1,347 zero-face detections on the right image, 115 multiple-face detections
on the left image and 49 multiple-face detections on the right image.

Accuracy, precision, recall, F1-score, ROC-AUC and EER are conditional on
the 3,515 pairs for which both images produced exactly one valid face. An
extraction failure is **not** a verification error: no similarity score was
ever produced for those pairs, so they can be neither correct nor incorrect.

### Reading the side-specific categories

`evaluate_pairs` attempts the left image first and abandons the pair at its
first terminal failure, so **each failed pair carries exactly one category**
and the four categories sum to 2,485 exactly. They are a partition of the
failed pairs, not a tally of failures per image.

The consequence matters for interpretation: `zero_faces_right` means the
right-hand image yielded no detectable face *after the left-hand image had
already passed the extraction checks*. Where both images of a pair would
have failed, only the left-hand category is recorded. The left/right counts
are therefore not directly comparable as a measure of which side is harder,
and the right-side counts are a lower bound on how often that side fails.

### Failure-rate traceability

Every figure above is derived at run time from the pair counts; none is
transcribed by hand.

- Pair extraction and failure classification:
  `src/face_verification/verification_evaluator.py` → `evaluate_pairs`
  (its inner `embed_side` and `record` helpers assign the category)
- Failure counts and rate:
  `src/face_verification/verification_evaluator.py` →
  `EvaluationResult.scored_pair_count`, `EvaluationResult.failed_pairs`,
  `EvaluationResult.failure_rate`, guarded by
  `EvaluationResult.validate_accounting`
- Aggregate metric assembly:
  `src/face_verification/verification_evaluator.py` → `summarize_metrics`
- CPLFW result construction:
  `scripts/evaluate_cplfw.py` → `main`
- Final report rendering:
  `scripts/run_complete_experiment.py` → `_render_final_report` and
  `_render_failure_breakdown`
- Report figures:
  `scripts/generate_report_evidence.py` → `figure_04_failure_rates` and
  `figure_05_cplfw_breakdown`

The JSON artifacts store `failure_rate` as a decimal fraction
(`0.4141666666666667`); the percentage is computed only when rendering
human-readable text.

## Synthetic vs. real evidence

Every artifact this pipeline writes states plainly, via its
`artifact_type`/`status`/`note` fields, whether it reflects a real benchmark
run or is a `not_run` placeholder (see `results/README.md`). The unit tests
under `tests/` use synthetic fixture vectors exclusively and are never cited
as biometric accuracy evidence — they establish only that the calculation
and control logic (metrics math, partition isolation, model-hash
verification, gallery determinism) behaves as specified.
