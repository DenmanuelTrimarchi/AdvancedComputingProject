#!/usr/bin/env python3
"""Experiments 2 and 3: evaluate the frozen threshold on LFW held-out data.

--split dev reads pairsDevTest.txt (development validation, still not the
final answer). --split final reads pairs.txt (the untouched final
evaluation protocol) and refuses to run unless the supplied threshold
artifact is explicitly tagged "frozen" — the threshold is never
recalibrated here.

Usage:
    python scripts/evaluate_lfw.py --split dev \
        --dataset-root /secure/path/datasets/lfw_funneled \
        --protocol-root /secure/path/protocols \
        --model-root /secure/path/models \
        --threshold-artifact results/aggregate/calibrated_threshold.json \
        --output results/aggregate/lfw_development_metrics.json
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
from face_verification.protocols import parse_lfw_pairs
from face_verification.provenance import software_environment_report
from face_verification.verification_evaluator import evaluate_pairs, summarize_metrics

SPLIT_TO_FILENAME = {"dev": "pairsDevTest.txt", "final": "pairs.txt"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=sorted(SPLIT_TO_FILENAME))
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--threshold-artifact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    threshold_payload = read_json_artifact(args.threshold_artifact)
    threshold = require_frozen_threshold(threshold_payload, context=str(args.threshold_artifact))

    protocol_filename = SPLIT_TO_FILENAME[args.split]
    pairs = parse_lfw_pairs(args.protocol_root / protocol_filename, args.dataset_root)

    detector = YuNetDetector(args.model_root / YUNET_FILENAME, YUNET_SHA256)
    embedder = SFaceEmbedder(args.model_root / SFACE_FILENAME, SFACE_SHA256)

    result = evaluate_pairs(pairs, detector=detector, embedder=embedder)
    summary = summarize_metrics(result, threshold)

    payload = {
        "artifact_type": "lfw_verification_metrics",
        "split": args.split,
        "protocol_file": protocol_filename,
        "threshold_source": str(args.threshold_artifact),
        "threshold_status": threshold_payload.get("status"),
        **summary,
        "model_version": MODEL_VERSION,
        "preprocessing_revision": PREPROCESSING_REVISION,
        "model_sha256": {"yunet": detector.model_sha256, "sface": embedder.model_sha256},
        "software_environment": software_environment_report(),
    }
    write_json_artifact(args.output, payload)
    print(f"Wrote {args.split} LFW metrics to {args.output} (accuracy={summary['accuracy']:.4f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
