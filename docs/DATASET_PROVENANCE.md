# Dataset provenance

Status: **placeholders only — no dataset has been acquired through this
document yet.** Fill in every field below at the time each dataset is
actually downloaded, before it is processed, and keep this file itself out
of any location that would expose acquisition details unnecessarily (it
contains no image data, so it is safe to commit — the datasets themselves
never are).

## LFW (Labeled Faces in the Wild)

| Field | Value |
|---|---|
| Official source | `http://vis-www.cs.umass.edu/lfw/` |
| Archive filename | `lfw-funneled.tgz` |
| Archive SHA-256 / MD5 | _placeholder — record on download_ |
| Protocol files | `pairsDevTrain.txt`, `pairsDevTest.txt`, `pairs.txt` |
| Protocol file checksums | _placeholder — record on download_ |
| Download date | _placeholder_ |
| Downloaded by | _placeholder_ |
| Terms reviewed | _placeholder — confirm the dataset's stated research-only terms_ |
| Ethics/approval reference | _placeholder — see docs/ETHICS_AND_BIOMETRICS.md_ |
| Local storage location | outside this repository, per `.env` `FACE_DATA_ROOT` / `FACE_PROTOCOL_ROOT` |
| Planned deletion date | _placeholder — set per your institution's retention policy_ |

If the official server is unavailable, a Kaggle mirror (`jessicali9530/lfw-dataset`)
may be used instead — record the mirror URL, licence statement, and download
date in the same table format, and prefer the funneled image variant
consistently (do not mix original/funneled/deep-funneled images in one run).

## CPLFW (Cross-Pose LFW)

| Field | Value |
|---|---|
| Official source | `https://www.whdeng.cn/CPLFW/index.html` |
| Archive filename | _placeholder — record on download_ |
| Archive SHA-256 | _placeholder — record on download_ |
| Protocol file | `pairs_CPLFW.txt` (use the authors' September 2018 updated list) |
| Protocol file checksum | _placeholder — record on download_ |
| Download date | _placeholder_ |
| Downloaded by | _placeholder_ |
| Terms reviewed | _placeholder_ |
| Ethics/approval reference | _placeholder_ |
| Local storage location | outside this repository, per `.env` `FACE_DATA_ROOT` / `FACE_PROTOCOL_ROOT` |
| Planned deletion date | _placeholder_ |

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
