#!/usr/bin/env python3
"""Check that an LFW dataset + protocol directory looks structurally valid.

Parses all three protocol files against the dataset root and reports pair
counts. Exits non-zero (and prints exactly what's wrong) if anything is
missing or malformed, rather than letting a later experiment fail obscurely.

Usage:
    python scripts/verify_lfw_dataset.py \
        --dataset-root /secure/path/datasets/lfw_funneled \
        --protocol-root /secure/path/protocols
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from face_verification.protocols import ProtocolError, parse_lfw_pairs

REQUIRED_PROTOCOL_FILES = ("pairsDevTrain.txt", "pairsDevTest.txt", "pairs.txt")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--protocol-root", required=True, type=Path)
    args = parser.parse_args(argv)

    if not args.dataset_root.is_dir():
        print(f"FAIL dataset root does not exist: {args.dataset_root}", file=sys.stderr)
        return 1

    ok = True
    for filename in REQUIRED_PROTOCOL_FILES:
        protocol_path = args.protocol_root / filename
        if not protocol_path.is_file():
            print(f"FAIL missing protocol file: {protocol_path}", file=sys.stderr)
            ok = False
            continue
        try:
            pairs = parse_lfw_pairs(protocol_path, args.dataset_root)
            same = sum(1 for pair in pairs if pair.same_identity)
            print(f"OK   {filename}: {len(pairs)} pairs ({same} matched, {len(pairs) - same} mismatched)")
        except ProtocolError as exc:
            ok = False
            print(f"FAIL {filename}: {exc}", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
