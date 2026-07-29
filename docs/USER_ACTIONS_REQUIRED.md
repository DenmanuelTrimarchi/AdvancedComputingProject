# Actions required from the researcher

This document tracks every institutional/administrative item this
repository cannot supply on its own — no code change or documentation
rewrite can fill these in; they require you (and, where noted, your
institution) to confirm a fact. See `docs/ETHICS_AND_BIOMETRICS.md` for why
each item exists and `docs/DATASET_PROVENANCE.md` for the dataset facts
that *are* already recorded.

None of the items below are described elsewhere in this repository as
complete. Treat every "TBC" as genuinely outstanding.

| Item | Status | Notes |
|---|---|---|
| Named data controller | **TBC** | Record name/role. |
| University ethics approval reference | **TBC** | Record the approval/reference number issued for this specific evaluation. |
| Signed DPIA (Data Protection Impact Assessment) | **TBC** | Record the reference, or confirm in writing that your institution does not require one for this class of processing. |
| GDPR (or applicable) lawful basis | **TBC** | Record which Article 6 basis applies. |
| Article 9 condition (special-category/biometric data) | **TBC** | Record which condition applies. |
| Retention period | **TBC** | Record in `docs/DATASET_PROVENANCE.md` once defined. |
| Planned deletion date | **TBC** | Record in `docs/DATASET_PROVENANCE.md` once defined. |
| Incident/data-breach reporting contact | **TBC** | Record who to contact and what happens to already-processed data if a problem is found. |
| LFW licence/terms of use — formal confirmation | **TBC** | `docs/DATASET_PROVENANCE.md` records the researcher's informal confirmation (27 July 2026); a formal sign-off is still outstanding. |
| CPLFW licence/terms of use — formal confirmation | **TBC** | Same as above. |
| Original LFW/CPLFW acquisition date | **partially TBC** | Only the file-timestamp-on-receipt date (27 July 2026) is recoverable from local evidence; the researcher's actual original download date, if different, should be recorded by hand. |
| **Storage migration to Arden University OneDrive** | **Outstanding — reverted (29 July 2026)** | The migration was completed and checksum-verified on 29 July 2026 (24,902 files, all matching), but the OneDrive-backed files subsequently proved operationally unreliable: macOS's Files-On-Demand feature dehydrated them to cloud-only placeholders, and neither a direct file read nor a Finder-level materialisation attempt could force a re-download (`fileproviderctl evaluate` showed `isUploaded: 1` / `isDownloaded: 0`; the Finder attempt failed with a genuine OneDrive error, `-15266`). A `fileproviderctl dump` showed the account's sync engine backlogged with unrelated pending operations. The researcher directed reverting storage to a private, `.gitignore`-excluded subdirectory of the project's own working directory (`datasets/`) — this is **not** the ethics-form-mandated Arden OneDrive location, and does not resolve this requirement. It is, however, isolated from Git: nothing under `datasets/` is or has ever been tracked (`git ls-files datasets/` is empty). Re-attempt the OneDrive migration once its sync reliability is resolved, or obtain and record explicit institutional confirmation that local gitignored storage is an acceptable interim/permanent location under the ethics approval. See `docs/DATA_MANAGEMENT.md` and `docs/DATASET_PROVENANCE.md`. |

## Fill-in block

Copy this block, complete it from your real institutional records, and paste
it back here. Anything left as `TBC` is a **submission blocker**, not a
completed item — it is reported as outstanding everywhere it appears.

```text
Named data controller:                  TBC
University ethics approval/reference:   TBC
DPIA reference or exemption confirmation: TBC
Article 6 lawful basis:                 TBC
Article 9 condition:                    TBC
Retention period:                       TBC
Planned deletion date:                  TBC
Incident contact:                       TBC
Incident procedure:                     TBC
LFW terms formally reviewed by/date:    TBC
CPLFW terms formally reviewed by/date:  TBC
Original dataset acquisition date:      TBC
```

Two of these have partial local evidence already, and should be *confirmed*
rather than researched from scratch:

- **Original dataset acquisition date** — file timestamps on receipt give
  27 July 2026. If you downloaded the archives earlier, that earlier date is
  the correct one and only you can supply it.
- **LFW/CPLFW terms reviewed** — `docs/DATASET_PROVENANCE.md` records your
  informal confirmation on 27 July 2026; what remains is a formal sign-off
  with a name and date.

## What this project will never do instead of you completing this list

- Invent an ethics approval number, DPIA reference, lawful basis, Article 9
  condition, retention date, or incident contact.
- Describe the Arden University OneDrive migration as complete before it
  is verified.
- Require, or claim, a remote GitHub Actions run. Validation is performed
  locally on macOS (see `scripts/run_local_mac.sh` and
  `docs/REPRODUCIBILITY.md`) because the private benchmark data and model
  binaries are intentionally never available to GitHub; the former CI
  workflow is retained only as an inactive reference at
  `docs/archive/github_actions_ci_reference.yml`. GitHub itself is used
  only as version-controlled backup of source code and privacy-reviewed
  aggregate evidence — a remote run is not a submission blocker.
