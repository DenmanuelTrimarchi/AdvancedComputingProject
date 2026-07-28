# Dataset provenance

Status: **acquired and checksum-verified for LFW; acquired and
raw-protocol-verified for CPLFW (no official archive checksum is published
by the authors to check against, so the SHA-256 values below are recorded
for this project's own reproducibility only, not compared against an
upstream-published value).** This document last verified 28 July 2026.
Fields still marked `TBC` require an institutional reference this document
cannot supply on its own — see `docs/ETHICS_AND_BIOMETRICS.md` and
`docs/USER_ACTIONS_REQUIRED.md`.

## LFW (Labeled Faces in the Wild)

| Field | Value |
|---|---|
| Official source | `http://vis-www.cs.umass.edu/lfw/` |
| Archive filename | `lfwfunneled.tgz` |
| Archive MD5 | `1b42dfed7d15c9b2dd63d5e5840c86ad` — matches the official/Torchvision-documented value |
| Protocol files | `pairsDevTrain.txt`, `pairsDevTest.txt`, `pairs.txt` |
| Protocol file MD5s | `pairsDevTrain.txt` = `4f27cbf15b2da4a85c1907eb4181ad21`; `pairsDevTest.txt` = `5132f7440eb68cf58910c8a45a2ac10b`; `pairs.txt` = `9f1ba174e4e1c508ff7cdf10ac338a7d` — all match the official/Torchvision-documented values |
| Download date | 27 July 2026 (file timestamps on receipt; original download date by the researcher TBC) |
| Downloaded by | Domingo Enmanuel Trimarchi (researcher) |
| Terms reviewed | LFW's stated research-only terms — TBC formal confirmation |
| Ethics/approval reference | TBC — see `docs/ETHICS_AND_BIOMETRICS.md` |
| Local storage location | private, access-controlled local research storage, outside this repository and outside any personal cloud service — **not yet confirmed to be the Arden University OneDrive location this project's data-management policy requires; see `docs/USER_ACTIONS_REQUIRED.md`** |
| Planned deletion date | TBC — set per your institution's retention policy |

If the official server is unavailable, a Kaggle mirror (`jessicali9530/lfw-dataset`)
may be used instead — record the mirror URL, licence statement, and download
date in the same table format, and prefer the funneled image variant
consistently (do not mix original/funneled/deep-funneled images in one run).

## CPLFW (Cross-Pose LFW)

| Field | Value |
|---|---|
| Official source | `https://www.whdeng.cn/CPLFW/index.html` |
| Container archive | `CPLFW.zip` (SHA-256 `9a09dd1ebe1a000c52f69f365f5d564cd529f1fcf4f0479510231856f358f416` — no official checksum is published by the authors to verify against; recorded for this project's own reproducibility only). Nests two distinct, non-interchangeable image sets plus the protocol file. |
| Raw image archive (**used for the reported result**) | `images.rar`, SHA-256 `7baca61dda21341eaa642f229eedfbba1d0aaa2d22447d79e158920106831165` — the authors' raw, unconstrained images, 250×250 px |
| Aligned image archive (superseded, see note below) | `cp-aligned.zip`, SHA-256 `420adcc13f1ab9510d8f99af04dbfb1695645ff73942c2a1010c5c01fd8367e2` — a separately pre-cropped/aligned copy, 224×224 px |
| Protocol file | `pairs_CPLFW.txt` (the authors' updated list; SHA-256 `f1da25fbbfa5ab076734a92293efe6df4be61f38513c4c56f5848b39b60658e6`; format confirmed directly against the real file — see `src/face_verification/protocols.py`) |
| Raw extraction result | `images.rar` extracted successfully with `unar` 1.10.8 into a nested `correct_points/` directory (images alongside per-image landmark `.txt` files), then flattened with `scripts/prepare_cplfw_raw_dataset.py`: 11,652 image files, 0 filename collisions |
| Protocol verification (raw) | `scripts/verify_cplfw_dataset.py` against the flattened raw directory: **6,000 / 6,000 pairs parsed (3,000 matched, 3,000 mismatched), every referenced image resolved, no malformed rows** |
| Download date | 27 July 2026 (file timestamps on receipt; original download date by the researcher TBC) |
| Downloaded by | Domingo Enmanuel Trimarchi (researcher) |
| Terms reviewed | TBC formal confirmation |
| Ethics/approval reference | TBC — see `docs/ETHICS_AND_BIOMETRICS.md` |
| Local storage location | private, access-controlled local research storage, outside this repository and outside any personal cloud service — **not yet confirmed to be the Arden University OneDrive location this project's data-management policy requires; see `docs/USER_ACTIONS_REQUIRED.md`** |
| Planned deletion date | TBC |

**History.** An earlier evaluation reported in this repository used
`cp-aligned.zip` because this environment could not extract `images.rar` (no
`unrar`/`unar`/`7z` available at the time) — the earlier CPLFW result was
therefore scored against pre-cropped 224×224 faces, not the authors' raw
distribution, and its unusually high face-detection failure rate (54.4%,
dominated by zero-face detections) is consistent with feeding a face
detector images that are already tightly cropped with no surrounding
margin. **The final reported experiment was rerun using the raw
authors-distributed `images.rar` image set on 28 July 2026**, after `unar`
was installed and the raw extraction verified against all 6,000
`pairs_CPLFW.txt` pairs (see the row above). The aligned dataset was not
deleted — it is retained at a clearly marked private backup location,
untouched, in case a future comparison between variants is wanted.

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
