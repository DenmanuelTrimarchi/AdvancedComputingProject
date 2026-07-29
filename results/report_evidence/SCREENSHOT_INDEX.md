# Screenshot evidence index

All 15 screenshots, generated (01-11) and manual (12-15), in report order. GitHub Actions is deliberately not among them — see `docs/REPRODUCIBILITY.md` for why remote CI is not part of this project's validation design.

| Order | Filename | Type | Report placement | Status |
|---:|---|---|---|---|
| 01 | `screenshot_01_local_environment_check.png` | Generated | Appendix B — Reproducibility evidence | Captured |
| 02 | `screenshot_02_model_hash_verification.png` | Generated | Appendix B — Reproducibility evidence | Captured |
| 03 | `screenshot_03_lfw_dataset_verification.png` | Generated | Appendix B — Reproducibility evidence | Captured |
| 04 | `screenshot_04_cplfw_raw_dataset_verification.png` | Generated | Appendix B — Reproducibility evidence | Captured |
| 05 | `screenshot_05_local_test_suite_passed.png` | Generated | Appendix B — Reproducibility evidence | Captured |
| 06 | `screenshot_06_local_complete_run.png` | Generated | Appendix B — Reproducibility evidence | Captured |
| 07 | `screenshot_07_threshold_freeze_evidence.png` | Generated | Chapter 3 — Methodology, Threshold selection | Captured |
| 08 | `screenshot_08_cplfw_raw_variant_evidence.png` | Generated | Chapter 3 — Methodology, Datasets | Captured |
| 09 | `screenshot_09_generated_output_inventory.png` | Generated | Appendix B — Reproducibility evidence | Captured |
| 10 | `screenshot_10_public_output_privacy_scan.png` | Generated | Appendix C — Data governance evidence | Captured |
| 11 | `screenshot_11_local_git_state.png` | Generated | Appendix B — Reproducibility evidence | Captured |
| 12 | `screenshot_12_streamlit_human_review_interface.png` | Manual | Chapter 5 — Human-review decision policy | Pending |
| 13 | `screenshot_13_arden_onedrive_storage.png` | Manual | Appendix C — Data governance evidence | Pending |
| 14 | `screenshot_14_ethics_approval.png` | Manual | Appendix C — Data governance evidence | Pending |
| 15 | `screenshot_15_github_backup_final_commit.png` | Manual | Appendix B — Version-control and backup evidence | Pending |

## Detail

### 01 — screenshot_01_local_environment_check.png

- **Title.** Local environment and dependency contract check
- **Purpose / source.** `python scripts/check_environment.py`
- **Suggested caption.** Local macOS execution environment confirming the pinned Python and dependency contract used for the experiment.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 1cdf4ea5c63c56d9909d1e8ca4c33751d634fe82eb98e7d2dbe663103c7cf39c

### 02 — screenshot_02_model_hash_verification.png

- **Title.** Pinned model hash verification
- **Purpose / source.** `python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"`
- **Suggested caption.** YuNet and SFace ONNX files verified against the pinned SHA-256 values before inference.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 27fe2f1c82387ead8b0d376468dc1270e678e8a0e36712a3b01fe2d7e48cafbf

### 03 — screenshot_03_lfw_dataset_verification.png

- **Title.** LFW dataset and protocol verification
- **Purpose / source.** `python scripts/verify_lfw_dataset.py ...`
- **Suggested caption.** Verification that the LFW development and final pair protocols resolved against the configured institutional dataset.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 60f4156a4ebf51906984aa69863c46a0c35e90f4471ae9f1cf8370f090e5dcb8

### 04 — screenshot_04_cplfw_raw_dataset_verification.png

- **Title.** Raw CPLFW dataset and protocol verification
- **Purpose / source.** `python scripts/verify_cplfw_dataset.py ...`
- **Suggested caption.** Verification that all 6,000 raw CPLFW protocol pairs resolved against the authors-distributed image set.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 726e2c509e86c9b0c4276b93d240f3f4a1d9da4cb8135561565c2142b8d5904b

### 05 — screenshot_05_local_test_suite_passed.png

- **Title.** Automated test suite
- **Purpose / source.** `pytest -v`
- **Suggested caption.** The complete synthetic-fixture test suite executed locally on macOS without access to private benchmark images or model binaries.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 8bdc588bb3dca99ab0d474c12247831e4e5e4c5f5831da643f2cd9cccd0fb148

### 06 — screenshot_06_local_complete_run.png

