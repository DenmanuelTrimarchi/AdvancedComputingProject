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
- **SHA-256.** 0cbfa103aa297176c25c727669e2f2f54e904b90b7f535964ffe2ae529052205

### 02 — screenshot_02_model_hash_verification.png

- **Title.** Pinned model hash verification
- **Purpose / source.** `python scripts/verify_models.py --model-root "$FACE_MODEL_ROOT"`
- **Suggested caption.** YuNet and SFace ONNX files verified against the pinned SHA-256 values before inference.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** b1970a4b18ba9841fabf4bd73e6e01ff708be443d93b9942d5c7d83e9de00667

### 03 — screenshot_03_lfw_dataset_verification.png

- **Title.** LFW dataset and protocol verification
- **Purpose / source.** `python scripts/verify_lfw_dataset.py --dataset-root "$FACE_DATA_ROOT/lfw_funneled" --protocol-root "$FACE_PROTOCOL_ROOT"`
- **Suggested caption.** Verification that the LFW development and final pair protocols resolved against the configured institutional dataset.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** e473bd9e463c86256010672d5d355c99bdb7acd4d847852cf830e25ba7d67b1a

### 04 — screenshot_04_cplfw_raw_dataset_verification.png

- **Title.** Raw CPLFW dataset and protocol verification
- **Purpose / source.** `python scripts/verify_cplfw_dataset.py --dataset-root "$CPLFW_RAW_ROOT" --protocol-root "$FACE_PROTOCOL_ROOT" --image-variant raw`
- **Suggested caption.** Verification that all 6,000 raw CPLFW protocol pairs resolved against the authors-distributed image set.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 4aea984b6cdc650cf0b92753d9a084592ce468e920925cd8951b1a6039809522

### 05 — screenshot_05_local_test_suite_passed.png

- **Title.** Automated test suite
- **Purpose / source.** `pytest -v`
- **Suggested caption.** The complete synthetic-fixture test suite executed locally on macOS without access to private benchmark images or model binaries.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 07bd3ed52c93dbbbd2a8c2ef92e87ca67a6b104dbe172ab3f0de5e132e883db5

### 06 — screenshot_06_local_complete_run.png

- **Title.** Complete local pipeline run
- **Purpose / source.** `./scripts/run_local_mac.sh`
- **Suggested caption.** Successful end-to-end local execution of the five-experiment pipeline using the institutional OneDrive-backed datasets, protocols and pinned models.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** b5348d80ce27ff2a85c0b8774f10ffcdf8a1d0fbaf6e08c214c38e892cd1bf58

### 07 — screenshot_07_threshold_freeze_evidence.png

- **Title.** Threshold freeze provenance
- **Purpose / source.** `(selected fields from results/aggregate/calibrated_threshold.json)`
- **Suggested caption.** Threshold provenance confirming that candidate selection occurred on the development protocol before final LFW and CPLFW evaluation.
- **Report section.** Chapter 3 — Methodology, Threshold selection
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 62cbf73bd0a428fffc14a866865a028ad20f952263b0b832c7034343517b02ce

### 08 — screenshot_08_cplfw_raw_variant_evidence.png

- **Title.** CPLFW image-variant provenance
- **Purpose / source.** `(selected fields from results/aggregate/cplfw_metrics.json)`
- **Suggested caption.** Provenance record confirming that the reported CPLFW experiment used the raw, unconstrained image variant rather than the pre-aligned copy.
- **Report section.** Chapter 3 — Methodology, Datasets
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 8f5ffa581c9110f6fa083686d58f0c4c173a1402d5ea7b1c55523685594eb2f7

### 09 — screenshot_09_generated_output_inventory.png

- **Title.** Generated output inventory
- **Purpose / source.** `(inventory of results/aggregate and results/report_evidence)`
- **Suggested caption.** Inventory of the aggregate outputs generated by the complete local experiment.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** f57e662eaf105edfb756fa1747e3dad0495e92f3365dcf2f4b3f824b5d35f9a3

### 10 — screenshot_10_public_output_privacy_scan.png

- **Title.** Public-output privacy scan
- **Purpose / source.** `python scripts/check_public_outputs.py --paths results/aggregate results/report_evidence`
- **Suggested caption.** Privacy validation confirming that public aggregate outputs contain no private path, identity information or biometric image.
- **Report section.** Appendix C — Data governance evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 19f9d81b1754c3afa0bc5533cbf9aaaeb6b8e38bf76041d0f58d732c780c9af2

### 11 — screenshot_11_local_git_state.png

- **Title.** Repository state at generation time
- **Purpose / source.** `git status --short && git log -1 --oneline`
- **Suggested caption.** Local source-control state used to generate the aggregate results and evidence pack.
- **Report section.** Appendix B — Reproducibility evidence
- **Privacy check.** Confirmed: contains_real_face_image, contains_identity_information and contains_absolute_path are all false in the manifest.
- **SHA-256.** 406b50d9b8256f694285dfe3b5c04f255943f6b6adb97727d14a84c6ac90d25c

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
