# Model provenance

Status: pinned upstream release identified and hash-verified against this
repository's manifest; the actual accuracy of the pipeline built from these
models on real data is a separate, not-yet-populated question — see
`docs/EVALUATION_PROTOCOL.md`.

## Pinned models

| Role | Filename | Upstream source | Licence | Expected SHA-256 |
|---|---|---|---|---|
| Face detection | `face_detection_yunet_2023mar.onnx` | `github.com/opencv/opencv_zoo` | MIT | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| Face embedding | `face_recognition_sface_2021dec.onnx` | `github.com/opencv/opencv_zoo` | Apache-2.0 | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` |

These hashes are recorded verbatim in `src/face_verification/config.py` and
re-checked by every entry point that loads a model
(`provenance.verify_model_file`) — a file that fails the hash check is
refused before any inference is attempted, not silently loaded.

## Runtime contract

The evaluation partition is the exact combination of:

- both model files, identified by SHA-256 (above);
- detector settings: score threshold 0.9, NMS threshold 0.3, top-k 5000,
  network input size fixed at 320×320 per frame;
- fixed embedding dimensionality: 128;
- preprocessing revision `opencv-yunet-sface-exif-bgr-l2-v1` (EXIF
  orientation normalisation → RGB → BGR → YuNet detect → SFace alignCrop →
  SFace feature → L2 normalise);
- pinned dependency versions: `numpy==2.5.1`, `opencv-python-headless==4.13.0.92`,
  `Pillow==12.3.0` (enforced at runtime by
  `provenance.check_dependency_contract`).

Changing any one of these creates a new evaluation partition: a threshold
calibrated under one contract must never be applied under another, and any
such change requires a fresh calibration and, per `docs/ETHICS_AND_BIOMETRICS.md`,
a fresh review before processing real faces again.

## What this does and does not establish

YuNet + SFace provide similarity evidence only. Nothing in this repository:

- performs liveness or presentation-attack detection;
- identifies a legal person or infers their intent;
- detects a scammer;
- guarantees that two similar-looking faces belong to the same person.

Any accuracy threshold published in OpenCV's own examples or documentation
is **not** this project's threshold — see `docs/EVALUATION_PROTOCOL.md` for
how this project's own threshold must be derived, from validation data only.

## Acquisition record

_To be completed at the time the model files are actually downloaded by a
human operator for a given run:_ upstream release/tag referenced, download
date, person who downloaded them, licence text location, confirmed checksum
match, and OpenCV version used to load them. Until this section is filled
in for a specific run, treat any result produced by that run as unverified
regarding exact model provenance, even if the SHA-256 checks above passed
(the checks confirm the file matches the pin; this section additionally
records who fetched it, from where, and when).
