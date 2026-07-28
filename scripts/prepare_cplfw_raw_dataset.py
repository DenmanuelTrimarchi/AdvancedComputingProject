#!/usr/bin/env python3
"""Flatten the raw, authors'-distributed CPLFW extraction (``images.rar``,
which nests every image one level down under ``correct_points/`` alongside
per-image 5-point landmark ``.txt`` files) into a single flat directory of
images only, matching the flat-filename layout that
``face_verification.protocols.parse_cplfw_pairs`` expects.

Copies, never moves, so the original extraction is left untouched.

Two source files that would land on the same destination filename are a
*collision* and abort the run; two files with the same name and
byte-identical content are a harmless *duplicate* and are counted, not
copied twice. The distinction is made by SHA-256, never by filename alone —
silently picking one of two *different* images would corrupt the evaluation
in a way no later check could detect.

Usage:
    python scripts/prepare_cplfw_raw_dataset.py \
        --source-root /secure/path/cplfw_raw_extracted \
        --target-root /secure/path/cplfw_raw
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Tuple

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def sha256_of(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_images(source_root: Path) -> Tuple[Dict[str, Path], int, List[str]]:
    """Return (destination filename -> source path, duplicate count, collisions)."""
    chosen: Dict[str, Path] = {}
    hashes: Dict[str, str] = {}
    duplicates = 0
    collisions: List[str] = []

    for path in sorted(source_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        name = path.name
        if name not in chosen:
            chosen[name] = path
            continue
        if name not in hashes:
            hashes[name] = sha256_of(chosen[name])
        if sha256_of(path) == hashes[name]:
            duplicates += 1
        else:
            collisions.append(f"{name}: {chosen[name].name} differs in content from {path}")
    return chosen, duplicates, collisions


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--target-root", required=True, type=Path)
    args = parser.parse_args(argv)

    if not args.source_root.is_dir():
        print(f"FAIL source root does not exist: {args.source_root}", file=sys.stderr)
        return 1

    source_count = sum(
        1 for p in args.source_root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )
    chosen, duplicates, collisions = discover_images(args.source_root)

    if collisions:
        print(f"FAIL {len(collisions)} filename collision(s) — different files share a name:", file=sys.stderr)
        for collision in collisions:
            print(f"  {collision}", file=sys.stderr)
        print("Refusing to overwrite silently.", file=sys.stderr)
        return 1

    if not chosen:
        print(f"FAIL no JPG/JPEG/PNG files found under {args.source_root}", file=sys.stderr)
        return 1

    args.target_root.mkdir(parents=True, exist_ok=True)
    copied = 0
    for name, source in sorted(chosen.items()):
        destination = args.target_root / name
        if destination.exists():
            if sha256_of(destination) != sha256_of(source):
                print(f"FAIL refusing to overwrite an existing, different file: {name}", file=sys.stderr)
                return 1
            continue
        shutil.copy2(source, destination)
        copied += 1

    print(f"OK   source images found  : {source_count}")
    print(f"OK   unique filenames     : {len(chosen)}")
    print(f"OK   copied               : {copied}")
    print(f"OK   duplicates skipped   : {duplicates} (same name, byte-identical content)")
    print(f"OK   collisions           : {len(collisions)} (same name, different content)")
    print(f"OK   target layout        : flat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
