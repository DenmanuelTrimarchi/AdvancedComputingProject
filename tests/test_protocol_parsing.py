"""Official LFW and CPLFW pair files are parsed strictly, or not at all.

The published protocols define the experiment, so a silently misread row
would invalidate every downstream figure. Each malformed shape is therefore
required to raise rather than degrade: wrong column counts, declared/actual
count mismatches, duplicate pairs, single-class protocols, missing images and
path traversal. CPLFW's two-lines-per-pair layout is covered separately from
LFW's, because the formats genuinely differ.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from face_verification.protocols import ProtocolError, parse_cplfw_pairs, parse_lfw_pairs
from tests.conftest import make_test_image


def _build_dataset(tmp_path: Path) -> Path:
    dataset_root = tmp_path / "lfw_funneled"
    for identity in ("Alice_Smith", "Bob_Jones"):
        identity_dir = dataset_root / identity
        identity_dir.mkdir(parents=True)
        make_test_image(identity_dir, f"{identity}_0001.jpg", fill=10)
        make_test_image(identity_dir, f"{identity}_0002.jpg", fill=20)
    return dataset_root


def _write_protocol(tmp_path: Path, name: str, lines: list[str]) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_lfw_protocol_header_and_rows(tmp_path):
    dataset_root = _build_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs.txt",
        [
            "2",
            "Alice_Smith 1 2",
            "Bob_Jones 1 2",
            "Alice_Smith 1 Bob_Jones 1",
            "Alice_Smith 2 Bob_Jones 2",
        ],
    )
    pairs = parse_lfw_pairs(protocol_path, dataset_root)
    assert len(pairs) == 4
    assert sum(1 for p in pairs if p.same_identity) == 2
    assert sum(1 for p in pairs if not p.same_identity) == 2


def test_malformed_column_count_fails(tmp_path):
    dataset_root = _build_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs.txt",
        [
            "1",
            "Alice_Smith 1 2",
            "just two columns",
        ],
    )
    with pytest.raises(ProtocolError):
        parse_lfw_pairs(protocol_path, dataset_root)


def test_missing_image_fails(tmp_path):
    dataset_root = _build_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs.txt",
        [
            "1",
            "Alice_Smith 1 9",  # image 9 does not exist
            "Alice_Smith 1 Bob_Jones 1",
        ],
    )
    with pytest.raises(ProtocolError):
        parse_lfw_pairs(protocol_path, dataset_root)


def test_path_traversal_and_missing_image_fail(tmp_path):
    dataset_root = _build_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs.txt",
        [
            "1",
            "../escape 1 2",
            "Alice_Smith 1 Bob_Jones 1",
        ],
    )
    with pytest.raises(ProtocolError):
        parse_lfw_pairs(protocol_path, dataset_root)


def test_duplicate_pair_is_rejected(tmp_path):
    dataset_root = _build_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs.txt",
        [
            "1",
            "Alice_Smith 1 2",
            "Alice_Smith 1 2",
        ],
    )
    with pytest.raises(ProtocolError):
        parse_lfw_pairs(protocol_path, dataset_root)


def test_single_class_protocol_is_rejected(tmp_path):
    dataset_root = _build_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs.txt",
        [
            "2",
            "Alice_Smith 1 2",
            "Bob_Jones 1 2",
        ],
    )
    with pytest.raises(ProtocolError):
        parse_lfw_pairs(protocol_path, dataset_root)


def test_header_count_mismatch_is_rejected(tmp_path):
    dataset_root = _build_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs.txt",
        [
            "3",  # declares 3 matched + 3 mismatched, but only 1 of each follows
            "Alice_Smith 1 2",
            "Alice_Smith 1 Bob_Jones 1",
        ],
    )
    with pytest.raises(ProtocolError):
        parse_lfw_pairs(protocol_path, dataset_root)


def _build_flat_cplfw_dataset(tmp_path: Path) -> Path:
    # CPLFW images are flat (no per-identity subdirectory), unlike LFW.
    dataset_root = tmp_path / "cplfw"
    dataset_root.mkdir()
    for name in ("Alice_Smith_1.jpg", "Alice_Smith_2.jpg", "Bob_Jones_1.jpg", "Bob_Jones_2.jpg"):
        make_test_image(dataset_root, name, fill=15)
    return dataset_root


def test_cplfw_uses_the_real_two_line_per_pair_format(tmp_path):
    # Real pairs_CPLFW.txt has no header; every pair is two consecutive
    # "filename label" lines with the label repeated on both lines.
    dataset_root = _build_flat_cplfw_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs_CPLFW.txt",
        [
            "Alice_Smith_1.jpg 1",
            "Alice_Smith_2.jpg 1",
            "Alice_Smith_1.jpg 0",
            "Bob_Jones_1.jpg 0",
        ],
    )
    pairs = parse_cplfw_pairs(protocol_path, dataset_root)
    assert len(pairs) == 2
    assert pairs[0].same_identity is True
    assert pairs[1].same_identity is False


def test_cplfw_rejects_mismatched_label_within_a_pair(tmp_path):
    dataset_root = _build_flat_cplfw_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs_CPLFW.txt",
        [
            "Alice_Smith_1.jpg 1",
            "Alice_Smith_2.jpg 0",  # labels disagree within one pair
        ],
    )
    with pytest.raises(ProtocolError):
        parse_cplfw_pairs(protocol_path, dataset_root)


def test_cplfw_rejects_odd_line_count(tmp_path):
    dataset_root = _build_flat_cplfw_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs_CPLFW.txt",
        [
            "Alice_Smith_1.jpg 1",
            "Alice_Smith_2.jpg 1",
            "Bob_Jones_1.jpg 0",  # unpaired trailing line
        ],
    )
    with pytest.raises(ProtocolError):
        parse_cplfw_pairs(protocol_path, dataset_root)
