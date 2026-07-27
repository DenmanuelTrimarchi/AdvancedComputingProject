# Research scope

## Why this exists

The supervisor rejected an earlier proposal for relying on artificial
profiles, synthetic images, mock reports and simulated security scenarios,
and required validation on real public benchmark datasets, with a narrower
scope than a full dating application. This repository is the response: a
standalone research artefact, evaluated only on real face-verification
benchmarks.

## Title

Design and Evaluation of a Face-Verification and Duplicate-Profile Detection
Proof of Concept Using Real-World Benchmark Datasets

## Research question

How effectively can a pretrained face-embedding model verify whether two
unconstrained facial images belong to the same person and identify potential
duplicate profiles under a human-review decision policy?

## Research contribution

Not a new face-recognition model, and not a dating application. The
contribution is:

1. a reproducible evaluation of a fixed pretrained face-verification
   pipeline (OpenCV YuNet + SFace) on real-world benchmark datasets;
2. validation-only calibration of face-similarity operating thresholds;
3. measurement of the false-match / false-non-match trade-off on held-out
   data;
4. a controlled 1:N duplicate-profile gallery experiment using real images;
5. an analysis of whether similarity scores are suitable only for human
   review rather than automatic account sanctions;
6. a comparison of ordinary unconstrained verification performance with
   cross-pose performance (LFW vs CPLFW).

## In scope

- Local Python CLI scripts that detect a face, embed it, compare embeddings,
  calibrate a threshold on a validation split, and evaluate that frozen
  threshold on held-out LFW and CPLFW data.
- A real 1:N duplicate-profile gallery experiment built from real LFW images.
- An optional, login-free, localhost-only Streamlit page for manually
  reviewing anonymised gallery cases from a local SQLite database.
- Unit tests of the pipeline's logic, using synthetic fixture data.

## Explicitly out of scope

Not implemented anywhere in this repository:

- Expo, React Native, Clerk, Convex, Next.js, or any cloud storage/auth
  service.
- A dating application: matching, swiping, messaging, reports, bans, scam
  classification.
- Liveness detection or facial age estimation.
- A production moderator system.
- Model training or fine-tuning — only a fixed, pinned, pretrained pipeline
  is evaluated.
- Automatic scraping of dating websites or collection of private user
  images.

`AdvancedComputingProjectYes` (the separate dating-app repository) remains a
possible future integration target for these findings, but nothing here
depends on it, and this research does not require reproducing it.
