from __future__ import annotations

import pytest

from face_verification.calibration import (
    CalibrationError,
    calibrate,
    require_frozen_threshold,
    select_operating_threshold,
)

SCORES = [0.95, 0.9, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1]
LABELS = [1, 1, 1, 0, 1, 0, 0, 0]


def test_calibration_accepts_validation_only():
    result = calibrate(SCORES, LABELS, split="validation")
    assert result.status == "frozen"
    assert "balanced_accuracy" in result.candidates
    assert "eer" in result.candidates
    assert "target_fmr_0.01" in result.candidates


@pytest.mark.parametrize("bad_split", ["held_out", "final", "test", "", "VALIDATION"])
def test_calibration_rejects_non_validation_split(bad_split):
    with pytest.raises(CalibrationError):
        calibrate(SCORES, LABELS, split=bad_split)


def test_select_operating_threshold_unknown_strategy_fails():
    result = calibrate(SCORES, LABELS, split="validation")
    with pytest.raises(CalibrationError):
        select_operating_threshold(result, strategy="not_a_real_strategy")


def test_require_frozen_threshold_rejects_non_frozen_status():
    with pytest.raises(CalibrationError):
        require_frozen_threshold({"status": "draft", "threshold": 0.5})
    with pytest.raises(CalibrationError):
        require_frozen_threshold({"status": "calibrating", "threshold": 0.5})


def test_require_frozen_threshold_accepts_frozen_status():
    assert require_frozen_threshold({"status": "frozen", "threshold": 0.42}) == pytest.approx(0.42)


def test_require_frozen_threshold_rejects_missing_numeric_threshold():
    with pytest.raises(CalibrationError):
        require_frozen_threshold({"status": "frozen", "threshold": "not-a-number"})
    with pytest.raises(CalibrationError):
        require_frozen_threshold({"status": "frozen"})
