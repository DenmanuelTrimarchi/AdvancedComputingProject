#!/usr/bin/env python3
"""Verify the interpreter and pinned dependency versions before any experiment runs.

Usage:
    python scripts/check_environment.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys

from face_verification.provenance import (
    DependencyContractError,
    check_dependency_contract,
    software_environment_report,
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the report as JSON instead of text.")
    args = parser.parse_args(argv)

    report = software_environment_report()
    try:
        check_dependency_contract(strict=True)
        ok = True
    except DependencyContractError as exc:
        ok = False
        report["dependency_error"] = str(exc)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Python: {report['python_version']}")
        print(f"Platform: {report['platform']}")
        print(f"Processor: {report['processor']}")
        for package, info in report["dependencies"].items():
            status = "OK" if info["installed"] == info["expected"] else "MISMATCH"
            print(f"  {package}: expected={info['expected']} installed={info['installed']} [{status}]")
        if not ok:
            print(f"\nFAILED: {report['dependency_error']}", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
