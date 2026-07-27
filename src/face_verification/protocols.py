"""Parsers for the LFW and CPLFW pair-list protocols.

The two datasets' authors distribute genuinely different file formats —
confirmed against the real, authors'-distributed ``pairs_CPLFW.txt``, not
assumed from secondary sources:

- **LFW** (``pairs.txt`` / ``pairsDevTrain.txt`` / ``pairsDevTest.txt``): a
  header line, then rows of either ``identity image_a image_b``
  (same-identity / matched) or ``identity_a image_a identity_b image_b``
  (different-identity / mismatched), with images stored per identity at
  ``identity/identity_%04d.jpg``.
- **CPLFW** (``pairs_CPLFW.txt``): no header; every pair is exactly two
  consecutive lines, each ``filename label`` (``label`` is ``0`` or ``1``
  and is identical on both lines of a pair); images are stored flat (no
  per-identity subdirectory) under the dataset root, already named e.g.
  ``Ingrid_Betancourt_1.jpg``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence, Set, Tuple


class ProtocolError(RuntimeError):
    """Raised for any malformed, inconsistent, or unsafe protocol file."""


@dataclass(frozen=True)
class Pair:
    left_path: Path
    right_path: Path
    same_identity: bool
    left_identity: str
    right_identity: str


def _image_filename(identity: str, image_number: str) -> str:
    try:
        number = int(image_number)
    except ValueError as exc:
        raise ProtocolError(f"Image number {image_number!r} is not an integer") from exc
    return f"{identity}_{number:04d}.jpg"


def _resolve_image_path(dataset_root: Path, identity: str, image_number: str) -> Path:
    filename = _image_filename(identity, image_number)
    candidate = (dataset_root / identity / filename).resolve()
    try:
        candidate.relative_to(dataset_root)
    except ValueError as exc:
        raise ProtocolError(f"Resolved image path escapes dataset root: {candidate}") from exc
    if not candidate.is_file():
        raise ProtocolError(f"Missing image referenced by protocol: {candidate}")
    return candidate


def _validate_header(header: Sequence[str], same_count: int, diff_count: int, protocol_path: Path) -> None:
    if len(header) == 1:
        expected = int(header[0])
        if same_count != expected or diff_count != expected:
            raise ProtocolError(
                f"{protocol_path}: header declares {expected} matched and {expected} "
                f"mismatched pairs, found {same_count} matched and {diff_count} mismatched"
            )
    elif len(header) == 2:
        folds, per_fold = int(header[0]), int(header[1])
        expected = folds * per_fold
        if same_count != expected or diff_count != expected:
            raise ProtocolError(
                f"{protocol_path}: header declares {folds} folds x {per_fold} pairs per "
                f"class, expected {expected} matched and {expected} mismatched, found "
                f"{same_count} matched and {diff_count} mismatched"
            )
    else:
        raise ProtocolError(f"{protocol_path}: unrecognised header format: {list(header)}")


def _parse_pairs_file(protocol_path: Path, dataset_root: Path) -> List[Pair]:
    protocol_path = Path(protocol_path)
    dataset_root = Path(dataset_root).resolve()

    if not protocol_path.is_file():
        raise ProtocolError(f"Protocol file does not exist: {protocol_path}")

    raw_lines = protocol_path.read_text(encoding="utf-8").strip("\n").split("\n")
    if not raw_lines or not raw_lines[0].strip():
        raise ProtocolError(f"Empty protocol file: {protocol_path}")

    header = raw_lines[0].split()
    data_lines = raw_lines[1:]

    pairs: List[Pair] = []
    seen: set[tuple[str, str]] = set()
    same_count = 0
    diff_count = 0

    for line_number, raw_line in enumerate(data_lines, start=2):
        line = raw_line.strip()
        if not line:
            continue
        columns = line.split("\t") if "\t" in line else line.split()

        if len(columns) == 3:
            identity, image_a, image_b = columns
            left = _resolve_image_path(dataset_root, identity, image_a)
            right = _resolve_image_path(dataset_root, identity, image_b)
            same_identity = True
            left_identity = right_identity = identity
        elif len(columns) == 4:
            identity_a, image_a, identity_b, image_b = columns
            left = _resolve_image_path(dataset_root, identity_a, image_a)
            right = _resolve_image_path(dataset_root, identity_b, image_b)
            same_identity = False
            left_identity, right_identity = identity_a, identity_b
        else:
            raise ProtocolError(
                f"{protocol_path}:{line_number}: expected 3 or 4 columns, got {len(columns)}"
            )

        key = (str(left), str(right))
        if key in seen:
            raise ProtocolError(f"{protocol_path}: duplicate pair detected: {key}")
        seen.add(key)

        pairs.append(Pair(left, right, same_identity, left_identity, right_identity))
        if same_identity:
            same_count += 1
        else:
            diff_count += 1

    if same_count == 0 or diff_count == 0:
        raise ProtocolError(
            f"{protocol_path} must contain both matched and mismatched pairs; "
            f"found {same_count} matched, {diff_count} mismatched"
        )

    _validate_header(header, same_count, diff_count, protocol_path)
    return pairs


def parse_lfw_pairs(protocol_path: Path, dataset_root: Path) -> List[Pair]:
    return _parse_pairs_file(protocol_path, dataset_root)


def _cplfw_identity_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    prefix, _, suffix = stem.rpartition("_")
    return prefix if prefix and suffix.isdigit() else stem


def _resolve_flat_image_path(dataset_root: Path, filename: str) -> Path:
    candidate = (dataset_root / filename).resolve()
    try:
        candidate.relative_to(dataset_root)
    except ValueError as exc:
        raise ProtocolError(f"Resolved image path escapes dataset root: {candidate}") from exc
    if not candidate.is_file():
        raise ProtocolError(f"Missing image referenced by protocol: {candidate}")
    return candidate


def parse_cplfw_pairs(protocol_path: Path, dataset_root: Path) -> List[Pair]:
    protocol_path = Path(protocol_path)
    dataset_root = Path(dataset_root).resolve()

    if not protocol_path.is_file():
        raise ProtocolError(f"Protocol file does not exist: {protocol_path}")

    lines = [line for line in protocol_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        raise ProtocolError(f"Empty protocol file: {protocol_path}")
    if len(lines) % 2 != 0:
        raise ProtocolError(
            f"{protocol_path}: expected an even number of lines (two per pair), got {len(lines)}"
        )

    pairs: List[Pair] = []
    seen: Set[Tuple[str, str]] = set()
    same_count = 0
    diff_count = 0

    for index in range(0, len(lines), 2):
        line_number = index + 1
        first_columns = lines[index].split()
        second_columns = lines[index + 1].split()

        if len(first_columns) != 2 or len(second_columns) != 2:
            raise ProtocolError(
                f"{protocol_path}:{line_number}: expected 'filename label' on each of a pair's two lines"
            )

        first_filename, first_label = first_columns
        second_filename, second_label = second_columns

        if first_label not in {"0", "1"} or second_label not in {"0", "1"}:
            raise ProtocolError(f"{protocol_path}:{line_number}: label must be 0 or 1")
        if first_label != second_label:
            raise ProtocolError(
                f"{protocol_path}:{line_number}: a pair's two lines must share the same label, "
                f"got {first_label!r} and {second_label!r}"
            )

        left = _resolve_flat_image_path(dataset_root, first_filename)
        right = _resolve_flat_image_path(dataset_root, second_filename)

        key = (str(left), str(right))
        if key in seen:
            raise ProtocolError(f"{protocol_path}: duplicate pair detected: {key}")
        seen.add(key)

        same_identity = first_label == "1"
        pairs.append(
            Pair(
                left,
                right,
                same_identity,
                _cplfw_identity_from_filename(first_filename),
                _cplfw_identity_from_filename(second_filename),
            )
        )
        if same_identity:
            same_count += 1
        else:
            diff_count += 1

    if same_count == 0 or diff_count == 0:
        raise ProtocolError(
            f"{protocol_path} must contain both matched and mismatched pairs; "
            f"found {same_count} matched, {diff_count} mismatched"
        )

    return pairs
