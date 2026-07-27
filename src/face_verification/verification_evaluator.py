"""Scores an LFW/CPLFW-style pair protocol end to end and reports metrics.

Face-extraction failures (zero or multiple detected faces, unreadable
images) are recorded as their own explicit outcome category and reported
alongside the accuracy metrics — never silently dropped from the pair count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from . import metrics as metrics_module
from .detector import FaceCountError, YuNetDetector
from .embedder import SFaceEmbedder
from .image_io import ImageLoadError, load_image_bgr
from .protocols import Pair
from .similarity import SimilarityError, cosine_similarity, l2_normalize


@dataclass(frozen=True)
class PairScore:
    pair: Pair
    similarity: Optional[float]
    failure_code: Optional[str]


@dataclass
class EvaluationResult:
    total_pairs: int
    scored_pairs: List[PairScore]
    failures: Dict[str, int] = field(default_factory=dict)

    @property
    def valid_scores(self) -> List[float]:
        return [s.similarity for s in self.scored_pairs if s.similarity is not None]

    @property
    def valid_labels(self) -> List[int]:
        return [1 if s.pair.same_identity else 0 for s in self.scored_pairs if s.similarity is not None]

    @property
    def failure_rate(self) -> float:
        return sum(self.failures.values()) / self.total_pairs if self.total_pairs else float("nan")


def _embed_image(
    path: Path,
    detector: YuNetDetector,
    embedder: SFaceEmbedder,
    cache: Dict[Path, np.ndarray],
) -> np.ndarray:
    if path in cache:
        return cache[path]
    loaded = load_image_bgr(path)
    face_row = detector.detect_single_face(loaded.bgr)
    raw_embedding = embedder.embed(loaded.bgr, face_row)
    normalized = l2_normalize(raw_embedding)
    cache[path] = normalized
    return normalized


def evaluate_pairs(pairs: List[Pair], *, detector: YuNetDetector, embedder: SFaceEmbedder) -> EvaluationResult:
    scored: List[PairScore] = []
    failures: Dict[str, int] = {}
    cache: Dict[Path, np.ndarray] = {}

    def record(code: str) -> None:
        failures[code] = failures.get(code, 0) + 1

    def embed_side(path: Path, side: str) -> "tuple[Optional[np.ndarray], Optional[str]]":
        try:
            return _embed_image(path, detector, embedder, cache), None
        except FaceCountError as exc:
            code = f"zero_faces_{side}" if exc.face_count == 0 else f"multiple_faces_{side}"
            return None, code
        except (ImageLoadError, SimilarityError) as exc:
            return None, f"image_error_{side}:{exc}"

    for pair in pairs:
        left_embedding, left_failure = embed_side(pair.left_path, "left")
        if left_embedding is None:
            record(left_failure.split(":")[0])
            scored.append(PairScore(pair, None, left_failure))
            continue

        right_embedding, right_failure = embed_side(pair.right_path, "right")
        if right_embedding is None:
            record(right_failure.split(":")[0])
            scored.append(PairScore(pair, None, right_failure))
            continue

        similarity = cosine_similarity(left_embedding, right_embedding)
        scored.append(PairScore(pair, similarity, None))

    return EvaluationResult(total_pairs=len(pairs), scored_pairs=scored, failures=failures)


def summarize_metrics(result: EvaluationResult, threshold: float) -> Dict[str, object]:
    scores = result.valid_scores
    labels = result.valid_labels
    if not scores:
        raise ValueError("No pairs were successfully scored; cannot compute metrics.")

    matrix = metrics_module.confusion_matrix(scores, labels, threshold)
    rates = metrics_module.rates_from_confusion(matrix)
    auc = metrics_module.roc_auc(scores, labels)
    eer = metrics_module.equal_error_rate(scores, labels)

    return {
        "threshold": threshold,
        "total_pairs": result.total_pairs,
        "scored_pairs": len(scores),
        "failed_pairs": result.total_pairs - len(scores),
        "failure_rate": result.failure_rate,
        "failure_breakdown": dict(result.failures),
        "confusion_matrix": matrix.as_dict(),
        "accuracy": rates["accuracy"],
        "precision": rates["precision"],
        "recall": rates["recall"],
        "f1": rates["f1"],
        "false_match_rate": rates["false_match_rate"],
        "false_non_match_rate": rates["false_non_match_rate"],
        "roc_auc": auc,
        "equal_error_rate": eer["equal_error_rate"],
    }
