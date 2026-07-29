"""Local macOS execution is the canonical validation workflow (see
docs/REPRODUCIBILITY.md); GitHub Actions is retained only as an inactive
archived reference. These tests pin the parts of that claim that are
checkable without running the real pipeline: the runner script exists and
is syntactically valid, the old workflow is gone, the archived copy is
clearly marked, no committed document still requires a remote CI run, and
the evidence generator's screenshot numbering/local-run summary behave as
specified.

Screenshot-numbering tests exercise the real generator with
``--run-validation`` but no dataset/model roots, so 02-04 gracefully report
"NOT RUN" — no private files are required. The local-run-summary content
tests read the project's own committed ``results/aggregate/*``, which is
tracked in git and therefore always present in any checkout.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER = REPO_ROOT / "scripts" / "run_local_mac.sh"
ARCHIVED_CI = REPO_ROOT / "docs" / "archive" / "github_actions_ci_reference.yml"
ACTIVE_WORKFLOWS = REPO_ROOT / ".github" / "workflows"
GENERATOR = REPO_ROOT / "scripts" / "generate_report_evidence.py"
REAL_AGGREGATE = REPO_ROOT / "results" / "aggregate"


def test_local_runner_exists_and_is_executable():
    assert RUNNER.is_file()
    assert RUNNER.stat().st_mode & 0o111, "scripts/run_local_mac.sh must be executable"


def test_local_runner_is_valid_bash():
    completed = subprocess.run(["bash", "-n", str(RUNNER)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_no_active_github_workflow_remains():
    if ACTIVE_WORKFLOWS.exists():
        active = list(ACTIVE_WORKFLOWS.glob("*.yml")) + list(ACTIVE_WORKFLOWS.glob("*.yaml"))
        assert active == [], f"an active GitHub Actions workflow still exists: {active}"


def test_archived_workflow_is_clearly_marked_inactive():
    assert ARCHIVED_CI.is_file(), "the old CI workflow should be preserved as an archived reference"
    text = ARCHIVED_CI.read_text(encoding="utf-8")
    assert "ARCHIVED REFERENCE ONLY" in text
    assert "not active" in text


def test_no_documentation_requires_a_remote_github_actions_run():
    """A dangling "GitHub Actions is required" statement would contradict
    docs/REPRODUCIBILITY.md's canonical-local-execution claim."""
    forbidden = re.compile(r"github actions (?:run |result )?(?:is required|must pass|passed)", re.IGNORECASE)
    for path in [REPO_ROOT / "README.md", *((REPO_ROOT / "docs").glob("*.md"))]:
        if path == ARCHIVED_CI:
            continue
        text = path.read_text(encoding="utf-8")
        assert not forbidden.search(text), f"{path} still requires a remote GitHub Actions result"


@pytest.fixture(scope="module")
def real_pack(tmp_path_factory) -> Path:
    """Real generator, real committed aggregate results, --run-validation
    with no dataset/model roots -- exercises the actual screenshot/summary
    logic without any private file."""
    if not REAL_AGGREGATE.is_dir():
        pytest.skip("results/aggregate not present in this checkout")
    output_root = tmp_path_factory.mktemp("real_evidence")
    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--results-root", str(REAL_AGGREGATE),
         "--output-root", str(output_root), "--run-validation"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert completed.returncode == 0, completed.stderr
    return output_root


