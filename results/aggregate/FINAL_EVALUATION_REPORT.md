# Final evaluation report

Real-data evaluation of the pinned OpenCV YuNet + SFace pipeline
(`model_version: opencv-sface-2021dec-yunet-2023mar`; hashes as recorded in
`docs/MODEL_PROVENANCE.md`) against real LFW and CPLFW benchmark data, run
27 July 2026 following the ethics/DPIA gate confirmation recorded in
`docs/ETHICS_AND_BIOMETRICS.md`. Every number below is machine-readable in
the corresponding `results/aggregate/*.json` file, each of which embeds its
own software/model provenance (`software_environment`, `model_sha256`,
`preprocessing_revision`) so it can be checked independently of this prose
summary.

## Experiment 1 — threshold calibration (LFW `pairsDevTrain.txt`, validation split, 2,200 pairs)

Scored 1,972 / 2,200 pairs (89.6%); 228 pairs (10.4%) failed face
extraction — 203 from multiple detected faces, 25 from zero detected faces.
Operating strategy `balanced_accuracy` froze the threshold at
**0.363012** (this happened to coincide exactly with the `target_fmr_0.001`
candidate at this sample). On the calibration data itself: accuracy 99.54%,
FMR 0.0%, FNMR 0.91% — not held-out evidence, reported here only for
completeness; see Experiments 2–3 for the actual validation/final numbers.

## Experiment 2 — LFW development validation (`pairsDevTest.txt`, 1,000 pairs)

Scored 896 / 1,000 (89.6%). Accuracy **99.22%**, precision 100%, recall
98.42%, F1 99.20%, ROC-AUC 99.66%, EER 1.36%.

## Experiment 3 — final LFW evaluation (`pairs.txt`, 6,000 pairs, frozen threshold, untouched protocol)

Scored 5,399 / 6,000 (90.0%). **Accuracy 99.09%**, precision 99.89%, recall
98.29%, F1 99.08%, false match rate 0.11%, false non-match rate 1.71%,
ROC-AUC 99.75%, EER 0.78%. Confusion matrix: TP 2,649, FP 3, TN 2,701,
FN 46. This is the headline LFW verification result, produced entirely
from a threshold frozen on a disjoint validation split.

## Experiment 4 — CPLFW cross-pose generalisation (`pairs_CPLFW.txt`, 6,000 pairs, same frozen threshold, no recalibration)

Scored only 2,737 / 6,000 (45.6%) — **54.4% of pairs failed face
extraction**, and overwhelmingly (3,129 of 3,263 failures) because YuNet
detected *zero* faces rather than detecting too many. This is the headline
generalisation finding: under CPLFW's deliberately large pose variation,
the **detector**, not the embedding/verification step, is the primary
bottleneck. On the pairs that did produce a score: accuracy 93.86%,
precision 97.58%, recall 89.36%, F1 93.29%, FMR 2.03%, FNMR 10.64%, ROC-AUC
96.93%, EER 7.04% — a real accuracy drop from LFW, on top of, not instead
of, the detection-failure rate above.

## Experiment 5 — real 1:N duplicate-profile gallery (LFW, seed 20260727)

Gallery: 986 successfully embedded identities (from 1,047 manifest
entries; 61 extraction failures). 1,047 duplicate probes (995 scored, 52
failures). 3,080 unknown probes (2,913 scored, 167 failures).

- Duplicate detection rate: **96.58%**
- Rank-1 identification rate: 92.76%
- True duplicate miss rate: 3.42%
- **False duplicate-review rate: 52.56%**

The false-review rate is the most important number in this experiment, not
a defect in it. It comes from reusing the 1:1 ownership-verification
threshold (calibrated for comparing exactly *two* images) as the 1:N
duplicate-review threshold. A ~0.11% single-comparison false-match rate
(Experiment 3) compounds across ~986 gallery comparisons per probe, so more
than half of entirely legitimate, non-duplicate profiles end up flagged for
review at this threshold. This is a direct, quantified demonstration —
exactly what this project's research question asked for — that a
1:1-calibrated threshold is not fit for 1:N search at this gallery scale,
and that a separately calibrated, more conservative gallery threshold (or a
two-stage decision policy) would be required before any real deployment.
It is also direct evidence *for* the project's design decision that a
similarity score above threshold opens a human-review case rather than an
automatic sanction (`docs/DECISIONS.md`-equivalent policy in
`docs/EVALUATION_PROTOCOL.md`): at this threshold, treating "duplicate
review" as "confirmed duplicate" would be wrong more often than not.

## Headline takeaways

1. On ordinary unconstrained LFW verification, the pipeline performs very
   well (99.09% accuracy, EER 0.78%), in line with SFace's published
   academic performance.
2. Accuracy is measured only over pairs with a detectable face in both
   images; face-extraction failure is itself non-trivial (10.4% on LFW,
   54.4% on CPLFW) and is reported as its own rate precisely so it is never
   mistaken for, or hidden inside, the accuracy figure.
3. Cross-pose robustness is substantially weaker than ordinary LFW
   performance, and the dominant cause is *detection* failure, not
   embedding/verification failure — a specific, actionable finding rather
   than a generic "accuracy went down."
4. A threshold suitable for 1:1 ownership verification is not suitable for
   1:N duplicate-profile search without its own calibration — evidenced
   directly by the 52.56% false-review rate.

## Limitations

See `docs/THREATS_TO_VALIDITY.md` in full. In particular: these figures
describe LFW/CPLFW's own demographic composition, not a dating app's real
user base; the gallery experiment (986 identities) is research-scale, not
production-scale; and "duplicate profile" here means "same face detected in
the gallery," not a legal or investigative finding.
