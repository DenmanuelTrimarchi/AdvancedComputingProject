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
| **Storage migration to Arden University OneDrive** | **Outstanding** | No Arden University OneDrive folder was found under `~/Library/CloudStorage` on this machine as of 28 July 2026 (only a personal Google Drive folder was present). The dataset/model verification and evaluation runs recorded in this repository used a private, access-controlled local directory instead — outside the repository and outside any personal cloud-sync service, but not the institutionally-mandated location. Locate or provision the Arden OneDrive research folder, copy (do not move) the private datasets/protocols/models/cache into it, verify file counts and checksums after the copy, update the (gitignored, never-committed) local `.env` to point `FACE_DATA_ROOT` / `FACE_PROTOCOL_ROOT` / `FACE_MODEL_ROOT` at the new location, and re-run `scripts/run_complete_experiment.py` from there. Do not delete the original local files until the OneDrive copy is verified. |

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
- Claim GitHub Actions passed remotely unless a real remote run is visible
  (see `.github/workflows/ci.yml` and `docs/REPRODUCIBILITY.md`).
- Describe the Arden University OneDrive migration as complete before it
  is verified.
