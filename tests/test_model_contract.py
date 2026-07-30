"""The pinned model and dependency contract, checked before any inference.

Results are only comparable if the exact same model weights produced them, so
a digest mismatch must stop the run before OpenCV ever loads the file — that
ordering is asserted here, not assumed. No real ONNX binary is needed: the
hash check is what is under test, and it fails on content alone.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from face_verification import provenance as provenance_module
from face_verification.detector import YuNetDetector
from face_verification.embedder import SFaceEmbedder
from face_verification.provenance import (
    DependencyContractError,
    ModelUnavailableError,
    sha256_of_file,
    verify_model_file,
)


def test_verify_model_file_accepts_matching_hash(tmp_path: Path):
    path = tmp_path / "model.onnx"
    path.write_bytes(b"pretend model bytes")
    expected = sha256_of_file(path)
    assert verify_model_file(path, expected) == expected


def test_verify_model_file_rejects_mismatched_hash(tmp_path: Path):
    path = tmp_path / "model.onnx"
    path.write_bytes(b"pretend model bytes")
    with pytest.raises(ModelUnavailableError):
        verify_model_file(path, "0" * 64)


def test_verify_model_file_rejects_missing_file(tmp_path: Path):
    with pytest.raises(ModelUnavailableError):
        verify_model_file(tmp_path / "does_not_exist.onnx", "0" * 64)


def test_yunet_detector_refuses_hash_mismatch_before_touching_opencv(tmp_path: Path):
    dummy = tmp_path / "face_detection_yunet_2023mar.onnx"
    dummy.write_bytes(b"not a real model")
    with pytest.raises(ModelUnavailableError):
        YuNetDetector(dummy, "0" * 64)


def test_sface_embedder_refuses_hash_mismatch_before_touching_opencv(tmp_path: Path):
    dummy = tmp_path / "face_recognition_sface_2021dec.onnx"
    dummy.write_bytes(b"not a real model")
    with pytest.raises(ModelUnavailableError):
        SFaceEmbedder(dummy, "0" * 64)


def test_dependency_contract_detects_mismatch(monkeypatch):
    monkeypatch.setattr(
        provenance_module, "EXPECTED_DEPENDENCY_VERSIONS", {"numpy": "0.0.0-impossible-version"}
    )
    with pytest.raises(DependencyContractError):
        provenance_module.check_dependency_contract(strict=True)


def test_dependency_contract_report_is_non_strict_by_default(monkeypatch):
    monkeypatch.setattr(
        provenance_module, "EXPECTED_DEPENDENCY_VERSIONS", {"numpy": "0.0.0-impossible-version"}
    )
    report = provenance_module.check_dependency_contract(strict=False)
    assert report["numpy"]["expected"] == "0.0.0-impossible-version"
    assert report["numpy"]["installed"] != "0.0.0-impossible-version"
