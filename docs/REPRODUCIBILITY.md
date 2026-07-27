# Reproducibility

## What is pinned

- Python interpreter version (recorded per run by
  `scripts/check_environment.py`, embedded in every result artifact under
  `software_environment`).
- `numpy==2.5.1`, `opencv-python-headless==4.13.0.92`, `Pillow==12.3.0` —
  enforced at runtime, not just declared in `pyproject.toml`
  (`provenance.check_dependency_contract(strict=True)` raises if the
  installed versions drift).
- Both model files, by SHA-256 (`docs/MODEL_PROVENANCE.md`).
- Detector settings, embedding dimensionality, and the exact preprocessing
  sequence (`config.PREPROCESSING_REVISION`).
- The random seed used for gallery manifest construction
  (`config.DEFAULT_RANDOM_SEED`, overridable via `--seed`, always recorded
  in the manifest and in `duplicate_gallery_metrics.json`).

Any change to any of the above is a new evaluation partition — see
`docs/MODEL_PROVENANCE.md`'s change-control note.

## Steps to reproduce a full run

```bash
python3.11 -m venv .venv          # or the closest available 3.11/3.12/3.13
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,review,report]'
pytest                             # synthetic-fixture test suite; no dataset needed

python scripts/check_environment.py
python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"
python scripts/verify_lfw_dataset.py --dataset-root "$FACE_DATA_ROOT/lfw_funneled" --protocol-root "$FACE_PROTOCOL_ROOT"
python scripts/verify_cplfw_dataset.py --dataset-root "$FACE_CPLFW_RAW_ROOT" --protocol-root "$FACE_PROTOCOL_ROOT"

python scripts/run_complete_experiment.py \
    --dataset-root "$FACE_DATA_ROOT" \
    --protocol-root "$FACE_PROTOCOL_ROOT" \
    --model-root "$FACE_MODEL_ROOT" \
    --cplfw-dataset-root "$FACE_CPLFW_RAW_ROOT" \
    --cplfw-image-variant raw \
    --output-root results/aggregate

python scripts/generate_report_figures.py \
    --results-root results/aggregate \
    --output-root results/figures
```

`$FACE_CPLFW_RAW_ROOT` is a flat directory of the CPLFW authors' raw,
unconstrained images (extracted from `images.rar`, then flattened with
`scripts/prepare_cplfw_raw_images.py` — CPLFW's own extraction nests every
image one level down alongside per-image landmark files). It is deliberately
a separate path from `$FACE_DATA_ROOT/cplfw`, which — if populated at
all — would hold the separately pre-cropped/aligned `cp-aligned.zip` copy
instead; the two are non-interchangeable evaluation inputs, never
interchangeable, hence the explicit `--cplfw-image-variant` on every command
that touches CPLFW. See `docs/DATASET_PROVENANCE.md`.

Every step above stops with a specific error rather than proceeding on
missing or invalid input — there is no code path that fabricates a result
when a dataset, protocol, or model file is absent.

## What is *not* pinned, and why that's fine

- Operating-system/processor identity is recorded (`platform.platform()`,
  `platform.processor()`) but not enforced — OpenCV's YuNet/SFace ONNX
  inference is deterministic given identical inputs and library versions
  regardless of host OS, to within ordinary floating-point tolerance.
- Wall-clock timing figures (embedding time, gallery-search time) will vary
  by machine; only the accuracy-relevant outputs (similarity scores,
  metrics) are treated as reproducible.

## Verifying a re-run matches a prior one

Because `results/aggregate/*.json` embeds the model SHA-256 values,
dependency versions, preprocessing revision, and (for the gallery) the
random seed, two runs can be compared field-by-field to confirm they used
an identical evaluation partition before comparing their metric values.
