# Code attribution register

This register identifies only code materially adapted from external sources.
Original project code based on standard programming logic is not listed.

## Outcome of the review

Every tracked source and configuration file in this repository was reviewed
for externally adapted code. **No file was found to contain code copied or
materially adapted from an external source**, so no source-attribution header
was added to any file.

The repository depends on external libraries (OpenCV, NumPy, Pillow,
Streamlit, Matplotlib) and on two external pretrained model files, but calling
a documented public API is not adaptation of that library's source code. The
model files themselves are external artefacts rather than code; their origin,
licences and SHA-256 digests are recorded separately in
`docs/MODEL_PROVENANCE.md`.

## Reviewed areas

The table lists only areas a reviewer could reasonably question on provenance
grounds. Every one was confirmed to be original project code.

| Repository file | Code area | External source | Adaptation status | Licence checked |
|---|---|---|---|---|
| `src/face_verification/detector.py` | `YuNetDetector` wrapper around `cv2.FaceDetectorYN` | None — uses OpenCV's documented public API only | Original | Not applicable |
| `src/face_verification/embedder.py` | `SFaceEmbedder` wrapper around `cv2.FaceRecognizerSF` | None — uses OpenCV's documented public API only | Original | Not applicable |
| `src/face_verification/similarity.py` | `l2_normalize`, `cosine_similarity` | None — standard vector algebra written independently | Original | Not applicable |
| `src/face_verification/metrics.py` | `roc_auc` rank-based implementation | None — the Mann-Whitney U rank identity is a standard statistical result, implemented here without reference to another codebase | Original | Not applicable |
| `src/face_verification/metrics.py` | `equal_error_rate`, `roc_points`, `confusion_matrix` | None — standard definitions implemented independently, deliberately avoiding a scikit-learn dependency | Original | Not applicable |
| `src/face_verification/protocols.py` | LFW and CPLFW pair-file parsing | None — the *file formats* are defined by the dataset authors and are documented in `docs/DATASET_PROVENANCE.md`; the parser is original | Original | Not applicable |
| `src/face_verification/image_io.py` | Bounded loading and EXIF orientation handling | None — uses Pillow's documented `ImageOps.exif_transpose` API; the bounds and failure taxonomy are project-specific | Original | Not applicable |
| `scripts/generate_report_evidence.py` | Matplotlib figure and terminal-rendering code | None — bespoke figure construction for this project's evidence pack | Original | Not applicable |
| `local_review/app.py` | Streamlit review page | None — standard Streamlit widgets composed for this project | Original | Not applicable |

## Model files (not code)

The two pretrained ONNX models are external inputs, not source code, and are
never committed to this repository. They are fully documented in
`docs/MODEL_PROVENANCE.md`, which records for each file the upstream location
(`github.com/opencv/opencv_zoo`), the licence (MIT for YuNet, Apache-2.0 for
SFace) and the pinned SHA-256 digest that `src/face_verification/provenance.py`
verifies at load time.

## Datasets (not code)

LFW and CPLFW are external datasets used under their published terms. Their
provenance, access conditions and verification evidence are recorded in
`docs/DATASET_PROVENANCE.md`. No dataset file is committed to this repository.

## Maintenance rule

If code is later adapted from an external source, add a header immediately
above the adapted block:

```python
##############
# Title: Short title of the adapted code or method
# Author: Author name, organisation or project
# Date: Year or full date where known
# Availability: Stable URL, DOI or repository location
##############
```

and add a matching row to the table above. `scripts/check_comment_style.py`
enforces that any such header carries all four fields and a stable
`Availability` location. Do not add a header where the origin cannot be
verified; record the uncertainty instead and raise it for review.
