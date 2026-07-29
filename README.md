# AdvancedComputingProject

Design and Evaluation of a Face-Verification and Duplicate-Profile Detection
Proof of Concept Using Real-World Benchmark Datasets.

## Why this is a separate repository

The companion repository, `AdvancedComputingProjectYes`, is an Expo/React
Native dating app with a Convex backend. The supervisor rejected an earlier
version of that project's proposal for relying on artificial profiles,
synthetic images, mock reports and simulated security scenarios, and
required validation on real public benchmark datasets, with a narrower
research scope. Rather than bolting real-data evaluation onto a dating app,
this repository is a standalone research artefact: no Expo, no React
Native, no Clerk, no Convex, no Next.js, no authentication, no database
service. It runs entirely as local Python command-line programs and can be
reproduced without touching `AdvancedComputingProjectYes` at all.

## Research question

> How effectively can a pretrained face-embedding model verify whether two
> unconstrained facial images belong to the same person and identify
> potential duplicate profiles under a human-review decision policy?

## Research contribution

Not a new face-recognition model, and not a dating application. The
contribution is a reproducible empirical evaluation of a fixed, pinned
face-verification pipeline (OpenCV YuNet detection + SFace embedding) on
real benchmark data:

1. validation-only calibration of face-similarity operating thresholds;
2. measurement of the false-match / false-non-match trade-off on held-out
   LFW data;
3. a controlled 1:N duplicate-profile gallery experiment using real images;
4. cross-pose generalisation from LFW to CPLFW using the *same* frozen
   threshold;
5. an assessment of whether similarity scores are fit only for human review
   rather than automatic account sanctions.

See `docs/RESEARCH_SCOPE.md` for the full scope statement, and
`docs/IMPLEMENTATION_PLAN.md` for the design rationale.

## Datasets required

- **LFW** (Labeled Faces in the Wild) — primary dataset, `pairsDevTrain.txt`
  (calibration), `pairsDevTest.txt` (development validation), `pairs.txt`
  (final evaluation).
- **CPLFW** (Cross-Pose LFW) — secondary dataset, `pairs_CPLFW.txt`
  (cross-pose generalisation, evaluated with the LFW-frozen threshold, no
  separate calibration). CPLFW ships two non-interchangeable image sets —
  the authors' raw, unconstrained images (`images.rar`) and a separately
  pre-cropped/aligned copy (`cp-aligned.zip`) — so every CPLFW command
  requires an explicit `--image-variant {raw,aligned}`; the reported result
  uses `raw`.

Neither dataset is downloaded automatically by anything in this repository.
See `docs/DATASET_PROVENANCE.md` for exact sources and checksums to record,
and `docs/DATA_MANAGEMENT.md` for where to store them: exclusively within
an access-controlled Arden University OneDrive folder, per this project's
ethics form — never inside this repository or a personal cloud service.

**Before downloading or processing any real face image, read
`docs/ETHICS_AND_BIOMETRICS.md`.** Public availability of a dataset does not
by itself satisfy an ethics or data-protection requirement.

## Model acquisition

Two pinned OpenCV Zoo models, never committed to this repository:

```text
face_detection_yunet_2023mar.onnx   (MIT, sha256 8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4)
face_recognition_sface_2021dec.onnx (Apache-2.0, sha256 0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79)
```

Fetch them (e.g. via `git clone --depth 1 https://github.com/opencv/opencv_zoo.git`
and `git lfs pull`, per `docs/MODEL_PROVENANCE.md`) into the directory
pointed to by `FACE_MODEL_ROOT`, then verify:

```bash
python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"
```

## Installation

```bash
python3.11 -m venv .venv   # or the closest available 3.11/3.12/3.13
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,review,report]'   # 'review' pulls in Streamlit for local_review/app.py;
                                                   # 'report' pulls in matplotlib for generate_report_evidence.py;
                                                   # omit either extra if you only need the core pipeline and tests
pytest                      # synthetic-fixture test suite — no dataset needed
```

Copy `.env.example` to `.env` and fill in `FACE_DATA_ROOT`,
`FACE_PROTOCOL_ROOT`, `FACE_MODEL_ROOT` (and, if you use the optional
embedding cache, `FACE_CACHE_ROOT`) with paths inside your access-controlled
Arden University OneDrive research folder — see `docs/DATA_MANAGEMENT.md`.

