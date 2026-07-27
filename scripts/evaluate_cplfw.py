#!/usr/bin/env python3
"""Experiment 4: cross-pose generalisation. Evaluates the exact frozen
LFW-calibrated threshold on CPLFW — deliberately no separate CPLFW
calibration step.

Requires an explicit ``--image-variant {raw,aligned}`` — CPLFW ships two
non-interchangeable image sets (the authors' raw, unconstrained images in
``images.rar``, and a separately pre-cropped/aligned copy in
``cp-aligned.zip``) and the result must never be ambiguous about which one
was scored.

Usage:
    python scripts/evaluate_cplfw.py \
        --dataset-root /path/to/private-storage/cplfw_raw \
        --protocol-root /path/to/private-storage/protocols \
        --model-root /path/to/private-storage/models \
        --image-variant raw \
        --threshold-artifact results/aggregate/calibrated_threshold.json \
        --output results/aggregate/cplfw_metrics.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from face_verification.artifacts import read_json_artifact, write_json_artifact
from face_verification.calibration import require_frozen_threshold
from face_verification.config import (
    CPLFW_IMAGE_VARIANTS,
    MODEL_VERSION,
    PREPROCESSING_REVISION,
    SFACE_FILENAME,
    SFACE_SHA256,
    YUNET_FILENAME,
    YUNET_SHA256,
    cplfw_provenance_fields,
)
from face_verification.detector import YuNetDetector
from face_verification.embedder import SFaceEmbedder
from face_verification.protocols import parse_cplfw_pairs
from face_verification.provenance import sha256_of_evaluated_image_set, sha256_of_file, software_environment_report
from face_verification.verification_evaluator import evaluate_pairs, summarize_metrics

PROTOCOL_FILENAME = "pairs_CPLFW.txt"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument(
        "--image-variant", required=True, choices=CPLFW_IMAGE_VARIANTS,
        help="Which CPLFW image set --dataset-root points at: the authors' raw "
             "images (images.rar) or the separately pre-cropped/aligned copy "
             "(cp-aligned.zip). Recorded verbatim in the output so the result "
             "can never be ambiguous about which variant was scored.",
    )
    parser.add_argument("--threshold-artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    provenance_fields = cplfw_provenance_fields(args.image_variant)

    protocol_path = args.protocol_root / PROTOCOL_FILENAME
    threshold_artifact_sha256 = sha256_of_file(args.threshold_artifact)
    threshold_payload = read_json_artifact(args.threshold_artifact)
    threshold = require_frozen_threshold(threshold_payload, context=str(args.threshold_artifact))

    pairs = parse_cplfw_pairs(protocol_path, args.dataset_root)
    evaluated_images = {p.left_path for p in pairs} | {p.right_path for p in pairs}

    detector = YuNetDetector(args.model_root / YUNET_FILENAME, YUNET_SHA256)
    embedder = SFaceEmbedder(args.model_root / SFACE_FILENAME, SFACE_SHA256)

    result = evaluate_pairs(pairs, detector=detector, embedder=embedder)
    summary = summarize_metrics(result, threshold)

    payload = {
        "artifact_type": "cplfw_verification_metrics",
        **provenance_fields,
        "protocol_file": PROTOCOL_FILENAME,
        "protocol_sha256": sha256_of_file(protocol_path),
        "evaluated_image_set_sha256": sha256_of_evaluated_image_set(evaluated_images, args.dataset_root),
        "threshold_source": str(args.threshold_artifact),
        "threshold_artifact_sha256": threshold_artifact_sha256,
        "threshold_status": threshold_payload.get("status"),
        "note": (
            "Frozen threshold calibrated on LFW pairsDevTrain.txt and selected on "
            "pairsDevTest.txt; not recalibrated for CPLFW. This measures cross-pose "
            "generalisation, not a separately-tuned CPLFW-specific result."
        ),
        **summary,
        "model_version": MODEL_VERSION,
        "preprocessing_revision": PREPROCESSING_REVISION,
        "model_sha256": {"yunet": detector.model_sha256, "sface": embedder.model_sha256},
        "software_environment": software_environment_report(),
    }
    write_json_artifact(args.output, payload)
    print(f"Wrote CPLFW metrics to {args.output} (accuracy={summary['accuracy']:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
