#!/usr/bin/env python3
"""Fail loudly if any file under a public results directory contains a
personal or absolute filesystem path (a ``/Users/...`` or ``\\Users\\...``
prefix, the researcher's home directory, or the expanded value of
FACE_DATA_ROOT/FACE_PROTOCOL_ROOT/FACE_MODEL_ROOT/FACE_CACHE_ROOT).

``scripts/run_complete_experiment.py`` already runs this check automatically
before it finishes; this script exists to re-run the same check standalone
(CI, or after hand-editing a committed result).

Usage:
    python scripts/check_public_results_privacy.py --results-root results/aggregate
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from face_verification.privacy import default_forbidden_path_substrings, find_path_leaks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", required=True, type=Path)
    args = parser.parse_args(argv)

    leaks = find_path_leaks(args.results_root, forbidden_substrings=default_forbidden_path_substrings())
    if leaks:
        print("FAIL personal/absolute path(s) found in public results:", file=sys.stderr)
        for leak in leaks:
            print(f"  {leak}", file=sys.stderr)
        return 1

    print(f"OK   no personal/absolute paths found under {args.results_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
