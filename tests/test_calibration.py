from __future__ import annotations

import pytest

from face_verification.calibration import (
    CalibrationError,
    calibrate,
    require_candidates,
    require_frozen_threshold,
    select_final_threshold,
)

TRAIN_SCORES = [0.95, 0.9, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1]
TRAIN_LABELS = [1, 1, 1, 0, 1, 0, 0, 0]


def test_calibration_produces_candidates_not_a_frozen_choice():
    result = calibrate(TRAIN_SCORES, TRAIN_LABELS, split="validation")
    assert result.status == "candidates"
    assert "balanced_accuracy" in result.candidates
    assert "eer" in result.candidates
    assert "target_fmr_0.01" in result.candidates


@pytest.mark.parametrize("bad_split", ["held_out", "final", "test", "", "VALIDATION"])
def test_calibration_rejects_non_validation_split(bad_split):
    with pytest.raises(CalibrationError):
        calibrate(TRAIN_SCORES, TRAIN_LABELS, split=bad_split)


def test_require_candidates_rejects_frozen_status():
    with pytest.raises(CalibrationError):
        require_candidates({"status": "frozen", "candidates": {"x": {"threshold": 0.5}}})


def test_require_candidates_rejects_empty_candidates():
    with pytest.raises(CalibrationError):
        require_candidates({"status": "candidates", "candidates": {}})


def test_require_candidates_accepts_well_formed_artifact():
    candidates = require_candidates({"status": "candidates", "candidates": {"x": {"threshold": 0.5}}})
    assert candidates == {"x": {"threshold": 0.5}}


def test_select_final_threshold_picks_best_development_balanced_accuracy():
    # Two candidates from "calibration": 0.5 separates the dev data perfectly,
    # 0.9 is far too strict and misses every true match on dev.
    candidates = {"loose": {"threshold": 0.5}, "strict": {"threshold": 0.9}}
    dev_scores = [0.8, 0.7, 0.3, 0.2]
    dev_labels = [1, 1, 0, 0]

    outcome = select_final_threshold(candidates, dev_scores, dev_labels)
    assert outcome["selected_candidate"] == "loose"
    assert outcome["selected_threshold"] == pytest.approx(0.5)
    assert set(outcome["all_candidates_dev_metrics"]) == {"loose", "strict"}
    assert outcome["all_candidates_dev_metrics"]["loose"]["balanced_accuracy"] == pytest.approx(1.0)


def test_select_final_threshold_breaks_exact_ties_deterministically_by_name():
    # Both candidates round to the identical threshold value, so their
    # development-split metrics (balanced accuracy, false match rate) are
    # byte-identical; only the documented name tie-break can decide.
    candidates = {"zeta": {"threshold": 0.5}, "alpha": {"threshold": 0.5}}
    dev_scores = [0.9, 0.8, 0.4, 0.1]
    dev_labels = [1, 1, 0, 0]

    outcome = select_final_threshold(candidates, dev_scores, dev_labels)
    assert outcome["selected_candidate"] == "alpha"


def test_select_final_threshold_rejects_empty_candidates():
    with pytest.raises(CalibrationError):
        select_final_threshold({}, [0.5], [1])


def test_require_frozen_threshold_rejects_non_frozen_status():
    with pytest.raises(CalibrationError):
        require_frozen_threshold({"status": "candidates", "threshold": 0.5})
    with pytest.raises(CalibrationError):
        require_frozen_threshold({"status": "draft", "threshold": 0.5})


def test_require_frozen_threshold_accepts_frozen_status():
    assert require_frozen_threshold({"status": "frozen", "threshold": 0.42}) == pytest.approx(0.42)


def test_require_frozen_threshold_rejects_missing_numeric_threshold():
    with pytest.raises(CalibrationError):
        require_frozen_threshold({"status": "frozen", "threshold": "not-a-number"})
    with pytest.raises(CalibrationError):
        require_frozen_threshold({"status": "frozen"})