## Running each experiment

```bash
python scripts/check_environment.py
python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"
python scripts/verify_lfw_dataset.py   --dataset-root "$FACE_DATA_ROOT/lfw_funneled" --protocol-root "$FACE_PROTOCOL_ROOT"
python scripts/verify_cplfw_dataset.py --dataset-root "$FACE_CPLFW_RAW_ROOT"          --protocol-root "$FACE_PROTOCOL_ROOT" --image-variant raw

# Experiment 1 — calibration (pairsDevTrain.txt only)
python scripts/calibrate_lfw.py \
    --dataset-root "$FACE_DATA_ROOT/lfw_funneled" --protocol-root "$FACE_PROTOCOL_ROOT" \
    --model-root "$FACE_MODEL_ROOT" --output results/aggregate/calibrated_threshold.json

# Experiment 2 — development validation (pairsDevTest.txt)
python scripts/evaluate_lfw.py --split dev \
    --dataset-root "$FACE_DATA_ROOT/lfw_funneled" --protocol-root "$FACE_PROTOCOL_ROOT" \
    --model-root "$FACE_MODEL_ROOT" --threshold-artifact results/aggregate/calibrated_threshold.json \
    --output results/aggregate/lfw_development_metrics.json

# Experiment 3 — final LFW evaluation (pairs.txt, frozen threshold)
python scripts/evaluate_lfw.py --split final \
    --dataset-root "$FACE_DATA_ROOT/lfw_funneled" --protocol-root "$FACE_PROTOCOL_ROOT" \
    --model-root "$FACE_MODEL_ROOT" --threshold-artifact results/aggregate/calibrated_threshold.json \
    --output results/aggregate/lfw_final_metrics.json

# Experiment 4 — CPLFW cross-pose generalisation (same frozen threshold)
# $FACE_CPLFW_RAW_ROOT is a flat directory of the authors' raw images,
# produced by extracting images.rar and then flattening it with
# scripts/prepare_cplfw_raw_dataset.py (see docs/DATASET_PROVENANCE.md).
python scripts/evaluate_cplfw.py \
    --dataset-root "$FACE_CPLFW_RAW_ROOT" --protocol-root "$FACE_PROTOCOL_ROOT" \
    --model-root "$FACE_MODEL_ROOT" --image-variant raw \
    --threshold-artifact results/aggregate/calibrated_threshold.json \
    --output results/aggregate/cplfw_metrics.json

# Experiment 5 — real 1:N duplicate-profile gallery
python scripts/create_gallery_manifest.py \
    --dataset-root "$FACE_DATA_ROOT/lfw_funneled" --protocol-root "$FACE_PROTOCOL_ROOT" \
    --output results/raw/gallery_manifest.json
python scripts/evaluate_duplicate_gallery.py \
    --manifest results/raw/gallery_manifest.json --model-root "$FACE_MODEL_ROOT" \
    --threshold-artifact results/aggregate/calibrated_threshold.json \
    --output results/aggregate/duplicate_gallery_metrics.json
```

Or run all of the above (except the optional review UI) with one command:

```bash
python scripts/run_complete_experiment.py \
    --dataset-root "$FACE_DATA_ROOT" --protocol-root "$FACE_PROTOCOL_ROOT" \
    --model-root "$FACE_MODEL_ROOT" --cplfw-dataset-root "$FACE_CPLFW_RAW_ROOT" \
    --cplfw-image-variant raw --output-root results/aggregate
```

It stops with the underlying step's own error message — never a fabricated
result — if any required dataset, protocol, or model file is missing or
invalid. It also refuses to finish if any generated public output ends up
containing a personal/absolute filesystem path (see
`face_verification.privacy.find_path_leaks`).

### Optional: report evidence pack (figures + validation evidence)

The single repeatable command is `./scripts/run_local_mac.sh` (see
`docs/REPRODUCIBILITY.md`), which includes evidence generation as its last
step. To run evidence generation alone:

