"""CPLFW ships two non-interchangeable image sets (the authors' raw images
in ``images.rar`` and a separately pre-cropped/aligned copy in
``cp-aligned.zip``). ``config.cplfw_provenance_fields`` is what makes a
result's variant explicit and non-omittable — see
``scripts/evaluate_cplfw.py``.
"""

from __future__ import annotations

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
