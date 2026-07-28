# Manual screenshots required

These five items cannot be generated locally, and this project will not fabricate them or emit look-alike placeholders. Capture each one yourself and save it into `results/report_evidence/screenshots/` using the filename given below.

> **Do not capture item 1 until a real GitHub Actions run has actually passed for the final commit.** Nothing in this repository asserts that remote CI has passed.

## `manual_01_github_actions_pass.png`

**Title.** GitHub Actions CI run passing for the final commit

**Where to capture.** GitHub → the repository → Actions → the CI workflow run for the final commit

**Must be visible.** The workflow name, a green success tick, the commit SHA, and every job step listed.

**Must be redacted.** Your GitHub username/avatar if you prefer, and any other private repository in the sidebar.

**Report section.** Appendix B — Reproducibility evidence

**Suggested caption.** Continuous integration passing for the submitted commit. CI runs the synthetic-fixture suite only; it never has access to real datasets or model binaries.

## `manual_02_final_github_commit.png`

**Title.** Repository main page at the final commit

**Where to capture.** GitHub → the repository main page

**Must be visible.** Repository name, the final commit message and SHA, and the top-level file listing.

**Must be redacted.** Nothing specific, provided no private repository is visible in the sidebar.

**Report section.** Appendix B — Reproducibility evidence

**Suggested caption.** The public repository at the submitted commit, showing that no dataset, model binary or database file is tracked.

## `manual_03_streamlit_review_interface.png`

**Title.** Local human-review interface

**Where to capture.** A terminal running the Streamlit command in README.md, then the browser at 127.0.0.1

**Must be visible.** The review UI showing opaque case identifiers and the reviewer decision controls.

**Must be redacted.** Nothing — the interface shows only opaque identifiers by design. Confirm no real name or face image is on screen before capturing.

**Report section.** Chapter 5 — Human-review decision policy

**Suggested caption.** The localhost-only review interface. Every case is identified by an opaque one-way hash; a similarity result opens a review case and never an automatic sanction.

## `manual_04_au_onedrive_storage_evidence.png`

**Title.** Institutional storage location

**Where to capture.** The Arden University OneDrive research folder, with folder properties/details visible

**Must be visible.** The folder name, that it is the institutional (not personal) account, and the item count.

**Must be redacted.** Every unrelated personal file and folder name; the full account email if you prefer.

**Report section.** Appendix C — Data governance evidence

**Suggested caption.** Benchmark images, protocols and models held in access-controlled institutional storage, outside the repository and outside any personal cloud service.

## `manual_05_ethics_approval_evidence.png`

**Title.** Ethics approval record

**Where to capture.** The university ethics approval page or approval document — only if disclosure is permitted

**Must be visible.** The approval reference number, the project title, and the approval date.

**Must be redacted.** Reviewer names, signatures, and any personal contact details.

**Report section.** Appendix C — Data governance evidence

**Suggested caption.** Institutional ethics approval covering this evaluation. Capture only if your institution permits reproducing the record in a dissertation appendix.
