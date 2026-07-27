# Implementation plan

Date: 27 July 2026

## Why this repository exists

The supervisor rejected a broadly simulated system based on artificial
profiles, synthetic images, mock reports and simulated security scenarios,
and asked for validation on real public benchmark datasets. Rather than
retrofitting real-data evaluation onto the existing dating-app repository
(`AdvancedComputingProjectYes`), this is a **new, standalone research
repository** with no dependency on Expo, Clerk, Convex, React Native or the
existing app. It contains only what is needed to answer the research
question with real data.

## Research framing

**Title:** Design and Evaluation of a Face-Verification and Duplicate-Profile
Detection Proof of Concept Using Real-World Benchmark Datasets

**Research question:** How effectively can a pretrained face-embedding model
verify whether two unconstrained facial images belong to the same person and
identify potential duplicate profiles under a human-review decision policy?

**Contribution:** not a new face-recognition model and not a dating
application. The contribution is a reproducible empirical evaluation of a
fixed, pinned face-verification pipeline (OpenCV YuNet + SFace) on real
benchmark data: validation-only threshold calibration, false-match/false-non
-match analysis on held-out data, a controlled 1:N duplicate-profile gallery
experiment, and cross-pose generalisation (LFW → CPLFW) — concluding with an
assessment of whether similarity scores are fit only for human review rather
than automatic account sanctions.

## Assumptions

- Real dataset files (LFW funneled images, CPLFW images, both protocol files)
  will be supplied manually by the user at paths outside this repository, via
  `FACE_DATA_ROOT` / `FACE_PROTOCOL_ROOT`. This repository never downloads
  dataset image archives automatically.
- The two OpenCV Zoo model files are treated differently from datasets: they
  are public pretrained model weights (no depicted-person biometric data
  attached to the *file itself* the way a face photograph is), so they may be
  fetched directly from the upstream OpenCV Zoo source and hash-verified, the
  same way the sister project already does. They are supplied via
  `FACE_MODEL_ROOT`.
- Real face images are only ever processed once the user has confirmed the
  ethics/data-protection review described in `docs/ETHICS_AND_BIOMETRICS.md`
  is satisfied for their institution. Nothing in this repository performs
  that review automatically or bypasses it.
- Python 3.13 (already installed on this machine) is used rather than 3.11/3.12,
  since the pinned dependency versions (numpy 2.5.1, opencv-python-headless
  4.13.0.92, Pillow 12.3.0 — the same pins already validated against Python
  3.13 in the sister project's face-service) install and run correctly on it.
  The actual interpreter and package versions in use are recorded by
  `scripts/check_environment.py` and embedded in every result artifact rather
  than silently assumed.
- No API server, database service, or authentication layer is required. The
  primary artefact is a set of local Python CLI scripts plus an optional,
  login-free, localhost-only Streamlit page for manually reviewing gallery
  cases.

## Dataset and model files expected

| Variable | Expected contents |
|---|---|
| `FACE_DATA_ROOT` | `lfw_funneled/<name>/<name>_<0001>.jpg` directory tree; `cplfw/` image directory |
| `FACE_PROTOCOL_ROOT` | `pairsDevTrain.txt`, `pairsDevTest.txt`, `pairs.txt` (official LFW format), `pairs_CPLFW.txt` (authors' updated format) |
| `FACE_MODEL_ROOT` | `face_detection_yunet_2023mar.onnx`, `face_recognition_sface_2021dec.onnx` |
| `FACE_CACHE_ROOT` | optional, disabled by default; embedding cache only |

No dataset or model file is committed to Git (see `.gitignore`). `scripts/verify_*`
scripts fail loudly, with a specific error, rather than silently proceeding
when any of the above is missing or fails a checksum.

## Validation / held-out boundary

This is the single most important methodological guarantee in the codebase,
enforced in code (`src/face_verification/calibration.py`,
`src/face_verification/artifacts.py`) and tested directly
(`tests/test_no_partition_leakage.py`), not just documented:

1. **Calibration** (`scripts/calibrate_lfw.py`) reads only `pairsDevTrain.txt`.
   The resulting threshold artifact records the SHA-256 of the exact pair file
   and image set used, and is tagged `split: "validation"`.
2. **Development validation** (`scripts/evaluate_lfw.py --split dev`) reads
   only `pairsDevTest.txt` and evaluates the calibrated candidate thresholds
   without changing them. One threshold is then frozen using a documented,
   non-interactive rule (maximum balanced accuracy on the dev split, ties
   broken by lower EER).
3. **Final evaluation** (`scripts/evaluate_lfw.py --split final` and
   `scripts/evaluate_cplfw.py`) reads only `pairs.txt` / `pairs_CPLFW.txt` and
   the already-frozen threshold artifact. Any attempt to pass a threshold
   artifact not tagged `frozen` or to recompute thresholds during this stage
   raises an error rather than silently proceeding.
4. **Gallery experiment** (`scripts/create_gallery_manifest.py`,
   `scripts/evaluate_duplicate_gallery.py`) explicitly excludes any image that
   appears in the calibration pair file, and enforces that no image occupies
   more than one manifest role (gallery / duplicate probe / unknown probe).

## Confirmation: no code from AdvancedComputingProjectYes is required

This repository does not import, vendor, or depend on any file from
`AdvancedComputingProjectYes`. The two projects only share upstream public
model provenance (same YuNet/SFace files, same pinned OpenCV/NumPy/Pillow
versions) — a deliberate choice so results are comparable, not a code
dependency. `AdvancedComputingProjectYes` remains a separate, possible future
integration target and is not touched by anything in this repository.

## Staged build order actually followed

1. Repository scaffold, licence, packaging, `.gitignore`, this plan.
2. Core library: `config`, `image_io`, `detector`, `embedder`, `similarity`,
   `protocols`, `metrics` — the mathematical/IO layer with no CLI attached.
3. Supporting infrastructure: `calibration`, `artifacts`, `provenance`,
   `privacy`.
4. Orchestration: `verification_evaluator`, `gallery_evaluator`.
5. CLI scripts as thin wrappers around the library.
6. Test suite (synthetic fixtures only — no real dataset needed to run `pytest`).
7. Remaining docs and YAML configs.
8. Optional local review Streamlit page.
9. Full test run to green; model files fetched and hash-verified (datasets
   deliberately left for the user to supply and approve per the ethics gate).
10. Git history and, once locally verified, a private GitHub repository.
