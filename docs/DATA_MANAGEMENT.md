# Data management

## Storage location

**All benchmark images, protocols, derived embeddings, temporary scores and
research databases are stored exclusively within an access-controlled
Arden University OneDrive folder, per this project's ethics form.** They
are not stored in GitHub, personal drives, or personal (non-institutional)
cloud services. Paths are supplied via `.env` (`FACE_DATA_ROOT`,
`FACE_PROTOCOL_ROOT`, `FACE_MODEL_ROOT`, `FACE_CACHE_ROOT`) — see
`.env.example`. A suggested layout inside your AU OneDrive research folder:

```text
<AU OneDrive>/face-verification/
├── datasets/
│   ├── lfw_funneled/
│   └── cplfw/
├── protocols/
│   ├── pairsDevTrain.txt
│   ├── pairsDevTest.txt
│   ├── pairs.txt
│   └── pairs_CPLFW.txt
├── models/
│   ├── face_detection_yunet_2023mar.onnx
│   └── face_recognition_sface_2021dec.onnx
└── cache/
```

This location must **not** be inside this Git repository, a personal
drive, or any personal (non-institutional) cloud service such as Dropbox
or a personal Google Drive/iCloud account — the AU OneDrive research
folder is the one and only approved location per the ethics form.

## What is committed vs. what is not

| Committed to Git | Never committed |
|---|---|
| Source code, tests, docs, configs | Dataset image files and archives |
| `results/aggregate/*.json` / `*.csv` / `*.md` (aggregate, anonymised) | `results/raw/`, `results/pair_scores/` (per-sample detail) |
| Placeholder provenance tables | Filled-in checksums that would need updating per download (fine to fill in locally, just don't forget they're for your own record — this file has no image data either way) |
| — | Model `.onnx` binaries |
| — | The embedding cache, if ever enabled |
| — | `.env` (only `.env.example` is committed) |

`.gitignore` enforces the dataset/model/cache exclusions mechanically, not
just by convention.

## Embedding cache

Disabled by default (`FACE_CACHE_ROOT` unset ⇒ no caching). If explicitly
enabled for a long-running batch job:

- the cache directory must be created with restrictive permissions
  (owner-only read/write);
- it must be documented, wherever it's referenced, as containing biometric
  templates — a normalised face embedding is still a biometric
  identifier, even though it cannot be inverted back into an image;
- it must live under `FACE_CACHE_ROOT`, which is itself outside the
  repository and gitignored.

## Retention and deletion

Real dataset copies and any generated cache should be deleted once the
dissertation experiments and any required re-runs are complete, per your
institution's data retention policy. Record the planned and actual deletion
dates in `docs/DATASET_PROVENANCE.md`.

## What leaves this machine

Nothing dataset-related is uploaded anywhere *by this codebase*. There is
no network call in the evaluation pipeline itself
(`src/face_verification/`) — models and datasets are read only from the
local, OneDrive-synced folder set via `.env`. Any transfer of real
biometric data to Arden University OneDrive itself happens through
OneDrive's own institutional sync client, under the university's own
access controls, not through any code in this repository — this
repository never uploads anything on its own. The only network activity
this codebase itself performs is the one-time, manual download of the two
public OpenCV Zoo model files (never real face images), documented in
`docs/MODEL_PROVENANCE.md`.
