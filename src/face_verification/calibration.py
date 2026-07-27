"""Threshold calibration — strictly validation-split only.

The validation/held-out boundary is the single most important methodological
guarantee in this codebase (see docs/IMPLEMENTATION_PLAN.md). It is enforced
here in code, not only in documentation: ``calibrate`` refuses to run on
anything not explicitly labelled the validation split, and
``require_frozen`` refuses to let a held-out/final evaluation use a
threshold artifact that was not produced by calibration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence

from . import metrics as metrics_module
from .metrics import ThresholdCandidate

VALIDATION_SPLIT = "validation"
FROZEN_STATUS = "frozen"

DEFAULT_TARGET_FALSE_MATCH_RATES: Sequence[float] = (0.001, 0.01, 0.05)


class CalibrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CalibrationResult:
    split: str
    status: str
    candidates: Dict[str, ThresholdCandidate]


def calibrate(
    scores: Sequence[float],
    labels: Sequence[int],
    *,
    split: str,
    target_false_match_rates: Sequence[float] = DEFAULT_TARGET_FALSE_MATCH_RATES,
) -> CalibrationResult:
    if split != VALIDATION_SPLIT:
        raise CalibrationError(
            f"Calibration must only run on the '{VALIDATION_SPLIT}' split; got '{split}'. "
            f"This is enforced in code to prevent held-out/test-set leakage into threshold "
            f"selection, regardless of what the caller intended."
        )

    candidates: Dict[str, ThresholdCandidate] = {
        "balanced_accuracy": metrics_module.select_threshold(scores, labels, strategy="balanced_accuracy"),
        "f1": metrics_module.select_threshold(scores, labels, strategy="f1"),
        "eer": metrics_module.select_threshold(scores, labels, strategy="eer"),
    }
    for target in target_false_match_rates:
        candidates[f"target_fmr_{target}"] = metrics_module.select_threshold(
            scores, labels, strategy="target_fmr", target_false_match_rate=target
        )

    return CalibrationResult(split=split, status=FROZEN_STATUS, candidates=candidates)


def select_operating_threshold(result: CalibrationResult, *, strategy: str) -> float:
    """Pick one calibration candidate's threshold to become the single
    operating threshold used for every subsequent held-out evaluation."""
    if strategy not in result.candidates:
        raise CalibrationError(
            f"Unknown calibration strategy '{strategy}'; available: {sorted(result.candidates)}"
        )
    return result.candidates[strategy].threshold


def require_frozen_threshold(payload: Dict[str, Any], *, context: str = "") -> float:
    """Read a threshold out of a loaded threshold-artifact dict, refusing
    anything not explicitly marked frozen by ``calibrate``."""
    if payload.get("status") != FROZEN_STATUS:
        raise CalibrationError(
            f"{context}: threshold artifact status is '{payload.get('status')}', not "
            f"'{FROZEN_STATUS}'. Refusing to use a non-frozen threshold for a held-out "
            f"or final evaluation."
        )
    threshold = payload.get("threshold")
    if not isinstance(threshold, (int, float)):
        raise CalibrationError(f"{context}: threshold artifact is missing a numeric 'threshold' field")
    return float(threshold)