```bash
python -m pip install -e '.[dev,review,report]'   # adds matplotlib

# Figures only, from the already-generated aggregate results:
python scripts/generate_report_evidence.py \
    --results-root results/aggregate --output-root results/report_evidence

# Additionally run the read-only verification commands and render their
# redacted output as evidence images:
python scripts/generate_report_evidence.py \
    --results-root results/aggregate --output-root results/report_evidence \
    --run-validation \
    --model-root "$FACE_MODEL_ROOT" \
    --lfw-dataset-root "$FACE_DATA_ROOT/lfw_funneled" \
    --cplfw-dataset-root "$FACE_CPLFW_RAW_ROOT" \
    --protocol-root "$FACE_PROTOCOL_ROOT"
```

Generates nine PNG figures, eleven rendered command-evidence images
(including a local-run summary, `screenshot_06_local_complete_run.png`), an
evidence index (`REPORT_EVIDENCE_INDEX.md`), a screenshot-specific index
(`SCREENSHOT_INDEX.md`) and a SHA-256 manifest — all derived only from the
committed `results/aggregate/*` files, never from a raw image or an
identity. Every rendered path is a redacted placeholder, and the generator
fails rather than emit a pack containing a private absolute path. Four
further screenshots (numbered 12-15: Streamlit, institutional storage,
ethics record, GitHub backup) cannot be produced locally and are **not**
fabricated — see `results/report_evidence/manual_screenshots_required.md`.
GitHub Actions is deliberately not among them: see
`docs/REPRODUCIBILITY.md` for why remote CI is not part of this project's
validation design.

### Optional: local review demonstration

```bash
streamlit run local_review/app.py --server.address=127.0.0.1 -- --db results/raw/review.sqlite
```

Localhost only, no login, reads/writes only opaque case identifiers — see
`local_review/app.py`'s module docstring.

## Outputs

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

`run_manifest.json`, the three CSVs, and `FINAL_EVALUATION_REPORT.md` are
written once, at the end, by `scripts/run_complete_experiment.py` — they
summarise/cross-reference the five metrics files above rather than
containing independent numbers, and `run_manifest.json` never contains the
absolute dataset/protocol/model paths, only the environment-variable names
and a SHA-256 of every other output file.

Every field states whether it reflects a real benchmark run (`"status":
"frozen"` / a real score) or is a `"not_run"` placeholder — see
`results/README.md`. **A real evaluation run against LFW and the raw
(`images.rar`) CPLFW image set completed 28 July 2026**, following the
ethics/DPIA gate confirmation recorded in `docs/ETHICS_AND_BIOMETRICS.md`:
99.09% accuracy on the final LFW protocol (EER 0.78%), 90.24% on CPLFW pairs
with a detectable face (though 41.4% of CPLFW pairs failed face *detection*
entirely — the dominant cross-pose finding, present even on the authors'
raw, unconstrained images, not an artefact of pre-cropping — see
`docs/DATASET_PROVENANCE.md`), 96.58% duplicate detection with a 52.56%
false-review rate in the 1:N gallery experiment (evidence that a
1:1-calibrated threshold needs separate calibration for 1:N search). Full
write-up: `results/aggregate/FINAL_EVALUATION_REPORT.md`.

## Limitations

See `docs/THREATS_TO_VALIDITY.md` in full. In brief: LFW/CPLFW's own
demographic skew limits how representative any result here is of a real
dating app's user base; face-extraction failures are excluded from
accuracy metrics (but reported as their own rate, never silently dropped);
the gallery experiment is research-scale, not production-scale; and a
"duplicate profile" here means "same face detected in the gallery," not a
legal or investigative finding about the account holder.

## Ethics warning

Face images and embeddings are biometric data. Read
`docs/ETHICS_AND_BIOMETRICS.md` before downloading, opening with a face
model, or embedding any real dataset image. This project never bans,
suspends or accuses an account — every duplicate-profile result is
evidence for a human reviewer, nothing more.

## Reproducing this without Expo, Clerk or Convex

Nothing in this repository imports from, or requires, the
`AdvancedComputingProjectYes` mobile app or its Clerk/Convex backend. The
only shared context is upstream model provenance (the same pinned YuNet/
SFace files, so results are comparable) — not a code dependency. Every
command above runs from a plain Python virtual environment; see
`docs/REPRODUCIBILITY.md` for the exact pinned versions and how to verify a
re-run used an identical evaluation partition.
