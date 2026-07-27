"""OpenCV SFace embedding wrapper.

Produces a raw (not yet L2-normalised) 128-value feature vector aligned from
a YuNet detection. Normalisation is deliberately a separate step
(``similarity.l2_normalize``) so both the live pipeline and any offline
re-analysis share the exact same normalisation code path.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .config import EMBEDDING_DIMENSIONS
from .provenance import verify_model_file


class EmbeddingShapeError(RuntimeError):
    """Raised when SFace returns a vector of unexpected shape."""


class SFaceEmbedder:
    def __init__(self, model_path: Path, expected_sha256: str):
        self.model_sha256 = verify_model_file(Path(model_path), expected_sha256)
        self._recognizer = cv2.FaceRecognizerSF.create(str(model_path), "")

    def embed(self, bgr: np.ndarray, face_row: np.ndarray) -> np.ndarray:
        aligned = self._recognizer.alignCrop(bgr, face_row)
        feature = self._recognizer.feature(aligned)
        embedding = np.asarray(feature, dtype=np.float64).reshape(-1)
        if embedding.shape[0] != EMBEDDING_DIMENSIONS:
            raise EmbeddingShapeError(
                f"Unexpected embedding dimensionality {embedding.shape[0]}, "
                f"expected {EMBEDDING_DIMENSIONS}"
            )
        return embedding
