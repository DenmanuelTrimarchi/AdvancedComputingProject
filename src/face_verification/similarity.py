"""Cosine similarity and L2 normalisation for face embeddings.

This is the one normalisation code path used everywhere in the project —
live embedding, cached embedding, and any re-analysis of stored scores all
go through this module so results stay comparable.
"""

from __future__ import annotations

import math

import numpy as np


class SimilarityError(ValueError):
    """Raised for malformed embeddings (wrong shape, non-finite, zero norm)."""


def l2_normalize(vector: np.ndarray, *, tolerance: float = 1e-7) -> np.ndarray:
    vector = np.asarray(vector, dtype=np.float64).reshape(-1)
    if vector.shape[0] == 0:
        raise SimilarityError("Vector must have at least one dimension.")
    if not np.all(np.isfinite(vector)):
        raise SimilarityError("Vector must contain only finite numbers before normalisation.")
    norm = math.sqrt(float(np.dot(vector, vector)))
    if norm <= 1e-12:
        raise SimilarityError("Vector norm is too close to zero to normalise safely.")
    normalized = vector / norm
    result_norm = math.sqrt(float(np.dot(normalized, normalized)))
    if abs(result_norm - 1.0) > tolerance:
        raise SimilarityError("Normalisation self-check failed.")
    return normalized


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float64).reshape(-1)
    right = np.asarray(right, dtype=np.float64).reshape(-1)
    if left.shape[0] == 0 or left.shape[0] != right.shape[0]:
        raise SimilarityError("Embeddings must have the same non-zero number of dimensions.")
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise SimilarityError("Embeddings must contain only finite numbers.")
    left_norm = math.sqrt(float(np.dot(left, left)))
    right_norm = math.sqrt(float(np.dot(right, right)))
    if left_norm == 0.0 or right_norm == 0.0:
        raise SimilarityError("Embeddings must have a non-zero norm.")
    return float(np.dot(left, right) / (left_norm * right_norm))
