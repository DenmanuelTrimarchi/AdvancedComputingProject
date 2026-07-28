"""Environment-driven configuration and the immutable model contract.

No path in this module is ever hard-coded to a particular researcher's home
directory. Every dataset/protocol/model/cache location comes from an
environment variable (see ``.env.example``) that the caller must set
explicitly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# --- Immutable model contract -----------------------------------------
#
# Changing any of these values changes the evaluation partition: a threshold
# calibrated under one contract must never be applied under another. See
# docs/MODEL_PROVENANCE.md.

EMBEDDING_DIMENSIONS = 128
MODEL_VERSION = "opencv-sface-2021dec-yunet-2023mar"
PREPROCESSING_REVISION = "opencv-yunet-sface-exif-bgr-l2-v1"

YUNET_FILENAME = "face_detection_yunet_2023mar.onnx"
SFACE_FILENAME = "face_recognition_sface_2021dec.onnx"

# Hashes of the official OpenCV Zoo release. Any file that does not match is
# refused rather than loaded (see provenance.verify_model_file).
YUNET_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
SFACE_SHA256 = "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"

DETECTOR_SCORE_THRESHOLD = 0.9
DETECTOR_NMS_THRESHOLD = 0.3
DETECTOR_TOP_K = 5000

# Dependencies whose exact installed version is part of the evaluation
# partition (they can change floating-point results at the margins).
EXPECTED_DEPENDENCY_VERSIONS = {
    "numpy": "2.5.1",
    "opencv-python-headless": "4.13.0.92",
    "Pillow": "12.3.0",
}

DEFAULT_MAX_IMAGE_BYTES = 8 * 1024 * 1024
HARD_MAX_IMAGE_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_IMAGE_PIXELS = 12_000_000
HARD_MAX_IMAGE_PIXELS = 40_000_000

DEFAULT_RANDOM_SEED = 20260727

# Verified archive checksums for this project's specific dataset acquisition
# (see docs/DATASET_PROVENANCE.md for the full acquisition record). These
# describe *this project's* copies, not an upstream-published guarantee for
# CPLFW (whose authors do not publish an official checksum).
LFW_ARCHIVE_FILENAME = "lfwfunneled.tgz"
LFW_ARCHIVE_MD5 = "1b42dfed7d15c9b2dd63d5e5840c86ad"
CPLFW_ARCHIVE_FILENAME = "CPLFW.zip"
CPLFW_ARCHIVE_SHA256 = "9a09dd1ebe1a000c52f69f365f5d564cd529f1fcf4f0479510231856f358f416"

# Per-variant archives nested inside CPLFW_ARCHIVE_FILENAME. CPLFW ships both
# the authors' raw, unconstrained images (``images.rar``) and a separately
# pre-cropped/aligned copy (``cp-aligned.zip``); these are two distinct
# experiment inputs, never interchangeable, hence a required
# ``--image-variant`` argument on scripts/evaluate_cplfw.py rather than an
# assumption baked into the dataset root path.
CPLFW_RAW_ARCHIVE_FILENAME = "images.rar"
CPLFW_RAW_ARCHIVE_SHA256 = "7baca61dda21341eaa642f229eedfbba1d0aaa2d22447d79e158920106831165"
CPLFW_ALIGNED_ARCHIVE_FILENAME = "cp-aligned.zip"
CPLFW_ALIGNED_ARCHIVE_SHA256 = "420adcc13f1ab9510d8f99af04dbfb1695645ff73942c2a1010c5c01fd8367e2"

CPLFW_IMAGE_VARIANTS = ("raw", "aligned")


def cplfw_provenance_fields(image_variant: str) -> dict:
    """Result fields that make a CPLFW evaluation's image variant explicit
    and never omittable. Raises ``ValueError`` for anything but 'raw'/
    'aligned' — the two are non-interchangeable image sets and a result must
    never be ambiguous, or wrong, about which one it scored."""
    if image_variant == "raw":
        archive_filename, archive_sha256 = CPLFW_RAW_ARCHIVE_FILENAME, CPLFW_RAW_ARCHIVE_SHA256
        image_source = "authors-distributed images.rar"
    elif image_variant == "aligned":
        archive_filename, archive_sha256 = CPLFW_ALIGNED_ARCHIVE_FILENAME, CPLFW_ALIGNED_ARCHIVE_SHA256
        image_source = "authors-distributed cp-aligned.zip"
    else:
        raise ValueError(
            f"Unknown CPLFW image variant {image_variant!r}; expected one of {CPLFW_IMAGE_VARIANTS}"
        )
    return {
        "dataset_image_variant": image_variant,
        "dataset_image_source": image_source,
        "dataset_archive_filename": archive_filename,
        "dataset_archive_sha256": archive_sha256,
        "dataset_root_description": "private research storage; path omitted",
    }


class ConfigurationError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class PathConfig:
    """Resolved, user-supplied filesystem roots. Never has a default value
    baked in — every field is either explicitly set or ``None``."""

    data_root: Optional[Path]
    protocol_root: Optional[Path]
    model_root: Optional[Path]
    cache_root: Optional[Path]

    @classmethod
    def from_environment(cls, env: Optional[dict] = None) -> "PathConfig":
        source = os.environ if env is None else env

        def optional(name: str) -> Optional[Path]:
            value = source.get(name)
            return Path(value).expanduser() if value else None

        return cls(
            data_root=optional("FACE_DATA_ROOT"),
            protocol_root=optional("FACE_PROTOCOL_ROOT"),
            model_root=optional("FACE_MODEL_ROOT"),
            cache_root=optional("FACE_CACHE_ROOT"),
        )

    def require_data_root(self) -> Path:
        return _require(self.data_root, "FACE_DATA_ROOT")

    def require_protocol_root(self) -> Path:
        return _require(self.protocol_root, "FACE_PROTOCOL_ROOT")

    def require_model_root(self) -> Path:
        return _require(self.model_root, "FACE_MODEL_ROOT")


def _require(value: Optional[Path], name: str) -> Path:
    if value is None:
        raise ConfigurationError(
            f"{name} is not set. Copy .env.example to .env and fill it in, "
            f"or export {name} directly. This project never assumes a default "
            f"path for real dataset/model files."
        )
    return value
