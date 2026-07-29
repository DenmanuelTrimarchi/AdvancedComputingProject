# Manual screenshots required

These four items cannot be generated locally, and this project will not fabricate them or emit look-alike placeholders. Capture each one yourself and save it into `results/report_evidence/screenshots/` using the filename given below.

GitHub Actions is not part of this list: validation is performed locally on macOS (see `scripts/run_local_mac.sh` and `docs/REPRODUCIBILITY.md`), and GitHub is used only as version-controlled backup — screenshot_15 below evidences that backup, not a remote CI pass.

## `screenshot_12_streamlit_human_review_interface.png`

**Title.** Local human-review interface

**Where to capture.** A terminal running `streamlit run local_review/app.py --server.address=127.0.0.1 -- --db results/raw/review.sqlite`, then the browser at 127.0.0.1

**Must be visible.** The review UI showing opaque case identifiers and the reviewer decision controls.

**Must be redacted.** Nothing should need redacting — the interface shows only opaque identifiers by design. Confirm before capturing that no real face image, no real name and no private path is on screen; if any is, stop and report it as a defect rather than cropping it out.

**Report section.** Chapter 5 — Human-review decision policy

**Suggested caption.** Localhost-only review interface showing opaque case identifiers and proportionate reviewer controls; no automatic account sanction is applied.

## `screenshot_13_arden_onedrive_storage.png`

**Title.** Institutional storage location

**Where to capture.** The Arden University OneDrive research folder, navigated to the project's own subfolder (not the OneDrive account root) — the migration is complete and verified, see docs/USER_ACTIONS_REQUIRED.md for the checksum/file-count record

**Must be visible.** The university-controlled OneDrive identity/location; the project subfolder; and the high-level folder structure (datasets/, protocols/, models/, optionally cache/).

**Must be redacted.** Face-image thumbnails; participant or identity names; unrelated university or personal files; absolute local paths containing your account name. Navigate *into* the project subfolder before capturing rather than screenshotting the OneDrive account root — an institutional OneDrive root commonly also holds unrelated personal documents (coursework, assignments, or similar) that must never appear in a committed screenshot. Switch the file browser out of any thumbnail/preview mode first.

**Report section.** Appendix C — Data governance evidence

**Suggested caption.** Datasets, protocols and pinned models stored in the access-controlled Arden University OneDrive research location, outside the Git repository.

## `screenshot_14_ethics_approval.png`

**Title.** Ethics approval record

**Where to capture.** The university ethics approval page or approval document — **only if your institution permits reproducing it** in a dissertation appendix

**Must be visible.** The institution; the approval status; the project title or reference; and the approval date/reference number.

**Must be redacted.** Reviewer names and signatures; personal contact details; any personal data not needed to evidence the approval itself.

**Report section.** Appendix C — Data governance evidence

**Suggested caption.** Institutional ethics approval or recorded authorisation covering the benchmark evaluation.

## `screenshot_15_github_backup_final_commit.png`

**Title.** GitHub backup of the final commit

**Where to capture.** GitHub → AdvancedComputingProject → the repository main page, on branch `main`

**Must be visible.** The repository name; that the branch is `main`; the final commit message and short SHA; and the source file listing.

**Must be redacted.** The Actions tab; billing information; private email addresses; unrelated repositories in the sidebar. GitHub is version-controlled backup evidence here, not an execution-passing claim — do not include an Actions screenshot.

**Report section.** Appendix B — Version-control and backup evidence

**Suggested caption.** GitHub repository used as version-controlled backup of the project source code and privacy-reviewed aggregate artefacts; execution was performed locally on macOS.
