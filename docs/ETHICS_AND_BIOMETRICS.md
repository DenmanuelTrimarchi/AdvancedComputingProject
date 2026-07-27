# Ethics and biometrics

Status: **approval gate confirmed open by the researcher on 27 July 2026 —
real-face processing (LFW, CPLFW) authorised for this evaluation.** The
ten-item checklist below was confirmed by the researcher at that time;
specific institutional references (DPIA document ID, ethics approval
number, named data controller) should still be filled in below for the
dissertation's methods/appendix section.

| Item | Status |
|---|---|
| Named data controller | _placeholder — record name/role_ |
| Signed DPIA | _placeholder — record reference, if required by your institution_ |
| Lawful basis / Article 9 condition | _placeholder — record which condition applies_ |
| University ethics approval | _placeholder — record approval/reference number_ |
| LFW/CPLFW licence terms reviewed | confirmed by researcher, 27 July 2026 |
| Model provenance recorded | see `docs/MODEL_PROVENANCE.md` — hashes verified |
| Access-controlled storage | see `docs/DATA_MANAGEMENT.md` — external, non-repo location |
| Retention period defined | _placeholder — record in `docs/DATASET_PROVENANCE.md`_ |
| Thresholds preregistered before held-out use | enforced in code, see `docs/EVALUATION_PROTOCOL.md` |
| Incident/withdrawal procedure | _placeholder — record contact and process_ |

## Core statements

- Face images and the embeddings derived from them are biometric research
  data. A 128-value SFace embedding cannot be inverted back into a
  photograph, but it remains a biometric identifier capable of matching a
  person across images, and should be handled with the same care as the
  source photograph.
- **Public availability of a dataset does not automatically authorise every
  use of it.** LFW and CPLFW being downloadable does not by itself satisfy
  a university's ethics or data-protection requirements for processing
  biometric data.
- No real dataset image should be downloaded, opened with a face model, or
  embedded until:
  1. a named data controller is identified for this project;
  2. a signed Data Protection Impact Assessment (DPIA) exists, if required
     by your institution for this class of processing;
  3. a GDPR (or applicable) lawful basis and, where biometric data is
     "special category" data, an Article 9 condition are documented;
  4. university ethics approval covering this specific evaluation has been
     obtained;
  5. the LFW and CPLFW licence/terms of use have been read and confirmed
     compatible with this use;
  6. model provenance has been recorded per `docs/MODEL_PROVENANCE.md`;
  7. storage is access-controlled per `docs/DATA_MANAGEMENT.md`;
  8. a retention period is defined and recorded in `docs/DATASET_PROVENANCE.md`;
  9. operating thresholds are preregistered before being read from held-out
     data (see `docs/EVALUATION_PROTOCOL.md`);
  10. an incident/withdrawal procedure exists for this project (who to
      contact, and what happens to already-processed data, if a problem is
      found).
- **Until all ten conditions above are satisfied, only deterministic
  synthetic vectors and opaque fake identities may be used.** The automated
  test suite under `tests/` does exactly this and nothing more.

## No participants, no new collection

This is a benchmark-evaluation study, not a user study. No participants are
recruited. No new photograph of any person is captured or requested by this
codebase. No dataset image is ever uploaded to a cloud service — the
pipeline in `src/face_verification/` performs all inference from local
files, with no network calls.

## No investigation of real people

Nothing in this repository attempts to identify, contact, locate, or
investigate any person depicted in LFW, CPLFW, or any other image. The
duplicate-profile gallery experiment (`docs/EVALUATION_PROTOCOL.md`,
Experiment 5) reports aggregate rates over opaque, one-way identity hashes
(`src/face_verification/privacy.opaque_id`) — never a real name — and its
findings are read as evidence about the *pipeline's* behaviour, not as a
claim about any specific depicted person.

## No inferred demographic attributes

No demographic attribute (age, ethnicity, gender presentation, or similar)
is inferred from any image merely to produce a subgroup breakdown. LFW and
CPLFW's own documented demographic composition is cited, where relevant, as
a *limitation* of external validity (`docs/THREATS_TO_VALIDITY.md`), not
recreated as a new labelled attribute by this project's own code.

## No fairness or production-readiness claim

Aggregate accuracy, false-match and false-non-match figures produced by
this pipeline must not be represented as proof of fairness across
subgroups, nor as evidence the system is ready for production use on a real
user base. See `docs/THREATS_TO_VALIDITY.md` for the specific gaps between
this benchmark evaluation and a production deployment decision.
