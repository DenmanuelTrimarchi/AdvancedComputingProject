#!/usr/bin/env python3
"""Experiment 5: run the real 1:N duplicate-profile gallery experiment from
a manifest built by create_gallery_manifest.py.

Never calls a detected duplicate a scammer and never bans, rejects or
accuses any identity — it only reports rates. By default this reuses the
calibrated threshold artifact's own operating threshold as the
duplicate-review threshold; pass --threshold-strategy to use a different
named candidate from that same artifact (e.g. a stricter target-FMR
candidate) instead.

Usage:
    python scripts/evaluate_duplicate_gallery.py \
        --manifest results/raw/gallery_manifest.json \
        --model-root /secure/path/models \
        --threshold-artifact results/aggregate/calibrated_threshold.json \
        --output results/aggregate/duplicate_gallery_metrics.json \
        --review-db results/raw/review.sqlite   # optional: also populate local_review/app.py's database
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from face_verification.artifacts import read_json_artifact, write_json_artifact
from face_verification.calibration import require_frozen_threshold
from face_verification.config import (
    MODEL_VERSION,
    PREPROCESSING_REVISION,
    SFACE_FILENAME,
    SFACE_SHA256,
    YUNET_FILENAME,
    YUNET_SHA256,
)
from face_verification.detector import YuNetDetector
from face_verification.embedder import SFaceEmbedder
from face_verification.gallery_evaluator import (
    GalleryManifest,
    ManifestEntry,
    evaluate_gallery,
    summarize_gallery_metrics,
)
from face_verification.provenance import software_environment_report


def _load_manifest(path: Path) -> GalleryManifest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = [
        ManifestEntry(entry["sample_id"], entry["identity_hash"], Path(entry["image_path"]), entry["role"])
        for entry in payload["entries"]
    ]
    return GalleryManifest(entries=entries, seed=payload["seed"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--threshold-artifact", required=True, type=Path)
    parser.add_argument("--threshold-strategy", default=None,
                         help="Named candidate from the artifact's 'candidates' map to use as the "
                              "duplicate-review threshold, instead of the artifact's default operating threshold.")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--review-db", type=Path, default=None,
                         help="If set, write every probe exceeding the duplicate-review threshold "
                              "into this local SQLite database, for local_review/app.py to display.")
    args = parser.parse_args(argv)

    manifest = _load_manifest(args.manifest)
    threshold_payload = read_json_artifact(args.threshold_artifact)

    if args.threshold_strategy:
        if threshold_payload.get("status") != "frozen":
            raise SystemExit(f"Threshold artifact status is not 'frozen': {args.threshold_artifact}")
        candidates = threshold_payload.get("candidates", {})
        if args.threshold_strategy not in candidates:
            raise SystemExit(
                f"Unknown threshold strategy '{args.threshold_strategy}'; available: {sorted(candidates)}"
            )
        threshold = float(candidates[args.threshold_strategy]["threshold"])
    else:
        threshold = require_frozen_threshold(threshold_payload, context=str(args.threshold_artifact))

    detector = YuNetDetector(args.model_root / YUNET_FILENAME, YUNET_SHA256)
    embedder = SFaceEmbedder(args.model_root / SFACE_FILENAME, SFACE_SHA256)

    result = evaluate_gallery(manifest, detector=detector, embedder=embedder, duplicate_review_threshold=threshold)
    summary = summarize_gallery_metrics(result)

    payload = {
        "artifact_type": "duplicate_gallery_metrics",
        "duplicate_review_threshold": threshold,
        "threshold_source": str(args.threshold_artifact),
        "threshold_strategy": args.threshold_strategy or threshold_payload.get("operating_strategy"),
        "seed": manifest.seed,
        "policy_note": (
            "A result above threshold opens a case for human review only. It is not evidence "
            "of scam activity and does not ban, reject or accuse any identity."
        ),
        **summary,
        "model_version": MODEL_VERSION,
        "preprocessing_revision": PREPROCESSING_REVISION,
        "model_sha256": {"yunet": detector.model_sha256, "sface": embedder.model_sha256},
        "software_environment": software_environment_report(),
    }
    write_json_artifact(args.output, payload)
    print(
        f"Wrote duplicate gallery metrics to {args.output} "
        f"(duplicate_detection_rate={summary['duplicate_detection_rate']:.4f})"
    )

    if args.review_db:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "local_review"))
        from database import connect, upsert_case  # noqa: E402

        flagged = [p for p in result.probe_results if p.exceeds_duplicate_threshold]
        with connect(args.review_db) as connection:
            for probe in flagged:
                upsert_case(
                    connection,
                    case_id=f"{probe.sample_id}:{probe.top_candidate_identity_hash}",
                    probe_sample_id=probe.sample_id,
                    candidate_identity_hash=probe.top_candidate_identity_hash,
                    similarity=probe.top_similarity,
                    threshold=threshold,
                )
        print(f"Wrote {len(flagged)} review case(s) to {args.review_db}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