- **Title.** Complete local pipeline run
- **Purpose / source.** `./scripts/run_local_mac.sh`
- **Suggested caption.** Successful end-to-end local execution of the five-experiment pipeline using the institutional OneDrive-backed datasets, protocols and pinned models.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 2774bb033aa29c6ddec5283d58b564fca81e6963d18bd22446140c3270e655ee

### 07 — screenshot_07_threshold_freeze_evidence.png

- **Title.** Threshold freeze provenance
- **Purpose / source.** `(selected fields from results/aggregate/calibrated_threshold.json)`
- **Suggested caption.** Threshold provenance confirming that candidate selection occurred on the development protocol before final LFW and CPLFW evaluation.
- **Report section.** Chapter 3 — Methodology, Threshold selection
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 07968256796b799acfa6b41807d4efa6b70a20acbd34ec60794643c2eeb63d5f

### 08 — screenshot_08_cplfw_raw_variant_evidence.png

- **Title.** CPLFW image-variant provenance
- **Purpose / source.** `(selected fields from results/aggregate/cplfw_metrics.json)`
- **Suggested caption.** Provenance record confirming that the reported CPLFW experiment used the raw, unconstrained image variant rather than the pre-aligned copy.
- **Report section.** Chapter 3 — Methodology, Datasets
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** a4f62c85a4ed5915672e8aa195d0f8eff16992aa8a10dbd792a66aba416dde9e

### 09 — screenshot_09_generated_output_inventory.png

- **Title.** Generated output inventory
- **Purpose / source.** `(inventory of results/aggregate and results/report_evidence)`
- **Suggested caption.** Inventory of the aggregate outputs generated by the complete local experiment.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 54d8543d38ef19edbd7c83ba4345c7964c0cb92a3e101495e6d4b9e51731f6ab

### 10 — screenshot_10_public_output_privacy_scan.png

- **Title.** Public-output privacy scan
- **Purpose / source.** `python scripts/check_public_outputs.py --paths results/aggregate results/report_evidence`
- **Suggested caption.** Privacy validation confirming that public aggregate outputs contain no private path, identity information or biometric image.
- **Report section.** Appendix C — Data governance evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 551db04172c353f9deea25b0a31fb7efb027b0c40d897c4d310ef55617937b56

### 11 — screenshot_11_local_git_state.png

- **Title.** Repository state at generation time
- **Purpose / source.** `git status --short && git log -1 --oneline`
- **Suggested caption.** Local source-control state used to generate the aggregate results and evidence pack.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** e965de977746b1af6e85ce4ad02e5f012e6c8f654c6e9a9575c96a763ff3f499

### 12 — screenshot_12_streamlit_human_review_interface.png

- **Title.** Local human-review interface
- **Purpose / source.** `manual capture`
- **Suggested caption.** Localhost-only review interface showing opaque case identifiers and proportionate reviewer controls; no automatic account sanction is applied.
- **Report section.** Chapter 5 — Human-review decision policy
- **Privacy check.** Not yet checked — verify before committing (see manual_screenshots_required.md).
- **SHA-256.** null (not yet captured)

### 13 — screenshot_13_arden_onedrive_storage.png

- **Title.** Institutional storage location
- **Purpose / source.** `manual capture`
- **Suggested caption.** Datasets, protocols and pinned models stored in the access-controlled Arden University OneDrive research location, outside the Git repository.
- **Report section.** Appendix C — Data governance evidence
- **Privacy check.** Not yet checked — verify before committing (see manual_screenshots_required.md).
- **SHA-256.** null (not yet captured)

### 14 — screenshot_14_ethics_approval.png

- **Title.** Ethics approval record
- **Purpose / source.** `manual capture`
- **Suggested caption.** Institutional ethics approval or recorded authorisation covering the benchmark evaluation.
- **Report section.** Appendix C — Data governance evidence
- **Privacy check.** Not yet checked — verify before committing (see manual_screenshots_required.md).
- **SHA-256.** null (not yet captured)

### 15 — screenshot_15_github_backup_final_commit.png

- **Title.** GitHub backup of the final commit
- **Purpose / source.** `manual capture`
- **Suggested caption.** GitHub repository used as version-controlled backup of the project source code and privacy-reviewed aggregate artefacts; execution was performed locally on macOS.
- **Report section.** Appendix B — Version-control and backup evidence
- **Privacy check.** Not yet checked — verify before committing (see manual_screenshots_required.md).
- **SHA-256.** null (not yet captured)
