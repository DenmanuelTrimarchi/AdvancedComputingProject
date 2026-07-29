"""Scores an LFW/CPLFW-style pair protocol end to end and reports metrics.

Face-extraction failures (zero or multiple detected faces, unreadable
images) are recorded as their own explicit outcome category and reported
alongside the accuracy metrics — never silently dropped from the pair count.
Per-image embedding latency (detect + align + embed + normalise) is timed
for every successfully processed image, so throughput can be reported
alongside accuracy rather than only inferred from wall-clock script runtime.
"""

from __future__ import annotations

import statistics
import time
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
    embedding_times_seconds: List[float] = field(default_factory=list)

    @property
    def valid_scores(self) -> List[float]:
        return [s.similarity for s in self.scored_pairs if s.similarity is not None]

    @property
    def valid_labels(self) -> List[int]:
        return [1 if s.pair.same_identity else 0 for s in self.scored_pairs if s.similarity is not None]

    @property
    def scored_pair_count(self) -> int:
        # Only pairs yielding one valid face on both sides carry a similarity score.
        return len(self.valid_scores)

    @property
    def failed_pairs(self) -> int:
        # Failed pairs stay within the protocol total; they simply have no score.
        return self.total_pairs - self.scored_pair_count

    @property
    def failure_rate(self) -> float:
        # Stored as a fraction of the full protocol; reports render the percentage.
        return self.failed_pairs / self.total_pairs if self.total_pairs else float("nan")

    def validate_accounting(self) -> None:
        """Confirm that every protocol pair is accounted for exactly once.

        Guards the reported denominator: the failure rate is only meaningful
        if no pair has been silently discarded, and if the per-category
        breakdown describes precisely the pairs that failed.
        """
        if self.scored_pair_count + self.failed_pairs != self.total_pairs:
            raise ValueError(
                f"Scored ({self.scored_pair_count}) and failed ({self.failed_pairs}) pairs must sum "
                f"to the protocol total ({self.total_pairs})."
            )
        # evaluate_pairs records exactly one terminal category per failed pair,
        # so the breakdown is a partition of the failures, not a tally per image.
        categorised = sum(self.failures.values())
        if categorised != self.failed_pairs:
            raise ValueError(
                f"Failure breakdown totals {categorised} but {self.failed_pairs} pairs failed; "
                f"every failed pair must carry exactly one extraction-failure category."
            )


def _embed_image(
    path: Path,
    detector: YuNetDetector,
    embedder: SFaceEmbedder,
    cache: Dict[Path, np.ndarray],
    embedding_times: List[float],
) -> np.ndarray:
    if path in cache:
        return cache[path]
    start = time.perf_counter()
    loaded = load_image_bgr(path)
    face_row = detector.detect_single_face(loaded.bgr)
    raw_embedding = embedder.embed(loaded.bgr, face_row)
    normalized = l2_normalize(raw_embedding)
    embedding_times.append(time.perf_counter() - start)
    cache[path] = normalized
    return normalized


def evaluate_pairs(pairs: List[Pair], *, detector: YuNetDetector, embedder: SFaceEmbedder) -> EvaluationResult:
    scored: List[PairScore] = []
    failures: Dict[str, int] = {}
    cache: Dict[Path, np.ndarray] = {}
    embedding_times: List[float] = []

    def record(code: str) -> None:
        failures[code] = failures.get(code, 0) + 1

    def embed_side(path: Path, side: str) -> "tuple[Optional[np.ndarray], Optional[str]]":
        try:
            return _embed_image(path, detector, embedder, cache, embedding_times), None
        except FaceCountError as exc:
            code = f"zero_faces_{side}" if exc.face_count == 0 else f"multiple_faces_{side}"
            return None, code
        except (ImageLoadError, SimilarityError) as exc:
            return None, f"image_error_{side}:{exc}"

    for pair in pairs:
        # Sides are attempted left first and the pair is abandoned on the first
        # terminal failure, so each failed pair records exactly one category.
        # Consequently a "_right" category means the right image failed *after*
        # the left had already yielded one valid face: where both sides would
        # fail, only the left is ever counted. The four categories therefore
        # partition the failed pairs; they are not per-image failure tallies.
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

    return EvaluationResult(
        total_pairs=len(pairs), scored_pairs=scored, failures=failures, embedding_times_seconds=embedding_times
    )


def summarize_metrics(result: EvaluationResult, threshold: float) -> Dict[str, object]:
    scores = result.valid_scores
    labels = result.valid_labels
    if not scores:
        raise ValueError("No pairs were successfully scored; cannot compute metrics.")

    # Refuse to publish a failure rate whose denominator does not reconcile.
    result.validate_accounting()

    matrix = metrics_module.confusion_matrix(scores, labels, threshold)
    rates = metrics_module.rates_from_confusion(matrix)
    auc = metrics_module.roc_auc(scores, labels)
    eer = metrics_module.equal_error_rate(scores, labels)
    roc_points = metrics_module.roc_points(scores, labels)

    times_ms = [t * 1000.0 for t in result.embedding_times_seconds]

    return {
        "threshold": threshold,
        "total_pairs": result.total_pairs,
        # Score-based metrics below are conditional on these scored pairs alone.
        "scored_pairs": result.scored_pair_count,
        "failed_pairs": result.failed_pairs,
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
        "roc_points": roc_points,
        "embedding_time_mean_ms": statistics.fmean(times_ms) if times_ms else float("nan"),
        "embedding_time_median_ms": statistics.median(times_ms) if times_ms else float("nan"),
        "embedding_time_p95_ms": metrics_module.percentile(times_ms, 95) if times_ms else float("nan"),
        "unique_images_embedded": len(times_ms),
    }
