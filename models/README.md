# models/

Intentionally empty in Git (`.gitignore` excludes `models/*.onnx` and
`*.bin`). The two pinned OpenCV Zoo model files
(`face_detection_yunet_2023mar.onnx`, `face_recognition_sface_2021dec.onnx`)
must be provisioned manually into the location pointed to by
`FACE_MODEL_ROOT` in your `.env` — see `docs/MODEL_PROVENANCE.md` for exact
hashes and upstream sources, and run `scripts/verify_models.py` to confirm
they match before running any experiment.

Nothing in this repository downloads a model file automatically at runtime.
