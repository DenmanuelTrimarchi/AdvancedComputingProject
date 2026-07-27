#!/usr/bin/env python3
"""Build a deterministic 1:N duplicate-profile gallery manifest from real
LFW images.

Identities appearing in the calibration protocol (pairsDevTrain.txt by
default) are excluded, so calibration data never leaks into the gallery
experiment. The manifest this script writes contains real image paths and
must never be committed to Git — write it under results/raw/ (already
git-ignored) or another private location, never under results/aggregate/.

Usage:
    python scripts/create_gallery_manifest.py \
        --dataset-root /secure/path/datasets/lfw_funneled \
        --protocol-root /secure/path/protocols \
        --output results/raw/gallery_manifest.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

from face_verification.config import DEFAULT_RANDOM_SEED
from face_verification.gallery_evaluator import build_manifest
from face_verification.protocols import parse_lfw_pairs


def _discover_identity_images(dataset_root: Path) -> Dict[str, List[Path]]:
    identities: Dict[str, List[Path]] = {}
    for identity_dir in sorted(p for p in dataset_root.iterdir() if p.is_dir()):
        images = sorted(identity_dir.glob(f"{identity_dir.name}_*.jpg"))
        if images:
            identities[identity_dir.name] = images
    return identities


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument("--calibration-protocol", default="pairsDevTrain.txt")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    parser.add_argument("--max-unknown-identities", type=int, default=None)
    args = parser.parse_args(argv)

    if not args.dataset_root.is_dir():
        raise SystemExit(f"Dataset root does not exist: {args.dataset_root}")

    identity_to_images = _discover_identity_images(args.dataset_root)

    calibration_pairs = parse_lfw_pairs(args.protocol_root / args.calibration_protocol, args.dataset_root)
    excluded_images = set()
    for pair in calibration_pairs:
        excluded_images.add(pair.left_path)
        excluded_images.add(pair.right_path)

    manifest = build_manifest(
        identity_to_images,
        excluded_images=excluded_images,
        seed=args.seed,
        max_unknown_identities=args.max_unknown_identities,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "seed": manifest.seed,
        "entries": [
            {
                "sample_id": entry.sample_id,
                "identity_hash": entry.identity_hash,
                "role": entry.role,
                "image_path": str(entry.image_path),
            }
            for entry in manifest.entries
        ],
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    gallery_count = sum(1 for entry in manifest.entries if entry.role == "gallery")
    duplicate_count = sum(1 for entry in manifest.entries if entry.role == "duplicate_probe")
    unknown_count = sum(1 for entry in manifest.entries if entry.role == "unknown_probe")
    print(
        f"Wrote gallery manifest to {args.output}: {gallery_count} gallery, "
        f"{duplicate_count} duplicate probes, {unknown_count} unknown probes. "
        f"This file contains real image paths — keep it out of Git."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
