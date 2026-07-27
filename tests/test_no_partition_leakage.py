"""The validation/held-out boundary is the single most important
methodological guarantee in this codebase. These tests enforce it directly
in code, not just in documentation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from face_verification.calibration import CalibrationError, calibrate, require_frozen_threshold
from face_verification.gallery_evaluator import GalleryError, build_manifest


def test_calibration_rejects_heldout_scores():
    scores = [0.9, 0.8, 0.3, 0.2]
    labels = [1, 1, 0, 0]
    with pytest.raises(CalibrationError):
        calibrate(scores, labels, split="dev")
    with pytest.raises(CalibrationError):
        calibrate(scores, labels, split="final")


def test_calibration_accepts_validation_only():
    scores = [0.9, 0.8, 0.3, 0.2]
    labels = [1, 1, 0, 0]
    result = calibrate(scores, labels, split="validation")
    assert result.status == "frozen"


def test_frozen_threshold_cannot_be_used_from_a_non_frozen_artifact():
    with pytest.raises(CalibrationError):
        require_frozen_threshold({"status": "calibrating", "threshold": 0.5}, context="test")


def test_calibration_images_excluded_from_gallery(tmp_path: Path):
    identity_to_images = {
        "alice": [tmp_path / "alice_0001.jpg", tmp_path / "alice_0002.jpg"],
        "bob": [tmp_path / "bob_0001.jpg", tmp_path / "bob_0002.jpg"],
        "carol": [tmp_path / "carol_0001.jpg"],
    }
    for images in identity_to_images.values():
        for image in images:
            image.write_bytes(b"placeholder")

    # Simulate the calibration protocol having consumed alice's two images.
    calibration_images = identity_to_images["alice"]

    manifest = build_manifest(identity_to_images, excluded_images=calibration_images, seed=1)

    used_paths = {entry.image_path for entry in manifest.entries}
    assert not used_paths.intersection(set(calibration_images))
    # alice had no images left after exclusion, so she contributes nothing.
    assert all("alice" not in str(path) for path in used_paths)


def test_gallery_requires_at_least_one_gallery_identity(tmp_path: Path):
    lone = tmp_path / "solo_0001.jpg"
    lone.write_bytes(b"placeholder")
    with pytest.raises(GalleryError):
        build_manifest({"solo": [lone]}, seed=1)
