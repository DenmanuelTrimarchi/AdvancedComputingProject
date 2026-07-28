"""CPLFW ships two non-interchangeable image sets (the authors' raw images
in ``images.rar`` and a separately pre-cropped/aligned copy in
``cp-aligned.zip``). ``config.cplfw_provenance_fields`` is what makes a
result's variant explicit and non-omittable — see
``scripts/evaluate_cplfw.py``.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from face_verification.config import CPLFW_IMAGE_VARIANTS, cplfw_provenance_fields

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "evaluate_cplfw.py"


def test_raw_and_aligned_are_the_only_accepted_variants():
    assert set(CPLFW_IMAGE_VARIANTS) == {"raw", "aligned"}


def test_unknown_variant_is_rejected():
    with pytest.raises(ValueError):
        cplfw_provenance_fields("112x112-cropped")


def test_variant_is_always_present_and_matches_the_request():
    for variant in CPLFW_IMAGE_VARIANTS:
        fields = cplfw_provenance_fields(variant)
        assert fields["dataset_image_variant"] == variant


def test_raw_and_aligned_cannot_be_described_as_each_other():
    raw = cplfw_provenance_fields("raw")
    aligned = cplfw_provenance_fields("aligned")

    assert raw["dataset_image_variant"] != aligned["dataset_image_variant"]
    assert raw["dataset_archive_sha256"] != aligned["dataset_archive_sha256"]
    assert raw["dataset_archive_filename"] != aligned["dataset_archive_filename"]
    assert "images.rar" in raw["dataset_image_source"]
    assert "cp-aligned.zip" in aligned["dataset_image_source"]


def test_provenance_fields_never_include_an_absolute_path():
    for variant in CPLFW_IMAGE_VARIANTS:
        fields = cplfw_provenance_fields(variant)
        for value in fields.values():
            assert not str(value).startswith("/")
            assert not str(value).startswith("~")


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *extra_args],
        capture_output=True,
        text=True,
    )


def test_cli_rejects_unknown_image_variant():
    completed = _run_cli(
        "--dataset-root", "unused", "--protocol-root", "unused", "--model-root", "unused",
        "--image-variant", "112x112-cropped",
        "--threshold-artifact", "unused", "--output", "unused",
    )
    assert completed.returncode != 0
    assert "--image-variant" in completed.stderr
    assert "invalid choice" in completed.stderr


def test_cli_requires_image_variant():
    completed = _run_cli(
        "--dataset-root", "unused", "--protocol-root", "unused", "--model-root", "unused",
        "--threshold-artifact", "unused", "--output", "unused",
    )
    assert completed.returncode != 0
    assert "--image-variant" in completed.stderr


def test_cplfw_evaluation_performs_no_separate_calibration():
    """CPLFW must consume a frozen threshold and never produce one. If this
    script ever imported the calibration entry points, a CPLFW-specific
    threshold could be fitted on the very data being reported.

    Checked against the parsed AST rather than the raw text, so that prose
    like "no separate CPLFW calibration step" in the module docstring does
    not read as a violation.
    """
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))

    imported: set[str] = set()
    called: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name):
                called.add(target.id)
            elif isinstance(target, ast.Attribute):
                called.add(target.attr)

    assert "require_frozen_threshold" in imported, "CPLFW must demand an already-frozen threshold"
    assert "require_frozen_threshold" in called, "CPLFW must actually enforce the frozen threshold"

    for forbidden in ("calibrate", "select_final_threshold", "require_candidates"):
        assert forbidden not in imported, (
            f"scripts/evaluate_cplfw.py imports {forbidden!r} — CPLFW must never "
            f"calibrate or re-select a threshold."
        )
        assert forbidden not in called, (
            f"scripts/evaluate_cplfw.py calls {forbidden!r} — CPLFW must never "
            f"calibrate or re-select a threshold."
        )


def test_verifier_requires_and_echoes_the_image_variant():
    """A verification result that does not say which image set it checked is
    not evidence of anything."""
    verifier = SCRIPT.parent / "verify_cplfw_dataset.py"

    missing = subprocess.run(
        [sys.executable, str(verifier), "--dataset-root", "unused", "--protocol-root", "unused"],
        capture_output=True, text=True,
    )
    assert missing.returncode != 0
    assert "--image-variant" in missing.stderr

    bad = subprocess.run(
        [sys.executable, str(verifier), "--dataset-root", "unused",
         "--protocol-root", "unused", "--image-variant", "112x112-cropped"],
        capture_output=True, text=True,
    )
    assert bad.returncode != 0
    assert "invalid choice" in bad.stderr

    assert "dataset_image_variant" in verifier.read_text(encoding="utf-8")
