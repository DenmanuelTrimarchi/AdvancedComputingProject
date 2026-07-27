#!/usr/bin/env python3
"""Experiment 1: calibrate verification thresholds using LFW pairsDevTrain.txt only.

Never reads pairsDevTest.txt or pairs.txt. Writes one artifact containing
every candidate strategy's threshold plus the single selected operating
threshold, tagged "frozen" so later scripts refuse to recalibrate it.

Usage:
    python scripts/calibrate_lfw.py \
        --dataset-root /secure/path/datasets/lfw_funneled \
        --protocol-root /secure/path/protocols \
        --model-root /secure/path/models \
        --output results/aggregate/calibrated_threshold.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from face_verification.artifacts import write_json_artifact
from face_verification.calibration import calibrate
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
from face_verification.protocols import parse_lfw_pairs
from face_verification.provenance import software_environment_report
from face_verification.verification_evaluator import evaluate_pairs

PROTOCOL_FILENAME = "pairsDevTrain.txt"
STRATEGY_CHOICES = [
    "balanced_accuracy",
    "f1",
    "eer",
    "target_fmr_0.001",
    "target_fmr_0.01",
    "target_fmr_0.05",
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--operating-strategy", default="balanced_accuracy", choices=STRATEGY_CHOICES)
    args = parser.parse_args(argv)

    pairs = parse_lfw_pairs(args.protocol_root / PROTOCOL_FILENAME, args.dataset_root)

    detector = YuNetDetector(args.model_root / YUNET_FILENAME, YUNET_SHA256)
    embedder = SFaceEmbedder(args.model_root / SFACE_FILENAME, SFACE_SHA256)

    result = evaluate_pairs(pairs, detector=detector, embedder=embedder)
    if not result.valid_scores:
        raise SystemExit(
            "No pairs were successfully scored during calibration; stopping rather than "
            "fabricating a threshold."
        )

    calibration = calibrate(result.valid_scores, result.valid_labels, split="validation")
    operating_threshold = calibration.candidates[args.operating_strategy].threshold

    payload = {
        "artifact_type": "calibrated_threshold",
        "dataset": "LFW",
        "protocol_file": PROTOCOL_FILENAME,
        "split": calibration.split,
        "status": calibration.status,
        "threshold": operating_threshold,
        "operating_strategy": args.operating_strategy,
        "candidates": {
            name: {"threshold": candidate.threshold, "metrics": candidate.metrics}
            for name, candidate in calibration.candidates.items()
        },
        "total_pairs": result.total_pairs,
        "scored_pairs": len(result.valid_scores),
        "failure_breakdown": dict(result.failures),
        "model_version": MODEL_VERSION,
        "preprocessing_revision": PREPROCESSING_REVISION,
        "model_sha256": {"yunet": detector.model_sha256, "sface": embedder.model_sha256},
        "software_environment": software_environment_report(),
    }
    write_json_artifact(args.output, payload)
    print(f"Wrote calibrated threshold artifact to {args.output} (threshold={operating_threshold:.6f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
