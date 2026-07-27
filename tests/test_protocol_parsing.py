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


def test_cplfw_parses_the_same_format(tmp_path):
    dataset_root = _build_dataset(tmp_path)
    protocol_path = _write_protocol(
        tmp_path,
        "pairs_CPLFW.txt",
        [
            "1",
            "Alice_Smith 1 2",
            "Alice_Smith 1 Bob_Jones 1",
        ],
    )
    pairs = parse_cplfw_pairs(protocol_path, dataset_root)
    assert len(pairs) == 2
