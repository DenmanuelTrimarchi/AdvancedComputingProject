"""Structural interfaces for the detection and embedding stages.

The evaluators depend on two operations, not on the concrete OpenCV wrappers
that provide them. Declaring that dependency structurally keeps the pinned
model out of the unit tests, which substitute deterministic fakes rather than
loading a real ONNX binary, and documents the exact surface any replacement
stage would have to honour.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class FaceDetector(Protocol):
    """Returns one detected face's row, or raises ``FaceCountError``."""

    def detect_single_face(self, bgr: np.ndarray) -> np.ndarray: ...


@runtime_checkable
class FaceEmbedder(Protocol):
    """Returns a raw, not yet L2-normalised embedding for a detected face."""

    def embed(self, bgr: np.ndarray, face_row: np.ndarray) -> np.ndarray: ...
