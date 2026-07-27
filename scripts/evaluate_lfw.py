#!/usr/bin/env python3
"""Experiment 1 Stage 2 (--split dev) and Experiment 3 (--split final).

--split dev is threshold-selection Stage 2: it reads the *candidates*
artifact produced by calibrate_lfw.py, evaluates every candidate against
pairsDevTest.txt, selects exactly one by a fixed documented rule (see
face_verification.calibration.SELECTION_RULE), and overwrites the same
--threshold-artifact file in place with status="frozen" plus full
selection evidence. It refuses to run against an artifact that is not
already status="candidates".

--split final is Experiment 3: it evaluates the already-frozen threshold on
the untouched pairs.txt protocol and refuses to run against anything not
status="frozen" -- it never selects or changes the threshold.

Usage:
    python scripts/evaluate_lfw.py --split dev \
        --dataset-root ... --protocol-root ... --model-root ... \
        --threshold-artifact results/aggregate/calibrated_threshold.json \
        --output results/aggregate/lfw_development_metrics.json

    python scripts/evaluate_lfw.py --split final \
        --dataset-root ... --protocol-root ... --model-root ... \
        --threshold-artifact results/aggregate/calibrated_threshold.json \
        --output results/aggregate/lfw_final_metrics.json
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

from face_verification.artifacts import read_json_artifact, write_json_artifact
from face_verification.calibration import require_candidates, require_frozen_threshold, select_final_threshold
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
from face_verification.verification_evaluator import evaluate_pairs, summarize_metrics

SPLIT_TO_FILENAME = {"dev": "pairsDevTest.txt", "final": "pairs.txt"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", required=True, choices=sorted(SPLIT_TO_FILENAME))
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument(
        "--threshold-artifact", required=True, type=Path,
        help="--split dev: the *candidates* artifact from calibrate_lfw.py, updated in place to "
             "status=frozen. --split final: an already-frozen artifact, read only.",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    protocol_filename = SPLIT_TO_FILENAME[args.split]
    protocol_path = args.protocol_root / protocol_filename
    pairs = parse_lfw_pairs(protocol_path, args.dataset_root)

    detector = YuNetDetector(args.model_root / YUNET_FILENAME, YUNET_SHA256)
    embedder = SFaceEmbedder(args.model_root / SFACE_FILENAME, SFACE_SHA256)

    result = evaluate_pairs(pairs, detector=detector, embedder=embedder)
    if not result.valid_scores:
        raise SystemExit(f"No pairs were successfully scored on {protocol_filename}; stopping.")

    protocol_sha256 = sha256_of_file(protocol_path)
    evaluated_images = {p.left_path for p in pairs} | {p.right_path for p in pairs}
    evaluated_image_set_sha256 = sha256_of_evaluated_image_set(evaluated_images, args.dataset_root)
    threshold_artifact_sha256 = sha256_of_file(args.threshold_artifact)
    threshold_payload = read_json_artifact(args.threshold_artifact)

    extra_fields: Dict[str, Any] = {}

    if args.split == "dev":
        candidates = require_candidates(threshold_payload, context=str(args.threshold_artifact))
        selection = select_final_threshold(candidates, result.valid_scores, result.valid_labels)
        threshold = selection["selected_threshold"]

        frozen_payload = dict(threshold_payload)
        frozen_payload["status"] = "frozen"
        frozen_payload["threshold"] = threshold
        frozen_payload["operating_strategy"] = selection["selected_candidate"]
        frozen_payload["selection_rule"] = selection["selection_rule"]
        frozen_payload["selection_evidence"] = selection["all_candidates_dev_metrics"]
        frozen_payload["frozen_from_protocol"] = protocol_filename
        frozen_payload["frozen_from_protocol_sha256"] = protocol_sha256
        write_json_artifact(args.threshold_artifact, frozen_payload)
        print(
            f"Selected and froze threshold={threshold:.6f} (candidate={selection['selected_candidate']}) "
            f"in {args.threshold_artifact}, based on {protocol_filename}"
        )

        extra_fields = {
            "selected_candidate": selection["selected_candidate"],
            "selection_rule": selection["selection_rule"],
            "all_candidates_dev_metrics": selection["all_candidates_dev_metrics"],
        }
    else:
        threshold = require_frozen_threshold(threshold_payload, context=str(args.threshold_artifact))

    summary = summarize_metrics(result, threshold)

    payload = {
        "artifact_type": "lfw_verification_metrics",
        "split": args.split,
        "protocol_file": protocol_filename,
        "protocol_sha256": protocol_sha256,
        "evaluated_image_set_sha256": evaluated_image_set_sha256,
        "dataset_archive_md5": LFW_ARCHIVE_MD5,
        "threshold_source": str(args.threshold_artifact),
        "threshold_artifact_sha256": threshold_artifact_sha256,
        "threshold_status": "frozen",
        **extra_fields,
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
