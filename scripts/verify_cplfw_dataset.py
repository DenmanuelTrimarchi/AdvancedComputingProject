#!/usr/bin/env python3
"""Check that a CPLFW dataset + the authors' updated pair-protocol file
looks structurally valid, and report exactly what was resolved.

``--image-variant`` is required and is echoed into the output: CPLFW ships
two non-interchangeable image sets (the authors' raw, unconstrained images
from ``images.rar`` and a separately pre-cropped/aligned copy from
``cp-aligned.zip``), so a verification result that does not say which one it
checked is not evidence of anything.

Every referenced image must exist. ``parse_cplfw_pairs`` raises on the first
missing file, malformed row, mismatched pair label or duplicate pair, so a
zero exit code means every one of the protocol's references resolved — there
is no partial-success path and nothing is silently excluded.

Usage:
    python scripts/verify_cplfw_dataset.py \
        --dataset-root /secure/path/cplfw_raw \
        --protocol-root /secure/path/protocols \
        --image-variant raw
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from face_verification.config import CPLFW_IMAGE_VARIANTS
from face_verification.protocols import ProtocolError, parse_cplfw_pairs

PROTOCOL_FILENAME = "pairs_CPLFW.txt"
EXPECTED_PAIRS = 6000
EXPECTED_PER_CLASS = 3000


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
    parser.add_argument(
        "--image-variant", required=True, choices=CPLFW_IMAGE_VARIANTS,
        help="Which CPLFW image set --dataset-root points at. Echoed into the "
             "output so the verification result is never ambiguous.",
    )
    args = parser.parse_args(argv)

    if not args.dataset_root.is_dir():
        print(f"FAIL dataset root does not exist: {args.dataset_root}", file=sys.stderr)
        return 1

    protocol_path = args.protocol_root / PROTOCOL_FILENAME
    if not protocol_path.is_file():
        print(f"FAIL missing protocol file: {protocol_path}", file=sys.stderr)
        return 1

    try:
        pairs = parse_cplfw_pairs(protocol_path, args.dataset_root)
    except ProtocolError as exc:
        print(f"FAIL {PROTOCOL_FILENAME}: {exc}", file=sys.stderr)
        return 1

    same = sum(1 for pair in pairs if pair.same_identity)
    different = len(pairs) - same
    referenced = {pair.left_path for pair in pairs} | {pair.right_path for pair in pairs}

    print(f"dataset_image_variant: {args.image_variant}")
    print(f"protocol_file: {PROTOCOL_FILENAME}")
    print(f"OK   total_pairs           : {len(pairs)}")
    print(f"OK   same_identity_pairs   : {same}")
    print(f"OK   different_identity_pairs: {different}")
    print(f"OK   unique_images_referenced: {len(referenced)}")
    print("OK   all references resolved (every protocol-referenced image exists)")
    print("OK   no malformed rows, no mismatched pair labels, no duplicate pairs")
    print("OK   no silent exclusions (parsing aborts on the first unresolved reference)")

    problems = []
    if len(pairs) != EXPECTED_PAIRS:
        problems.append(f"expected {EXPECTED_PAIRS} pairs, parsed {len(pairs)}")
    if same != EXPECTED_PER_CLASS:
        problems.append(f"expected {EXPECTED_PER_CLASS} same-identity pairs, parsed {same}")
    if different != EXPECTED_PER_CLASS:
        problems.append(f"expected {EXPECTED_PER_CLASS} different-identity pairs, parsed {different}")
    if problems:
        print("FAIL official CPLFW protocol shape not matched:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
