"""OpenCV YuNet face-detection wrapper.

Requires exactly one detectable face per image, in line with the research
question ("does this selfie/photo show one identifiable face"), and never
silently proceeds with zero or multiple detections — see
docs/EVALUATION_PROTOCOL.md for how those outcomes are counted rather than
dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import DETECTOR_NMS_THRESHOLD, DETECTOR_SCORE_THRESHOLD, DETECTOR_TOP_K
from .provenance import verify_model_file


class FaceCountError(RuntimeError):
    """Raised when an image does not contain exactly one detectable face."""

    def __init__(self, face_count: int):
        super().__init__(f"Expected exactly one face, found {face_count}")
        self.face_count = face_count


@dataclass(frozen=True)
class DetectorSettings:
    score_threshold: float = DETECTOR_SCORE_THRESHOLD
    nms_threshold: float = DETECTOR_NMS_THRESHOLD
    top_k: int = DETECTOR_TOP_K


class YuNetDetector:
    def __init__(
        self,
        model_path: Path,
        expected_sha256: str,
        settings: DetectorSettings = DetectorSettings(),
    ):
        self.model_sha256 = verify_model_file(Path(model_path), expected_sha256)
        self.settings = settings
        self._detector = cv2.FaceDetectorYN.create(
            str(model_path),
            "",
            (320, 320),
            settings.score_threshold,
            settings.nms_threshold,
            settings.top_k,
        )

    def detect_single_face(self, bgr: np.ndarray) -> np.ndarray:
        """Return the single detected face's row from YuNet's output matrix
        (bounding box, 5 landmarks, confidence), or raise FaceCountError."""
        height, width = bgr.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(bgr)
        count = 0 if faces is None else len(faces)
        if count != 1:
            raise FaceCountError(count)
        return faces[0]
