#!/usr/bin/env python3
"""Run the complete experiment pipeline in the required order:

1. environment/model validation
2. LFW calibration (pairsDevTrain.txt)
3. LFW development validation (pairsDevTest.txt)
4. final LFW evaluation (pairs.txt)
5. CPLFW evaluation
6. duplicate gallery evaluation
7. (aggregate report generation is a separate manual step — see
   docs/EVALUATION_PROTOCOL.md — this script's job is to produce the JSON/CSV
   artifacts a report is written from)

Stops immediately, with the underlying script's error message, rather than
fabricating a result when a required dataset, protocol or model file is
missing or invalid.

Usage:
    python scripts/run_complete_experiment.py \
        --dataset-root /secure/path/datasets \
        --protocol-root /secure/path/protocols \
        --model-root /secure/path/models \
        --output-root results/aggregate
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def _run(args: list[str]) -> None:
    printable = " ".join(str(a) for a in args)
    print(f"\n$ {sys.executable} {printable}")
    completed = subprocess.run([sys.executable, *args])
    if completed.returncode != 0:
        raise SystemExit(f"Stopping: step failed (exit code {completed.returncode}): {printable}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--dataset-root", required=True, type=Path,
        help="Root containing lfw_funneled/ and cplfw/ subdirectories",
    )
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument(
        "--gallery-manifest", type=Path, default=Path("results/raw/gallery_manifest.json"),
        help="Where to write the private gallery manifest (must stay out of Git).",
    )
    parser.add_argument("--operating-strategy", default="balanced_accuracy")
    args = parser.parse_args(argv)

    lfw_root = args.dataset_root / "lfw_funneled"
    cplfw_root = args.dataset_root / "cplfw"
    output_root = args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    threshold_artifact = output_root / "calibrated_threshold.json"
    dev_metrics = output_root / "lfw_development_metrics.json"
    final_metrics = output_root / "lfw_final_metrics.json"
    cplfw_metrics = output_root / "cplfw_metrics.json"
    duplicate_metrics = output_root / "duplicate_gallery_metrics.json"

    _run([str(SCRIPTS_DIR / "check_environment.py")])
    _run([str(SCRIPTS_DIR / "verify_models.py"), "--model-root", str(args.model_root)])
    _run([
        str(SCRIPTS_DIR / "verify_lfw_dataset.py"),
        "--dataset-root", str(lfw_root), "--protocol-root", str(args.protocol_root),
    ])
    _run([
        str(SCRIPTS_DIR / "verify_cplfw_dataset.py"),
        "--dataset-root", str(cplfw_root), "--protocol-root", str(args.protocol_root),
    ])

    _run([
        str(SCRIPTS_DIR / "calibrate_lfw.py"),
        "--dataset-root", str(lfw_root), "--protocol-root", str(args.protocol_root),
        "--model-root", str(args.model_root), "--output", str(threshold_artifact),
        "--operating-strategy", args.operating_strategy,
    ])
    _run([
        str(SCRIPTS_DIR / "evaluate_lfw.py"), "--split", "dev",
        "--dataset-root", str(lfw_root), "--protocol-root", str(args.protocol_root),
        "--model-root", str(args.model_root), "--threshold-artifact", str(threshold_artifact),
        "--output", str(dev_metrics),
    ])
    _run([
        str(SCRIPTS_DIR / "evaluate_lfw.py"), "--split", "final",
        "--dataset-root", str(lfw_root), "--protocol-root", str(args.protocol_root),
        "--model-root", str(args.model_root), "--threshold-artifact", str(threshold_artifact),
        "--output", str(final_metrics),
    ])
    _run([
        str(SCRIPTS_DIR / "evaluate_cplfw.py"),
        "--dataset-root", str(cplfw_root), "--protocol-root", str(args.protocol_root),
        "--model-root", str(args.model_root), "--threshold-artifact", str(threshold_artifact),
        "--output", str(cplfw_metrics),
    ])
    _run([
        str(SCRIPTS_DIR / "create_gallery_manifest.py"),
        "--dataset-root", str(lfw_root), "--protocol-root", str(args.protocol_root),
        "--output", str(args.gallery_manifest),
    ])
    _run([
        str(SCRIPTS_DIR / "evaluate_duplicate_gallery.py"),
        "--manifest", str(args.gallery_manifest), "--model-root", str(args.model_root),
        "--threshold-artifact", str(threshold_artifact), "--output", str(duplicate_metrics),
    ])

    print(f"\nComplete. Aggregate results are in {output_root}")
    print(
        "The duplicate-gallery step reused the calibrated threshold artifact's own operating "
        "threshold as the duplicate-review threshold; pass --threshold-strategy directly to "
        "scripts/evaluate_duplicate_gallery.py to use a different named candidate instead."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
