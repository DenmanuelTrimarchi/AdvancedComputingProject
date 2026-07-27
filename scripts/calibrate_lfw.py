#!/usr/bin/env python3
"""Experiment 1, Stage 1: generate candidate thresholds from LFW
pairsDevTrain.txt only.

Never reads pairsDevTest.txt or pairs.txt, and never itself selects a
winner — see scripts/evaluate_lfw.py --split dev, which is Stage 2 and is
the only step allowed to freeze a threshold for held-out use.

Usage:
    python scripts/calibrate_lfw.py \
        --dataset-root /path/to/AU-OneDrive/datasets/lfw_funneled \
        --protocol-root /path/to/AU-OneDrive/protocols \
        --model-root /path/to/AU-OneDrive/models \
        --output results/aggregate/calibrated_threshold.json
"""

from __future__ import annotations

import argparse
from pathlib import Path

from face_verification.artifacts import write_json_artifact
from face_verification.calibration import calibrate
from face_verification.config import (
    LFW_ARCHIVE_MD5,
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
from face_verification.provenance import sha256_of_evaluated_image_set, sha256_of_file, software_environment_report
from face_verification.verification_evaluator import evaluate_pairs

PROTOCOL_FILENAME = "pairsDevTrain.txt"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    protocol_path = args.protocol_root / PROTOCOL_FILENAME
    pairs = parse_lfw_pairs(protocol_path, args.dataset_root)

    detector = YuNetDetector(args.model_root / YUNET_FILENAME, YUNET_SHA256)
    embedder = SFaceEmbedder(args.model_root / SFACE_FILENAME, SFACE_SHA256)

    result = evaluate_pairs(pairs, detector=detector, embedder=embedder)
    if not result.valid_scores:
        raise SystemExit(
            "No pairs were successfully scored during calibration; stopping rather than "
            "fabricating a threshold."
        )

    calibration = calibrate(result.valid_scores, result.valid_labels, split="validation")

    evaluated_images = {p.left_path for p in pairs} | {p.right_path for p in pairs}

    payload = {
        "artifact_type": "calibrated_threshold",
        "dataset": "LFW",
        "protocol_file": PROTOCOL_FILENAME,
        "protocol_sha256": sha256_of_file(protocol_path),
        "evaluated_image_set_sha256": sha256_of_evaluated_image_set(evaluated_images, args.dataset_root),
        "dataset_archive_md5": LFW_ARCHIVE_MD5,
        "split": calibration.split,
        "status": calibration.status,
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
    print(
        f"Wrote {len(calibration.candidates)} candidate threshold(s) to {args.output} "
        f"(status=candidates; run scripts/evaluate_lfw.py --split dev next to select and freeze one)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
