# data/

Intentionally empty in Git — the repository root `.gitignore` ignores
everything under `data/` except this file. Real dataset images never belong
here, or anywhere in this repository; they live outside the repo entirely,
at the path set by `FACE_DATA_ROOT` in your local `.env`. See
`.env.example` and `docs/DATA_MANAGEMENT.md`.
