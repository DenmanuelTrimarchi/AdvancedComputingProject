#!/usr/bin/env python3
"""Fail loudly if any public output contains a personal or absolute
filesystem path.

Scans every JSON, CSV, Markdown and text file under each supplied path, plus
the embedded text metadata of every PNG, for a ``/Users/...`` or
``\\Users\\...`` prefix, ``/home/``, the researcher's home directory, the
known private-storage location names (``SecureResearchData``,
``Library/CloudStorage``), and the expanded value of
FACE_DATA_ROOT/FACE_PROTOCOL_ROOT/FACE_MODEL_ROOT/FACE_CACHE_ROOT.

Exits non-zero on the first prohibited string found anywhere.

Note the one thing this cannot check: text *rendered into image pixels*.
PNG pixels are never read. Rendered evidence images are protected by the
redaction step in ``scripts/generate_report_evidence.py``, not by this
scanner.

``scripts/run_complete_experiment.py`` runs the same check automatically
before it finishes; this script exists to re-run it standalone across
several roots at once (CI, or after hand-editing a committed result).

Usage:
    python scripts/check_public_outputs.py \
        --paths results/aggregate results/report_evidence results/historical
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from face_verification.privacy import default_forbidden_path_substrings, find_path_leaks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--paths", required=True, nargs="+", type=Path,
        help="One or more public output directories (or files) to scan.",
    )
    args = parser.parse_args(argv)

    forbidden = default_forbidden_path_substrings()
    all_leaks = []
    scanned = []

    for path in args.paths:
        if not path.exists():
            print(f"FAIL path does not exist: {path}", file=sys.stderr)
            return 1
        leaks = find_path_leaks(path, forbidden_substrings=forbidden)
        all_leaks.extend(leaks)
        scanned.append(path)

    if all_leaks:
        print("FAIL personal/absolute path(s) found in public outputs:", file=sys.stderr)
        for leak in all_leaks:
            print(f"  {leak}", file=sys.stderr)
        return 1

    print(f"OK   no personal/absolute paths found under: {', '.join(str(p) for p in scanned)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
