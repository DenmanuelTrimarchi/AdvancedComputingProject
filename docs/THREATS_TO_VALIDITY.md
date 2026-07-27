# Threats to validity

## Internal validity

- **Partition leakage.** Mitigated in code (`calibration.calibrate` rejects
  non-validation splits; the gallery excludes calibration images) and
  tested directly (`tests/test_no_partition_leakage.py`), but a human
  operator could still misuse the CLI (e.g. pointing `--protocol-root` at a
  directory where `pairsDevTrain.txt` and `pairs.txt` are accidentally
  identical files). The scripts cannot detect a corrupted *dataset*, only
  enforce which *script* is allowed to touch which *split name*.
- **Face-extraction failures are excluded from score-based metrics.** A
  pair where either image fails detection contributes to the reported
  failure rate but not to accuracy/EER/AUC. If failures correlate with
  identity, pose, or image quality in a non-random way, the reported
  accuracy is conditioned on "images the detector could process," not all
  images in the protocol.
- **Single detector confidence operating point.** YuNet's own
  score/NMS thresholds (0.9 / 0.3) are fixed constants, not calibrated
  per-experiment; a different detector operating point could change which
  images are ruled zero/multiple-face before embedding is ever attempted.

## External validity

- **LFW's own demographic skew** is well documented in the literature
  (predominantly public figures, skewed in age/ethnicity/gender relative to
  the general population); results here should not be read as representative
  of accuracy on a real dating app's user base.
- **CPLFW measures pose difficulty specifically**, not the full range of
  real-world capture conditions (lighting, camera quality, compression,
  occlusion, expression) a mobile selfie-verification flow would encounter.
- **The gallery experiment's size is bounded by how many LFW identities have
  ≥2 usable images** after calibration exclusions — a research-scale
  gallery, not a production-scale one. Duplicate-detection and false-review
  rates at, say, 100,000 registered profiles are not established by this
  experiment.

## Construct validity

- **"Duplicate profile" here means "same face detected in the gallery,"**
  not "same person operating both accounts" in any legal or investigative
  sense, and not "fraudulent account." The gallery experiment cannot
  distinguish a legitimate second account (e.g. a public figure, a person
  who deleted and re-registered) from misuse.
- **A high similarity score is evidence for a human reviewer, not a
  verdict.** This project does not, and cannot from this experimental
  design alone, establish an acceptable false-positive rate for any
  particular production deployment decision.

## Statistical validity

- Metrics on `pairsDevTest.txt` (1,000 pairs) and the calibration split
  (2,200 pairs) have wider confidence intervals than the 6,000-pair final
  LFW protocol; report all three pair counts alongside any accuracy figure,
  not the number alone.
- The gallery experiment's identity pool size directly bounds statistical
  power for the duplicate-detection and false-review rates; report the
  actual gallery/probe counts (`results/aggregate/duplicate_gallery_metrics.json`)
  alongside the rates.

## What would need to change to strengthen these results

A held-out set drawn from the actual target population (e.g. anonymised,
consented mobile selfie pairs, subject to a fresh ethics/DPIA review), a
demographic-subgroup breakdown of the LFW/CPLFW results (not attempted here
— see `docs/ETHICS_AND_BIOMETRICS.md` on why this project does not infer
demographic attributes merely to produce subgroup numbers), and a
substantially larger gallery experiment before any claim about production
duplicate-detection performance.
