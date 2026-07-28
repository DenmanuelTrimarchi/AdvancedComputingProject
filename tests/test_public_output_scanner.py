"""scripts/check_public_outputs.py is the gate that keeps a personal
filesystem path out of a committed result. These tests exercise the CLI
itself — the library-level behaviour of ``find_path_leaks`` is covered in
tests/test_artifact_privacy.py.

A scanner that exits 0 on a leak is worse than no scanner, so the failure
path is tested at least as carefully as the success path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_public_outputs.py"


def _scan(*paths: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--paths", *[str(p) for p in paths]],
        capture_output=True, text=True,
    )


def test_clean_outputs_pass(tmp_path: Path):
    (tmp_path / "run_manifest.json").write_text(
        '{"output_root": "results/aggregate", "dataset_root_variable": "FACE_DATA_ROOT"}',
        encoding="utf-8",
    )
    completed = _scan(tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert "OK" in completed.stdout


def test_absolute_path_fails_with_nonzero_exit(tmp_path: Path):
    (tmp_path / "run_manifest.json").write_text(
        '{"dataset_root": "/Users/someone/SecureResearchData/datasets"}', encoding="utf-8"
    )
    completed = _scan(tmp_path)
    assert completed.returncode != 0
    assert "run_manifest.json" in completed.stderr


def test_private_location_marker_fails_without_an_absolute_prefix(tmp_path: Path):
    # A bare storage-location name identifies the researcher's layout even
    # when it is not written as an absolute path.
    (tmp_path / "notes.md").write_text("Stored under SecureResearchData for the run.", encoding="utf-8")
    completed = _scan(tmp_path)
    assert completed.returncode != 0
    assert "SecureResearchData" in completed.stderr


def test_scans_every_supplied_path_not_just_the_first(tmp_path: Path):
    clean = tmp_path / "clean"
    dirty = tmp_path / "dirty"
    clean.mkdir()
    dirty.mkdir()
    (clean / "a.json").write_text('{"ok": true}', encoding="utf-8")
    (dirty / "b.json").write_text('{"root": "/Users/someone/data"}', encoding="utf-8")

    completed = _scan(clean, dirty)
    assert completed.returncode != 0
    assert "b.json" in completed.stderr


def test_missing_path_is_an_error_not_a_silent_pass(tmp_path: Path):
    # A typo'd path must never be reported as "clean".
    completed = _scan(tmp_path / "does_not_exist")
    assert completed.returncode != 0
    assert "does not exist" in completed.stderr


def test_committed_public_outputs_are_clean():
    """The repository's own committed outputs must pass their own gate."""
    repo_root = SCRIPT.resolve().parent.parent
    roots = [repo_root / "results" / name for name in ("aggregate", "report_evidence", "historical")]
    existing = [root for root in roots if root.exists()]
    assert existing, "no committed public output directories found"

    completed = _scan(*existing)
    assert completed.returncode == 0, completed.stderr
