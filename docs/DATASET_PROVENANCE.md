# Dataset provenance

Status: **acquired and checksum-verified for LFW; acquired for CPLFW (no
official checksum published by the authors to check against).** Fields
still marked `TBC` require an institutional reference this document cannot
supply on its own — see `docs/ETHICS_AND_BIOMETRICS.md`.

## LFW (Labeled Faces in the Wild)

| Field | Value |
|---|---|
| Official source | `http://vis-www.cs.umass.edu/lfw/` |
| Archive filename | `lfwfunneled.tgz` |
| Archive MD5 | `1b42dfed7d15c9b2dd63d5e5840c86ad` — matches the official/Torchvision-documented value |
| Protocol files | `pairsDevTrain.txt`, `pairsDevTest.txt`, `pairs.txt` |
| Protocol file MD5s | `pairsDevTrain.txt` = `4f27cbf15b2da4a85c1907eb4181ad21`; `pairsDevTest.txt` = `5132f7440eb68cf58910c8a45a2ac10b`; `pairs.txt` = `9f1ba174e4e1c508ff7cdf10ac338a7d` — all match the official/Torchvision-documented values |
| Download date | 27 July 2026 (file timestamps on receipt; original download date by the researcher TBC) |
| Downloaded by | researcher (name TBC) |
| Terms reviewed | LFW's stated research-only terms — TBC formal confirmation |
| Ethics/approval reference | TBC — see `docs/ETHICS_AND_BIOMETRICS.md` |
| Local storage location | Arden University OneDrive research folder, per `.env` `FACE_DATA_ROOT` / `FACE_PROTOCOL_ROOT` (see docs/DATA_MANAGEMENT.md) |
| Planned deletion date | TBC — set per your institution's retention policy |

If the official server is unavailable, a Kaggle mirror (`jessicali9530/lfw-dataset`)
may be used instead — record the mirror URL, licence statement, and download
date in the same table format, and prefer the funneled image variant
consistently (do not mix original/funneled/deep-funneled images in one run).

## CPLFW (Cross-Pose LFW)

| Field | Value |
|---|---|
| Official source | `https://www.whdeng.cn/CPLFW/index.html` |
| Archive filename | `CPLFW.zip` |
| Archive SHA-256 | `9a09dd1ebe1a000c52f69f365f5d564cd529f1fcf4f0479510231856f358f416` — no official checksum is published by the authors to verify against; recorded for this project's own reproducibility only |
| Protocol file | `pairs_CPLFW.txt` (the authors' updated list; format confirmed directly against the real file — see `src/face_verification/protocols.py`) |
| Download date | 27 July 2026 (file timestamps on receipt; original download date by the researcher TBC) |
| Downloaded by | researcher (name TBC) |
| Terms reviewed | TBC formal confirmation |
| Ethics/approval reference | TBC — see `docs/ETHICS_AND_BIOMETRICS.md` |
| Local storage location | Arden University OneDrive research folder, per `.env` `FACE_DATA_ROOT` / `FACE_PROTOCOL_ROOT` (see docs/DATA_MANAGEMENT.md) |
| Planned deletion date | TBC |

Note: the archive also contained `images.rar`, which this environment could
not extract (no `unrar`/`unar`/`7z` available); the evaluation instead used
the bundled pre-aligned `cp-aligned.zip` image set (11,651 of ~11,652 files
extracted successfully — one filename with non-ASCII characters failed to
extract but is not referenced by any pair in `pairs_CPLFW.txt`, confirmed by
direct search).

Do not substitute a Kaggle re-upload of unknown licence when the authors'
official source is reachable.

## Rules that apply to both datasets

- Never download automatically from an unverified mirror.
- Never scrape a dating website or collect private user images for this
  project.
- Never commit dataset archives, extracted images, protocol files, or any
  per-sample identity information to Git — see `.gitignore`.
- `scripts/verify_lfw_dataset.py` / `scripts/verify_cplfw_dataset.py` confirm
  structural integrity (every protocol-referenced image exists, pair counts
  match the header) but do not themselves verify archive checksums — do that
  once, by hand, at download time, and record it in this file.
