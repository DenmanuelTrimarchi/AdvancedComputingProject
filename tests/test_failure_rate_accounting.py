"""The reported extraction-failure rate is only meaningful if every protocol
pair is accounted for exactly once, and if the rate is derived from those
counts rather than transcribed.

These tests pin the arithmetic, the accounting invariant, and the wording of
the human-readable rendering. They use synthetic counts only — no dataset or
model file is required.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from face_verification.protocols import Pair
from face_verification.verification_evaluator import EvaluationResult, PairScore

REPO_ROOT = Path(__file__).resolve().parent.parent
CPLFW_METRICS = REPO_ROOT / "results" / "aggregate" / "cplfw_metrics.json"


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "run_complete_experiment", REPO_ROOT / "scripts" / "run_complete_experiment.py"
    )
    assert spec is not None and spec.loader is not None, "run_complete_experiment.py is not importable"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pair(index: int) -> Pair:
    return Pair(Path(f"a_{index}.jpg"), Path(f"b_{index}.jpg"), index % 2 == 0, f"a{index}", f"b{index}")


def _result(*, scored: int, failed: int, failures: dict[str, int]) -> EvaluationResult:
    entries = [PairScore(_pair(i), 0.5, None) for i in range(scored)]
    entries += [PairScore(_pair(1000 + i), None, "zero_faces_left") for i in range(failed)]
    return EvaluationResult(total_pairs=scored + failed, scored_pairs=entries, failures=failures)


def test_scored_and_failed_pairs_sum_to_the_protocol_total():
    result = _result(scored=3515, failed=2485, failures={"zero_faces_left": 2485})
    assert result.scored_pair_count + result.failed_pairs == result.total_pairs == 6000


def test_failure_rate_is_derived_from_the_counts():
    result = _result(scored=3515, failed=2485, failures={"zero_faces_left": 2485})
    # Extraction failures stay in the denominator even though they have no score.
    assert result.failure_rate == pytest.approx(2485 / 6000)
    assert result.failure_rate == pytest.approx(0.4141666666666667)


def test_zero_total_pairs_does_not_divide_by_zero():
    empty = EvaluationResult(total_pairs=0, scored_pairs=[], failures={})
    rate = empty.failure_rate  # must not raise
    assert rate != rate, "an undefined rate should be NaN, not a fabricated 0.0"


def test_accounting_rejects_a_breakdown_that_does_not_partition_the_failures():
    # A breakdown summing to fewer pairs than failed means a failure was dropped.
    result = _result(scored=10, failed=5, failures={"zero_faces_left": 3})
    with pytest.raises(ValueError, match="exactly one extraction-failure category"):
        result.validate_accounting()


def test_accounting_accepts_a_correct_partition():
    result = _result(
        scored=3515, failed=2485,
        failures={"zero_faces_left": 974, "zero_faces_right": 1347,
                  "multiple_faces_left": 115, "multiple_faces_right": 49},
    )
    result.validate_accounting()  # must not raise
    assert sum(result.failures.values()) == result.failed_pairs == 2485


@pytest.mark.skipif(not CPLFW_METRICS.is_file(), reason="committed CPLFW result not present")
def test_committed_raw_cplfw_result_reconciles():
    payload = json.loads(CPLFW_METRICS.read_text(encoding="utf-8"))

    total = payload["total_pairs"]
    scored = payload["scored_pairs"]
    failed = payload["failed_pairs"]
    breakdown = payload["failure_breakdown"]

    assert payload["dataset_image_variant"] == "raw"
    assert scored + failed == total
    assert sum(breakdown.values()) == failed, "failure categories must account for every failed pair"
    assert payload["failure_rate"] == pytest.approx(failed / total)
    # The JSON keeps the full fraction; only reports round it.
    assert isinstance(payload["failure_rate"], float)


@pytest.mark.skipif(not CPLFW_METRICS.is_file(), reason="committed CPLFW result not present")
def test_percentage_rendering_matches_the_stored_fraction():
    runner = _load_runner()
    payload = json.loads(CPLFW_METRICS.read_text(encoding="utf-8"))
    assert runner._fmt_pct(payload["failure_rate"]) == "41.42%"
    assert runner._fmt_int(payload["total_pairs"]) == "6,000"
    assert runner._fmt_int(payload["scored_pairs"]) == "3,515"
    assert runner._fmt_int(payload["failed_pairs"]) == "2,485"


@pytest.mark.skipif(not CPLFW_METRICS.is_file(), reason="committed CPLFW result not present")
def test_breakdown_prose_names_every_category_and_never_drops_one():
    runner = _load_runner()
    payload = json.loads(CPLFW_METRICS.read_text(encoding="utf-8"))
    prose = runner._render_failure_breakdown(payload)

    for count in payload["failure_breakdown"].values():
        assert f"{count:,}" in prose, "every category count must appear in the prose"
    assert "left first" in prose, "the classification rule must be stated"
    assert "exactly one category" in prose


def test_breakdown_prose_surfaces_an_unexpected_category():
    """An unrecognised category must be reported, not silently dropped."""
    runner = _load_runner()
    prose = runner._render_failure_breakdown(
        {"failed_pairs": 7, "failure_breakdown": {"zero_faces_left": 4, "image_error_left": 3}}
    )
    assert "image_error_left" in prose
    assert "3" in prose
