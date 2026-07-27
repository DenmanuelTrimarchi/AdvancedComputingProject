#!/usr/bin/env python3
"""Flatten the raw, authors'-distributed CPLFW extraction (``images.rar``,
which nests every image one level down under ``correct_points/`` alongside
per-image landmark ``.txt`` files) into a single flat directory of images
only, matching the flat-filename layout that
``face_verification.protocols.parse_cplfw_pairs`` expects.

Copies, never moves, so the original extraction is left untouched. Refuses
to run if two different source files would collide on the same destination
filename, rather than silently overwriting one with the other.

Usage:
    python scripts/prepare_cplfw_raw_images.py \
        --source-root /secure/path/cplfw_raw_extracted \
        --target-root /secure/path/cplfw_raw
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def discover_images(source_root: Path) -> dict[str, Path]:
    """Map destination filename -> unique source path, raising if two
    different source files would collide on the same filename."""
    by_name: dict[str, Path] = {}
    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        existing = by_name.get(path.name)
        if existing is not None and existing != path:
            raise SystemExit(
                f"Filename collision: {path.name!r} found at both "
                f"{existing} and {path}. Refusing to overwrite silently."
            )
        by_name[path.name] = path
    return by_name


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--target-root", required=True, type=Path)
    args = parser.parse_args(argv)

    if not args.source_root.is_dir():
        print(f"FAIL source root does not exist: {args.source_root}", file=sys.stderr)
        return 1

    by_name = discover_images(args.source_root)
    if not by_name:
        print(f"FAIL no JPG/JPEG/PNG files found under {args.source_root}", file=sys.stderr)
        return 1

    args.target_root.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name, source in by_name.items():
        destination = args.target_root / name
        if destination.exists():
            if destination.stat().st_size != source.stat().st_size:
                raise SystemExit(
                    f"Refusing to overwrite conflicting existing file: {destination} "
                    f"(size differs from source {source})"
                )
            continue
        shutil.copy2(source, destination)
        copied += 1

    print(f"Copied {copied} image file(s) into {args.target_root} ({len(by_name)} total unique filenames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
