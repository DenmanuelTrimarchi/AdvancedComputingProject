#!/usr/bin/env python3
"""Check that a CPLFW dataset + the authors' updated pair-protocol file
looks structurally valid.

Usage:
    python scripts/verify_cplfw_dataset.py \
        --dataset-root /secure/path/datasets/cplfw \
        --protocol-root /secure/path/protocols
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from face_verification.protocols import ProtocolError, parse_cplfw_pairs

PROTOCOL_FILENAME = "pairs_CPLFW.txt"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
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
        same = sum(1 for pair in pairs if pair.same_identity)
        print(f"OK   {PROTOCOL_FILENAME}: {len(pairs)} pairs ({same} matched, {len(pairs) - same} mismatched)")
        return 0
    except ProtocolError as exc:
        print(f"FAIL {PROTOCOL_FILENAME}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
