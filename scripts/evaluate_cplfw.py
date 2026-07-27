#!/usr/bin/env python3
"""Experiment 4: cross-pose generalisation. Evaluates the exact frozen
LFW-calibrated threshold on CPLFW — deliberately no separate CPLFW
calibration step.

Usage:
    python scripts/evaluate_cplfw.py \
        --dataset-root /secure/path/datasets/cplfw \
        --protocol-root /secure/path/protocols \
        --model-root /secure/path/models \
        --threshold-artifact results/aggregate/calibrated_threshold.json \
        --output results/aggregate/cplfw_metrics.json
"""

from __future__ import annotations

import argparse
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
from face_verification.protocols import parse_cplfw_pairs
from face_verification.provenance import software_environment_report
from face_verification.verification_evaluator import evaluate_pairs, summarize_metrics

PROTOCOL_FILENAME = "pairs_CPLFW.txt"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--threshold-artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    threshold_payload = read_json_artifact(args.threshold_artifact)
    threshold = require_frozen_threshold(threshold_payload, context=str(args.threshold_artifact))

    pairs = parse_cplfw_pairs(args.protocol_root / PROTOCOL_FILENAME, args.dataset_root)

    detector = YuNetDetector(args.model_root / YUNET_FILENAME, YUNET_SHA256)
    embedder = SFaceEmbedder(args.model_root / SFACE_FILENAME, SFACE_SHA256)

    result = evaluate_pairs(pairs, detector=detector, embedder=embedder)
    summary = summarize_metrics(result, threshold)

    payload = {
        "artifact_type": "cplfw_verification_metrics",
        "protocol_file": PROTOCOL_FILENAME,
        "threshold_source": str(args.threshold_artifact),
        "threshold_status": threshold_payload.get("status"),
        "note": (
            "Frozen threshold calibrated on LFW pairsDevTrain.txt; not recalibrated for "
            "CPLFW. This measures cross-pose generalisation, not a separately-tuned "
            "CPLFW-specific result."
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