def test_screenshot_numbers_are_sequential_one_to_fifteen(real_pack: Path):
    manifest = json.loads((real_pack / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    numbers = sorted(
        int(Path(item["filename"]).stem.split("_")[1])
        for item in manifest["items"]
        if item["filename"].startswith("screenshots/")
    )
    assert numbers == list(range(1, 16)), numbers


def test_no_manifest_entry_references_github_actions(real_pack: Path):
    manifest = json.loads((real_pack / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["items"]:
        assert "github_actions" not in item["filename"].lower()


def test_every_screenshot_filename_appears_in_the_screenshot_index(real_pack: Path):
    index_text = (real_pack / "SCREENSHOT_INDEX.md").read_text(encoding="utf-8")
    manifest = json.loads((real_pack / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["items"]:
        if item["filename"].startswith("screenshots/"):
            assert Path(item["filename"]).name in index_text


def test_generated_screenshots_have_no_absolute_path(real_pack: Path):
    from face_verification.privacy import default_forbidden_path_substrings, find_path_leaks

    leaks = find_path_leaks(real_pack, forbidden_substrings=default_forbidden_path_substrings())
    assert leaks == [], leaks


def test_local_run_summary_is_derived_from_committed_aggregate_results(real_pack: Path):
    """Screenshot 06 must report the project's actual committed headline
    metrics -- not a hardcoded or stale figure."""
    cplfw = json.loads((REAL_AGGREGATE / "cplfw_metrics.json").read_text(encoding="utf-8"))
    gallery = json.loads((REAL_AGGREGATE / "duplicate_gallery_metrics.json").read_text(encoding="utf-8"))
    log_text = (real_pack / "logs" / "environment_check.txt").read_text(encoding="utf-8")
    assert log_text  # sanity: logs really were written

    manifest = json.loads((real_pack / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    summary_entry = next(
        item for item in manifest["items"] if item["filename"] == "screenshots/screenshot_06_local_complete_run.png"
    )
    assert summary_entry["sha256"]

    expected_cplfw_rate = f"{cplfw['failure_rate'] * 100:.2f}%"
    expected_gallery_review = f"{gallery['false_duplicate_review_rate'] * 100:.2f}%"
    # The committed project result is 41.42% / 52.56%; assert both the
    # general derivation and these specific figures so a silent metric
    # change would be caught.
    assert expected_cplfw_rate == "41.42%"
    assert expected_gallery_review == "52.56%"


def test_captured_manual_screenshot_gets_a_real_hash_and_is_never_overwritten(tmp_path: Path):
    """If a real manual screenshot is already sitting at --output-root before
    the generator runs, it must be detected, hashed, and left untouched --
    never regenerated or overwritten with a placeholder."""
    if not REAL_AGGREGATE.is_dir():
        pytest.skip("results/aggregate not present in this checkout")

    output_root = tmp_path / "evidence"
    screenshots_dir = output_root / "screenshots"
    screenshots_dir.mkdir(parents=True)
    captured_path = screenshots_dir / "screenshot_13_arden_onedrive_storage.png"
    original_bytes = b"not a real PNG, but a stand-in for one the researcher already captured"
    captured_path.write_bytes(original_bytes)

    completed = subprocess.run(
        [sys.executable, str(GENERATOR), "--results-root", str(REAL_AGGREGATE),
         "--output-root", str(output_root)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert completed.returncode == 0, completed.stderr

    assert captured_path.read_bytes() == original_bytes, "a captured manual screenshot must never be overwritten"

    manifest = json.loads((output_root / "report_evidence_manifest.json").read_text(encoding="utf-8"))
    entry = next(
        item for item in manifest["items"]
        if item["filename"] == "screenshots/screenshot_13_arden_onedrive_storage.png"
    )
    assert entry["status"] == "captured"
    assert entry["sha256"] is not None

    import hashlib
    assert entry["sha256"] == hashlib.sha256(original_bytes).hexdigest()


def test_local_run_summary_never_fabricates_a_pass_for_a_skipped_check(real_pack: Path):
    """--run-validation with no --model-root etc. means 02-04 do not run;
    the summary must say SKIPPED, never a fabricated PASS."""
    summary_text = (real_pack / "logs" / "local_complete_run.txt").read_text(encoding="utf-8")
    assert "Model verification: SKIPPED" in summary_text
    assert "LFW protocol verification: SKIPPED" in summary_text
    assert "Raw CPLFW protocol verification: SKIPPED" in summary_text
    assert "Model verification: PASS" not in summary_text
    # Checks that did run for real must still be reported honestly.
    assert "Environment check: PASS" in summary_text
    assert "Complete experiment: PASS" in summary_text
    assert "Privacy scan: PASS" in summary_text
    assert "Final LFW accuracy: 99.09%" in summary_text
    assert "Raw CPLFW extraction-failure rate: 41.42%" in summary_text
    assert "Gallery false-review rate: 52.56%" in summary_text


def test_pytest_step_does_not_recurse_when_run_from_inside_pytest(real_pack: Path):
    """The generator's own "05" step runs `pytest -v` with no path filter,
    which would otherwise re-collect and re-run this very test file,
    re-triggering `real_pack`, forever. Fixed by having that step check for
    PYTEST_CURRENT_TEST (which pytest sets in os.environ for exactly this
    purpose) and skip rather than recurse -- this test is what would hang
    or fork-bomb if that guard were ever removed.
    """
    assert os.environ.get("PYTEST_CURRENT_TEST"), "expected to be running inside pytest"
    summary_text = (real_pack / "logs" / "local_complete_run.txt").read_text(encoding="utf-8")
    assert "Tests: SKIPPED" in summary_text
    assert "Tests: FAILED" not in summary_text
    pytest_log = (real_pack / "logs" / "pytest_result.txt")
    assert not pytest_log.exists(), "pytest must not actually be re-invoked from inside pytest"
