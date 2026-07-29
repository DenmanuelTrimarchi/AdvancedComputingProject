"""Binary classification metrics for face-verification similarity scores.

Convention: label 1 = same identity ("match"), label 0 = different identity
("non-match"). Higher similarity is more match-like; the decision rule is
``score >= threshold => predicted match``. No scikit-learn dependency —
everything here is plain NumPy so the dependency contract stays small and
fully pinned.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np


class MetricsError(ValueError):
    pass


def percentile(values: Sequence[float], pct: float) -> float:
    """Linear-interpolation percentile (matches numpy's default method),
    with no numpy/scipy statistics dependency beyond the array itself."""
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    if len(ordered) == 1:
        return float(ordered[0])
    index = (pct / 100.0) * (len(ordered) - 1)
    lower, upper = int(index), min(int(index) + 1, len(ordered) - 1)
    if lower == upper:
        return float(ordered[lower])
    fraction = index - lower
    return float(ordered[lower] + fraction * (ordered[upper] - ordered[lower]))


@dataclass(frozen=True)
class ConfusionMatrix:
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int

    @property
    def total(self) -> int:
        return self.true_positive + self.false_positive + self.true_negative + self.false_negative

    def as_dict(self) -> Dict[str, int]:
        return {
            "true_positive": self.true_positive,
            "false_positive": self.false_positive,
            "true_negative": self.true_negative,
            "false_negative": self.false_negative,
        }


def _validate_inputs(scores: Sequence[float], labels: Sequence[int]) -> Tuple[np.ndarray, np.ndarray]:
    scores_arr = np.asarray(scores, dtype=np.float64)
    labels_arr = np.asarray(labels, dtype=np.int64)
    if scores_arr.shape[0] != labels_arr.shape[0]:
        raise MetricsError("scores and labels must have the same length")
    if scores_arr.shape[0] == 0:
        raise MetricsError("scores/labels must not be empty")
    if not np.all(np.isfinite(scores_arr)):
        raise MetricsError("scores must contain only finite numbers")
    unique_labels = set(np.unique(labels_arr).tolist())
    if not unique_labels.issubset({0, 1}):
        raise MetricsError(f"labels must be 0 or 1, found {sorted(unique_labels)}")
    if unique_labels != {0, 1}:
        raise MetricsError(
            f"labels must contain both classes (0 and 1); found only {sorted(unique_labels)}"
        )
    return scores_arr, labels_arr


def confusion_matrix(scores: Sequence[float], labels: Sequence[int], threshold: float) -> ConfusionMatrix:
    scores_arr, labels_arr = _validate_inputs(scores, labels)
    predicted_match = scores_arr >= threshold
    actual_match = labels_arr == 1

    return ConfusionMatrix(
        true_positive=int(np.sum(predicted_match & actual_match)),
        false_positive=int(np.sum(predicted_match & ~actual_match)),
        true_negative=int(np.sum(~predicted_match & ~actual_match)),
        false_negative=int(np.sum(~predicted_match & actual_match)),
    )


def rates_from_confusion(matrix: ConfusionMatrix) -> Dict[str, float]:
    positives = matrix.true_positive + matrix.false_negative
    negatives = matrix.true_negative + matrix.false_positive
    total = matrix.total

    accuracy = (matrix.true_positive + matrix.true_negative) / total if total else float("nan")
    precision = (
        matrix.true_positive / (matrix.true_positive + matrix.false_positive)
        if (matrix.true_positive + matrix.false_positive) > 0
        else float("nan")
    )
    recall = matrix.true_positive / positives if positives > 0 else float("nan")
    # A self-comparison is the NaN test here: an undefined rate must propagate
    # as NaN rather than silently contribute a zero to the derived metric.
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision == precision and recall == recall and (precision + recall) > 0
        else float("nan")
    )
    false_match_rate = matrix.false_positive / negatives if negatives > 0 else float("nan")
    false_non_match_rate = matrix.false_negative / positives if positives > 0 else float("nan")

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_match_rate": false_match_rate,
        "false_non_match_rate": false_non_match_rate,
        "true_match_rate": recall,
    }


def roc_points(scores: Sequence[float], labels: Sequence[int]) -> List[Dict[str, float]]:
    """ROC curve as ``{threshold, false_match_rate, true_match_rate}`` points,
    one per distinct score plus +/-1 sentinels, ordered by descending threshold."""
    scores_arr, labels_arr = _validate_inputs(scores, labels)
    thresholds = np.unique(scores_arr)[::-1]
    sentinel_high = float(thresholds[0]) + 1.0 if thresholds.size else 1.0
    sentinel_low = float(thresholds[-1]) - 1.0 if thresholds.size else -1.0
    all_thresholds = np.concatenate(([sentinel_high], thresholds, [sentinel_low]))

    points = []
    for threshold in all_thresholds:
        matrix = confusion_matrix(scores_arr, labels_arr, float(threshold))
        rates = rates_from_confusion(matrix)
        points.append(
            {
                "threshold": float(threshold),
                "false_match_rate": rates["false_match_rate"],
                "true_match_rate": rates["true_match_rate"],
            }
        )
    return points


def roc_auc(scores: Sequence[float], labels: Sequence[int]) -> float:
    """Rank-based ROC-AUC (Mann-Whitney U statistic), ties broken with
    average ranks. Equivalent to trapezoidal-rule AUC, no sklearn needed."""
    scores_arr, labels_arr = _validate_inputs(scores, labels)
    order = np.argsort(scores_arr, kind="mergesort")
    sorted_scores = scores_arr[order]
    ranks = np.empty(len(scores_arr), dtype=np.float64)

    n = len(sorted_scores)
    i = 0
    while i < n:
        j = i
        while j < n and sorted_scores[j] == sorted_scores[i]:
            j += 1
        average_rank = (i + 1 + j) / 2.0  # 1-indexed rank, averaged across the tie block
        ranks[order[i:j]] = average_rank
        i = j

    positive_mask = labels_arr == 1
    n_pos = int(np.sum(positive_mask))
    n_neg = int(len(labels_arr) - n_pos)
    if n_pos == 0 or n_neg == 0:
        raise MetricsError("roc_auc requires at least one example of each class")

    sum_ranks_positive = float(np.sum(ranks[positive_mask]))
    return float((sum_ranks_positive - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def equal_error_rate(scores: Sequence[float], labels: Sequence[int]) -> Dict[str, float]:
    """EER via linear interpolation between the ROC points bracketing
    false_match_rate == false_non_match_rate."""
    points = roc_points(scores, labels)

    best_gap: Optional[float] = None
    best_eer: Optional[float] = None
    best_threshold: Optional[float] = None
    previous: Optional[Tuple[float, float, float, float]] = None

    for point in points:
        fmr = point["false_match_rate"]
        fnmr = 1.0 - point["true_match_rate"]
        gap = fmr - fnmr
        if previous is not None:
            prev_fmr, _prev_fnmr, prev_gap, prev_threshold = previous
            crosses = (prev_gap <= 0 <= gap) or (prev_gap >= 0 >= gap)
            if crosses:
                if gap == prev_gap:
                    eer, threshold = fmr, point["threshold"]
                else:
                    ratio = prev_gap / (prev_gap - gap)
                    eer = prev_fmr + ratio * (fmr - prev_fmr)
                    threshold = prev_threshold + ratio * (point["threshold"] - prev_threshold)
                if best_gap is None or abs(gap) < best_gap:
                    best_gap, best_eer, best_threshold = abs(gap), eer, threshold
        previous = (fmr, fnmr, gap, point["threshold"])

    if best_eer is None:
        closest = min(points, key=lambda p: abs(p["false_match_rate"] - (1.0 - p["true_match_rate"])))
        best_eer = closest["false_match_rate"]
        best_threshold = closest["threshold"]

    return {"equal_error_rate": float(best_eer), "threshold": float(best_threshold)}


@dataclass(frozen=True)
class ThresholdCandidate:
    threshold: float
    strategy: str
    metrics: Dict[str, float]


def select_threshold(
    scores: Sequence[float],
    labels: Sequence[int],
    *,
    strategy: str,
    target_false_match_rate: Optional[float] = None,
) -> ThresholdCandidate:
    scores_arr, labels_arr = _validate_inputs(scores, labels)
    candidate_thresholds = np.unique(scores_arr)

    if strategy == "eer":
        eer_result = equal_error_rate(scores_arr, labels_arr)
        threshold = eer_result["threshold"]
        metrics = rates_from_confusion(confusion_matrix(scores_arr, labels_arr, threshold))
        metrics["equal_error_rate"] = eer_result["equal_error_rate"]
        return ThresholdCandidate(threshold, strategy, metrics)

    if strategy == "target_fmr":
        if target_false_match_rate is None:
            raise MetricsError("target_fmr strategy requires target_false_match_rate")
        best_threshold: Optional[float] = None
        best_metrics: Optional[Dict[str, float]] = None
        for threshold in sorted(candidate_thresholds, reverse=True):
            metrics = rates_from_confusion(confusion_matrix(scores_arr, labels_arr, float(threshold)))
            fmr = metrics["false_match_rate"]
            if fmr == fmr and fmr <= target_false_match_rate:
                best_threshold, best_metrics = float(threshold), metrics
            elif best_threshold is not None:
                break
        if best_threshold is None or best_metrics is None:
            raise MetricsError(f"No threshold achieves false_match_rate <= {target_false_match_rate}")
        return ThresholdCandidate(best_threshold, strategy, best_metrics)

    if strategy not in {"balanced_accuracy", "f1"}:
        raise MetricsError(f"Unknown threshold-selection strategy: {strategy}")

    best_threshold = None
    best_score = float("-inf")
    best_metrics = None
    for threshold in candidate_thresholds:
        metrics = rates_from_confusion(confusion_matrix(scores_arr, labels_arr, float(threshold)))
        if strategy == "balanced_accuracy":
            tmr = metrics["true_match_rate"]
            fmr = metrics["false_match_rate"]
            tnr = 1.0 - fmr if fmr == fmr else float("nan")
            score = (tmr + tnr) / 2.0 if tmr == tmr and tnr == tnr else float("-inf")
        else:
            score = metrics["f1"] if metrics["f1"] == metrics["f1"] else float("-inf")
        prefer_higher_on_tie = score == best_score and best_threshold is not None and threshold > best_threshold
        if score > best_score or prefer_higher_on_tie:
            best_score, best_threshold, best_metrics = score, float(threshold), metrics

    if best_threshold is None or best_metrics is None:
        raise MetricsError(f"Could not select a threshold using strategy={strategy}")
    return ThresholdCandidate(best_threshold, strategy, best_metrics)
