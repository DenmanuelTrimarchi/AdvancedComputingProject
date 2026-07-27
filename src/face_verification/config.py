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
