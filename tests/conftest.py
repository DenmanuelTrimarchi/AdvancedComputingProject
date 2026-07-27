"""Shared test fixtures.

No test in this suite loads a real YuNet/SFace model file. Detection and
embedding are stood in for by small duck-typed fakes keyed off the exact
byte content of a tiny, deterministically generated PNG, so behaviour is
fully controllable and reproducible without any model binary on disk.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image

from face_verification.detector import FaceCountError


def array_key(bgr: np.ndarray) -> str:
    return hashlib.sha256(bgr.tobytes()).hexdigest()


def make_test_image(directory: Path, name: str, fill: int) -> Tuple[Path, str]:
    """Write a tiny, lossless, uniform-colour PNG and return (path, content_key).

    Because every channel is set to the same value, the byte content is
    identical whether read back as RGB or BGR, so the returned key matches
    what ``image_io.load_image_bgr`` will see after the round trip.
    """
    array = np.full((8, 8, 3), fill, dtype=np.uint8)
    path = directory / name
    Image.fromarray(array, mode="RGB").save(path, format="PNG")
    return path, array_key(array)


class FakeDetector:
    """Duck-types ``YuNetDetector.detect_single_face`` without a real model."""

    def __init__(self, face_counts: Optional[Dict[str, int]] = None, default_count: int = 1):
        self.face_counts = face_counts or {}
        self.default_count = default_count

    def detect_single_face(self, bgr: np.ndarray) -> np.ndarray:
        count = self.face_counts.get(array_key(bgr), self.default_count)
        if count != 1:
            raise FaceCountError(count)
        return np.array([0, 0, bgr.shape[1], bgr.shape[0], 0, 0, 0, 0, 0, 0, 0, 0, 1.0], dtype=np.float32)


class FakeEmbedder:
    """Duck-types ``SFaceEmbedder.embed``: a deterministic vector per image,
    or an explicit override for a given image key (e.g. to inject a
    non-finite vector for failure-path tests)."""

    def __init__(self, dimensions: int = 128, overrides: Optional[Dict[str, np.ndarray]] = None):
        self.dimensions = dimensions
        self.overrides = overrides or {}

    def embed(self, bgr: np.ndarray, face_row: np.ndarray) -> np.ndarray:
        key = array_key(bgr)
        if key in self.overrides:
            return np.asarray(self.overrides[key], dtype=np.float64)
        seed = int(key[:8], 16)
        rng = np.random.default_rng(seed)
        return rng.normal(size=self.dimensions)
