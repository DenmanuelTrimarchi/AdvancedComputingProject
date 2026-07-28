"""scripts/generate_report_evidence.py must derive every figure from the
committed aggregate outputs alone, never from a hardcoded metric value, and
must never let a private absolute path reach the generated pack.

Exercised against small synthetic fixtures — never real benchmark data.
Skipped entirely if the optional 'report' extra is not installed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("matplotlib")

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "generate_report_evidence.py"

EXPECTED_FIGURES = [
    "figure_01_roc_comparison.png",
    "figure_02_lfw_final_confusion_matrix.png",
    "figure_03_cplfw_confusion_matrix.png",
    "figure_04_extraction_failure_rates.png",
    "figure_05_cplfw_failure_breakdown.png",
    "figure_06_gallery_outcomes.png",
    "figure_07_threshold_candidate_comparison.png",
    "figure_08_latency_comparison.png",
    "figure_09_experiment_flow.png",
]

EXPERIMENTS = ["lfw_development", "lfw_final", "cplfw"]

SUMMARY_FIELDS = (
    "protocol_file,total_pairs,scored_pairs,failure_rate,threshold,accuracy,precision,recall,f1,"
    "false_match_rate,false_non_match_rate,roc_auc,equal_error_rate,embedding_time_mean_ms,"
    "embedding_time_median_ms,embedding_time_p95_ms"
)


def _write_synthetic_aggregate(results_root: Path) -> None:
    results_root.mkdir(parents=True, exist_ok=True)

    rows = ["experiment," + SUMMARY_FIELDS]
    for name in EXPERIMENTS:
        rows.append(
            f"{name},protocol.txt,100,90,0.1,0.36,0.95,0.96,0.94,0.95,"
            f"0.02,0.06,0.97,0.05,20.0,19.5,25.0"
        )
    (results_root / "metrics_summary.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")

    confusion = ["experiment,true_positive,false_positive,true_negative,false_negative"]
    for name in EXPERIMENTS:
        confusion.append(f"{name},44,2,43,1")
    (results_root / "confusion_matrices.csv").write_text("\n".join(confusion) + "\n", encoding="utf-8")

    roc = ["experiment,threshold,false_match_rate,true_match_rate"]
    for name in EXPERIMENTS:
        roc.append(f"{name},0.2,0.5,0.9")
        roc.append(f"{name},0.5,0.1,0.7")
    (results_root / "roc_points.csv").write_text("\n".join(roc) + "\n", encoding="utf-8")

    (results_root / "cplfw_metrics.json").write_text(
        json.dumps({
            "dataset_image_variant": "raw",
            "dataset_image_source": "authors-distributed images.rar",
            "dataset_archive_sha256": "0" * 64,
            "protocol_file": "pairs_CPLFW.txt",
            "protocol_sha256": "1" * 64,
            "total_pairs": 100,
            "scored_pairs": 90,
            "failed_pairs": 10,
            "failure_rate": 0.1,
            "failure_breakdown": {
                "zero_faces_left": 4, "zero_faces_right": 3,
                "multiple_faces_left": 2, "multiple_faces_right": 1,
            },
        }),
        encoding="utf-8",
    )
    (results_root / "duplicate_gallery_metrics.json").write_text(
        json.dumps({
            "gallery_size": 50,
            "duplicate_detection_rate": 0.9,
            "rank1_identification_rate": 0.85,
            "true_duplicate_miss_rate": 0.1,
            "false_duplicate_review_rate": 0.2,
            "gallery_search_time_mean_ms": 5.0,
            "gallery_search_time_p95_ms": 7.0,
        }),
        encoding="utf-8",
    )
    (results_root / "calibrated_threshold.json").write_text(
        json.dumps({
            "status": "frozen",
            "threshold": 0.36,
            "operating_strategy": "balanced_accuracy",
            "frozen_from_protocol": "pairsDevTest.txt",
            "frozen_from_protocol_sha256": "2" * 64,
            "selection_rule": "Maximum balanced accuracy; ties by lower FMR, then candidate name.",
            "selection_evidence": {
                "balanced_accuracy": {
                    "balanced_accuracy": 0.95, "false_match_rate": 0.02,
                    "false_non_match_rate": 0.06, "threshold": 0.36,
                },
                "f1": {
                    "balanced_accuracy": 0.93, "false_match_rate": 0.04,
                    "false_non_match_rate": 0.05, "threshold": 0.31,
                },
            },
        }),
        encoding="utf-8",
    )


@pytest.fixture
def synthetic_aggregate(tmp_path: Path) -> Path:
    results_root = tmp_path / "aggregate"
    _write_synthetic_aggregate(results_root)
    return results_root


def _generate(results_root: Path, output_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--results-root", str(results_root),
         "--output-root", str(output_root), *extra],
        capture_output=True, text=True,
    )


def test_generates_all_nine_figures(tmp_path: Path, synthetic_aggregate: Path):
    output_root = tmp_path / "evidence"
    completed = _generate(synthetic_aggregate, output_root)
    assert completed.returncode == 0, completed.stderr

    for name in EXPECTED_FIGURES:
        assert (output_root / "figures" / name).is_file(), f"missing {name}"


def test_generates_index_manifest_and_manual_screenshot_doc(tmp_path: Path, synthetic_aggregate: Path):
    output_root = tmp_path / "evidence"
    assert _generate(synthetic_aggregate, output_root).returncode == 0

    assert (output_root / "REPORT_EVIDENCE_INDEX.md").is_file()
    assert (output_root / "manual_screenshots_required.md").is_file()

    manifest = json.loads((output_root / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifact_type"] == "report_evidence_manifest"

    figures = [item for item in manifest["items"] if item["type"] == "figure"]
    assert len(figures) == len(EXPECTED_FIGURES)
    for item in figures:
        assert item["sha256"], f"figure entry has no hash: {item['filename']}"
        assert item["source_file_sha256"], f"figure entry records no source hash: {item['filename']}"
        assert item["contains_real_face_image"] is False
        assert item["contains_absolute_path"] is False


def test_manual_screenshots_are_declared_pending_never_fabricated(tmp_path: Path, synthetic_aggregate: Path):
    output_root = tmp_path / "evidence"
    assert _generate(synthetic_aggregate, output_root).returncode == 0

    manifest = json.loads((output_root / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    manual = [item for item in manifest["items"] if item["type"] == "manual_screenshot"]
    assert manual, "manual screenshots should be declared"
    for item in manual:
        assert item["sha256"] is None
        assert "awaiting manual capture" in item["status"]
        # The generator must not have written a look-alike placeholder image.
        assert not (output_root / item["filename"]).exists()


def test_index_and_manifest_agree(tmp_path: Path, synthetic_aggregate: Path):
    output_root = tmp_path / "evidence"
    assert _generate(synthetic_aggregate, output_root).returncode == 0

    manifest = json.loads((output_root / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    index_text = (output_root / "REPORT_EVIDENCE_INDEX.md").read_text(encoding="utf-8")
    for item in manifest["items"]:
        assert item["filename"] in index_text, f"{item['filename']} missing from the evidence index"


def test_fails_loudly_on_missing_aggregate_input(tmp_path: Path):
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    completed = _generate(empty_root, tmp_path / "evidence")
    assert completed.returncode != 0
    assert "missing" in completed.stderr.lower()


def test_fails_loudly_on_incomplete_aggregate_field(tmp_path: Path, synthetic_aggregate: Path):
    # Drop a required field: the generator must refuse rather than draw a
    # partial chart with a silently-defaulted value.
    payload = json.loads((synthetic_aggregate / "duplicate_gallery_metrics.json").read_text(encoding="utf-8"))
    del payload["false_duplicate_review_rate"]
    (synthetic_aggregate / "duplicate_gallery_metrics.json").write_text(json.dumps(payload), encoding="utf-8")

    completed = _generate(synthetic_aggregate, tmp_path / "evidence")
    assert completed.returncode != 0
    assert "false_duplicate_review_rate" in completed.stderr


def test_manifest_records_source_provenance_not_a_false_containment_claim(
    tmp_path: Path, synthetic_aggregate: Path
):
    """The pack is generated *from* a source commit and added by a later one.
    The manifest must say that, and must never imply the evidence files
    already existed at the commit it names."""
    output_root = tmp_path / "evidence"
    assert _generate(synthetic_aggregate, output_root).returncode == 0

    manifest = json.loads((output_root / "report_evidence_manifest.json").read_text(encoding="utf-8"))

    assert "source_git_commit" in manifest
    assert "source_working_tree_clean_before_generation" in manifest
    assert isinstance(manifest["source_working_tree_clean_before_generation"], bool)
    assert "evidence_generated_outside_repository" in manifest

    # The old field implied the evidence belonged to that commit.
    assert "git_working_tree_dirty" not in manifest

    note = manifest["provenance_note"]
    assert "subsequent commit" in note, "the manifest must state the evidence is added later"


def test_generating_outside_the_repository_is_recorded(tmp_path: Path, synthetic_aggregate: Path):
    output_root = tmp_path / "evidence"  # tmp_path is outside the repo
    assert _generate(synthetic_aggregate, output_root).returncode == 0

    manifest = json.loads((output_root / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    assert manifest["evidence_generated_outside_repository"] is True


def test_source_files_are_labelled_unambiguously(tmp_path: Path, synthetic_aggregate: Path):
    """A bare basename is ambiguous provenance — the same filename occurs
    under several roots. Sources inside the repo must be labelled
    repo-relative; sources outside it fall back to a basename but must never
    be an absolute path."""
    output_root = tmp_path / "evidence"
    assert _generate(synthetic_aggregate, output_root).returncode == 0

    manifest = json.loads((output_root / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["items"]:
        for label in item["source_files"]:
            assert not label.startswith("/"), f"absolute source label: {label}"
            assert not label.startswith("~"), f"home-relative source label: {label}"
        assert set(item["source_files"]) == set(item["source_file_sha256"]), (
            f"{item['filename']}: source_files and source_file_sha256 disagree"
        )


def test_generated_pack_contains_no_absolute_path(tmp_path: Path, synthetic_aggregate: Path):
    from face_verification.privacy import default_forbidden_path_substrings, find_path_leaks

    output_root = tmp_path / "evidence"
    assert _generate(synthetic_aggregate, output_root).returncode == 0

    leaks = find_path_leaks(output_root, forbidden_substrings=default_forbidden_path_substrings())
    assert leaks == [], f"private path leaked into the evidence pack: {leaks}"
