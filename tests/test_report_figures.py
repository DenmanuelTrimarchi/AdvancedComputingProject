"""scripts/generate_report_figures.py must derive every figure from the
committed aggregate outputs alone, never from a hardcoded metric value.
Exercised here against small synthetic fixtures — never real benchmark
data — with matplotlib skipped entirely if the optional 'report' extra
is not installed (see pyproject.toml).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_report_figures.py"

EXPECTED_FIGURES = [
    "roc_comparison.png",
    "lfw_final_confusion_matrix.png",
    "cplfw_confusion_matrix.png",
    "extraction_failure_rates.png",
    "cplfw_failure_breakdown.png",
    "gallery_outcomes.png",
    "threshold_candidate_comparison.png",
]


def _write_verification_fixture(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "confusion_matrix": {
                    "true_positive": 10, "false_positive": 1, "true_negative": 12, "false_negative": 2,
                },
                "failure_rate": 0.1,
                "scored_pairs": 25,
                "total_pairs": 28,
                "roc_points": [
                    {"threshold": 0.2, "false_match_rate": 0.5, "true_match_rate": 0.9},
                    {"threshold": 0.5, "false_match_rate": 0.1, "true_match_rate": 0.7},
                ],
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def synthetic_aggregate(tmp_path: Path) -> Path:
    results_root = tmp_path / "aggregate"
    results_root.mkdir()

    for name in ("lfw_development", "lfw_final", "cplfw"):
        _write_verification_fixture(results_root / f"{name}_metrics.json")

    (results_root / "duplicate_gallery_metrics.json").write_text(
        json.dumps(
            {
                "gallery_size": 50,
                "duplicate_detection_rate": 0.9,
                "rank1_identification_rate": 0.85,
                "true_duplicate_miss_rate": 0.1,
                "false_duplicate_review_rate": 0.2,
                "policy_note": "A result above threshold opens a case for human review only.",
            }
        ),
        encoding="utf-8",
    )
    (results_root / "calibrated_threshold.json").write_text(
        json.dumps(
            {
                "operating_strategy": "balanced_accuracy",
                "selection_evidence": {
                    "balanced_accuracy": {"balanced_accuracy": 0.95},
                    "f1": {"balanced_accuracy": 0.93},
                },
            }
        ),
        encoding="utf-8",
    )
    return results_root


def test_generates_all_seven_figures(tmp_path: Path, synthetic_aggregate: Path):
    output_root = tmp_path / "figures"
    completed = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--results-root", str(synthetic_aggregate),
            "--output-root", str(output_root),
        ],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr

    for name in EXPECTED_FIGURES:
        assert (output_root / name).is_file(), f"missing {name}"


def test_fails_loudly_on_missing_input(tmp_path: Path):
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    completed = subprocess.run(
        [
            sys.executable, str(SCRIPT),
            "--results-root", str(empty_root),
            "--output-root", str(tmp_path / "figures"),
        ],
        capture_output=True, text=True,
    )
    assert completed.returncode != 0
    assert "missing" in completed.stderr.lower()
