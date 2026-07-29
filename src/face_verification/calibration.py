"""Two-stage threshold calibration — strictly validation-split, then
development-split selection.

The validation/held-out boundary is the single most important methodological
guarantee in this codebase (see docs/IMPLEMENTATION_PLAN.md), enforced here
in code rather than only in documentation, across two distinct stages:

1. ``calibrate`` (run against ``pairsDevTrain.txt`` only) generates a table
   of *candidate* thresholds. It never itself picks a winner — the result's
   status is ``"candidates"``, not ``"frozen"``.
2. ``select_final_threshold`` (run against ``pairsDevTest.txt`` only)
   evaluates every candidate on the development split and selects exactly
   one, by a fixed, documented, fully deterministic rule. Only this step's
   output is marked ``"frozen"``.

``require_frozen_threshold`` refuses to let a final/held-out evaluation
(LFW ``pairs.txt``, CPLFW) use anything that has not been through step 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence

from . import metrics as metrics_module
from .metrics import ThresholdCandidate

VALIDATION_SPLIT = "validation"
CANDIDATES_STATUS = "candidates"
FROZEN_STATUS = "frozen"

DEFAULT_TARGET_FALSE_MATCH_RATES: Sequence[float] = (0.001, 0.01, 0.05)

SELECTION_RULE = (
    "Maximum balanced accuracy on the development split (pairsDevTest.txt); "
    "ties broken by lower development-split false match rate, then by "
    "candidate name, for full determinism."
)


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
    """Stage 1: generate candidate thresholds from the validation split only.

    Deliberately does not select a winner — see module docstring.
    """
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

    return CalibrationResult(split=split, status=CANDIDATES_STATUS, candidates=candidates)


def require_candidates(payload: Dict[str, Any], *, context: str = "") -> Dict[str, Dict[str, Any]]:
    """Read the candidate-threshold table out of a loaded artifact dict,
    refusing anything already frozen (or never calibrated) — this is the
    Stage-2 entry point's guard, mirroring ``require_frozen_threshold`` for
    Stage 3."""
    if payload.get("status") != CANDIDATES_STATUS:
        raise CalibrationError(
            f"{context}: threshold artifact status is '{payload.get('status')}', not "
            f"'{CANDIDATES_STATUS}'. Expected an artifact produced by calibrate_lfw.py that "
            f"has not yet been frozen by a development-split selection step."
        )
    candidates = payload.get("candidates")
    if not isinstance(candidates, dict) or not candidates:
        raise CalibrationError(f"{context}: threshold artifact has no candidates to select from")
    return candidates


def select_final_threshold(
    candidates: Dict[str, Dict[str, Any]],
    dev_scores: Sequence[float],
    dev_labels: Sequence[int],
) -> Dict[str, Any]:
    """Stage 2: evaluate every Stage-1 candidate against development-split
    scores and select exactly one, by ``SELECTION_RULE``. Returns the
    selection outcome plus every candidate's development-set metrics, so the
    choice is fully auditable rather than a black box."""
    if not candidates:
        raise CalibrationError("No candidate thresholds to select from")

    per_candidate_dev_metrics: Dict[str, Dict[str, float]] = {}
    for name, candidate in candidates.items():
        threshold = float(candidate["threshold"])
        matrix = metrics_module.confusion_matrix(dev_scores, dev_labels, threshold)
        rates = metrics_module.rates_from_confusion(matrix)
        tmr, fmr = rates["true_match_rate"], rates["false_match_rate"]
        # Self-comparison is the NaN test; an unscorable candidate sorts last
        # rather than winning the selection by accident.
        balanced_accuracy = (tmr + (1.0 - fmr)) / 2.0 if tmr == tmr and fmr == fmr else float("-inf")
        per_candidate_dev_metrics[name] = {**rates, "threshold": threshold, "balanced_accuracy": balanced_accuracy}

    def sort_key(name: str):
        metrics = per_candidate_dev_metrics[name]
        return (-metrics["balanced_accuracy"], metrics["false_match_rate"], name)

    selected_name = min(per_candidate_dev_metrics, key=sort_key)
    selected = per_candidate_dev_metrics[selected_name]

    return {
        "selected_candidate": selected_name,
        "selected_threshold": selected["threshold"],
        "selection_rule": SELECTION_RULE,
        "all_candidates_dev_metrics": per_candidate_dev_metrics,
    }


def require_frozen_threshold(payload: Dict[str, Any], *, context: str = "") -> float:
    """Stage 3 entry point's guard: read a threshold out of a loaded
    artifact dict, refusing anything not explicitly marked frozen by
    ``select_final_threshold``."""
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
