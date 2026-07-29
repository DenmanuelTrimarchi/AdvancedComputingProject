"""scripts/generate_results_summary.py is a quick-look companion to the
dissertation-grade evidence pack: every number in it must be read from
results/aggregate/* at generation time, never hardcoded, and every figure
it embeds must actually exist and resolve from the summary file's own
location.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "generate_results_summary.py"


def _write_synthetic_aggregate(results_root: Path) -> None:
    results_root.mkdir(parents=True, exist_ok=True)

    rows = [
        "experiment,protocol_file,total_pairs,scored_pairs,failure_rate,threshold,accuracy,precision,"
        "recall,f1,false_match_rate,false_non_match_rate,roc_auc,equal_error_rate,"
        "embedding_time_mean_ms,embedding_time_median_ms,embedding_time_p95_ms"
    ]
    for name in ("lfw_development", "lfw_final", "cplfw"):
        rows.append(f"{name},protocol.txt,100,90,0.1,0.36,0.95,0.96,0.94,0.95,0.02,0.06,0.97,0.05,20.0,19.5,25.0")
    (results_root / "metrics_summary.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    confusion = ["experiment,true_positive,false_positive,true_negative,false_negative"]
    for name in ("lfw_development", "lfw_final", "cplfw"):
        confusion.append(f"{name},44,2,43,1")
    (results_root / "confusion_matrices.csv").write_text("\n".join(confusion) + "\n", encoding="utf-8")

    roc = ["experiment,threshold,false_match_rate,true_match_rate"]
    for name in ("lfw_development", "lfw_final", "cplfw"):
        roc.append(f"{name},0.2,0.5,0.9")
        roc.append(f"{name},0.5,0.1,0.7")
    (results_root / "roc_points.csv").write_text("\n".join(roc) + "\n", encoding="utf-8")

    (results_root / "lfw_development_metrics.json").write_text(json.dumps({"accuracy": 0.95}), encoding="utf-8")
    (results_root / "lfw_final_metrics.json").write_text(
        json.dumps({
            "accuracy": 0.95, "failure_rate": 0.1,
            "false_match_rate": 0.02, "false_non_match_rate": 0.06,
        }),
        encoding="utf-8",
    )

    (results_root / "cplfw_metrics.json").write_text(
        json.dumps({
            "accuracy": 0.90, "failure_rate": 0.1, "total_pairs": 100, "scored_pairs": 90,
            "failed_pairs": 10, "false_match_rate": 0.02, "false_non_match_rate": 0.06,
            "failure_breakdown": {"zero_faces_left": 4, "zero_faces_right": 3,
                                  "multiple_faces_left": 2, "multiple_faces_right": 1},
        }),
        encoding="utf-8",
    )
    (results_root / "duplicate_gallery_metrics.json").write_text(
        json.dumps({
            "gallery_size": 50, "duplicate_detection_rate": 0.9, "false_duplicate_review_rate": 0.2,
            "rank1_identification_rate": 0.85, "true_duplicate_miss_rate": 0.1,
            "gallery_search_time_mean_ms": 5.0, "gallery_search_time_p95_ms": 7.0,
        }),
        encoding="utf-8",
    )
    (results_root / "calibrated_threshold.json").write_text(
        json.dumps({
            "status": "frozen", "threshold": 0.36, "operating_strategy": "balanced_accuracy",
            "selection_evidence": {
                "balanced_accuracy": {"balanced_accuracy": 0.95, "false_match_rate": 0.02,
                                      "false_non_match_rate": 0.06, "threshold": 0.36},
                "f1": {"balanced_accuracy": 0.93, "false_match_rate": 0.04,
                      "false_non_match_rate": 0.05, "threshold": 0.31},
            },
        }),
        encoding="utf-8",
    )


def test_generates_summary_and_figures_from_scratch(tmp_path: Path):
    results_root = tmp_path / "aggregate"
    _write_synthetic_aggregate(results_root)
    figures_root = tmp_path / "evidence" / "figures"
    output = tmp_path / "RESULTS_SUMMARY.md"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--results-root", str(results_root),
         "--figures-root", str(figures_root), "--output", str(output)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert completed.returncode == 0, completed.stderr
    assert output.is_file()

    for name in ["figure_01_roc_comparison.png", "figure_06_gallery_outcomes.png",
                 "figure_09_experiment_flow.png"]:
        assert (figures_root / name).is_file()


def test_every_embedded_image_path_resolves(tmp_path: Path):
    results_root = tmp_path / "aggregate"
    _write_synthetic_aggregate(results_root)
    figures_root = tmp_path / "evidence" / "figures"
    output = tmp_path / "reports" / "RESULTS_SUMMARY.md"  # different directory depth on purpose

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--results-root", str(results_root),
         "--figures-root", str(figures_root), "--output", str(output)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert completed.returncode == 0, completed.stderr

    import re
    text = output.read_text(encoding="utf-8")
    image_paths = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    assert len(image_paths) == 9
    for relative in image_paths:
        resolved = (output.parent / relative).resolve()
        assert resolved.is_file(), f"embedded image does not resolve: {relative}"


def test_does_not_regenerate_figures_that_already_exist(tmp_path: Path):
    """Figures already present must be left alone, not silently recomputed
    (and re-timestamped) on every summary run."""
    results_root = tmp_path / "aggregate"
    _write_synthetic_aggregate(results_root)
    figures_root = tmp_path / "evidence" / "figures"
    output = tmp_path / "RESULTS_SUMMARY.md"

    first = subprocess.run(
        [sys.executable, str(SCRIPT), "--results-root", str(results_root),
         "--figures-root", str(figures_root), "--output", str(output)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert first.returncode == 0, first.stderr
    marker = figures_root / "figure_01_roc_comparison.png"
    original_mtime = marker.stat().st_mtime

    second = subprocess.run(
        [sys.executable, str(SCRIPT), "--results-root", str(results_root),
         "--figures-root", str(figures_root), "--output", str(output)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert second.returncode == 0, second.stderr
    assert marker.stat().st_mtime == original_mtime


def test_headline_numbers_are_derived_not_hardcoded(tmp_path: Path):
    results_root = tmp_path / "aggregate"
    _write_synthetic_aggregate(results_root)
    figures_root = tmp_path / "evidence" / "figures"
    output = tmp_path / "RESULTS_SUMMARY.md"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--results-root", str(results_root),
         "--figures-root", str(figures_root), "--output", str(output)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert completed.returncode == 0, completed.stderr

    text = output.read_text(encoding="utf-8")
    # These come from the synthetic fixture above, not the real project figures.
    assert "90.00%" in text  # cplfw accuracy
    assert "10.00%" in text  # cplfw failure_rate
    assert "986" not in text  # the real project's gallery size must not leak in
    assert "50" in text  # the synthetic gallery size
