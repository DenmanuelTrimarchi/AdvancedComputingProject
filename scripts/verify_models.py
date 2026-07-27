#!/usr/bin/env python3
"""Hash-verify the two pinned OpenCV Zoo model files at --model-root.

Usage:
    python scripts/verify_models.py --model-root /secure/path/models
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from face_verification.config import SFACE_FILENAME, SFACE_SHA256, YUNET_FILENAME, YUNET_SHA256
from face_verification.provenance import ModelUnavailableError, verify_model_file


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", required=True, type=Path)
    args = parser.parse_args(argv)

    ok = True
    for filename, expected_sha256 in ((YUNET_FILENAME, YUNET_SHA256), (SFACE_FILENAME, SFACE_SHA256)):
        path = args.model_root / filename
        try:
            actual = verify_model_file(path, expected_sha256)
            print(f"OK   {filename}  sha256={actual}")
        except ModelUnavailableError as exc:
            ok = False
            print(f"FAIL {filename}: {exc}", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
