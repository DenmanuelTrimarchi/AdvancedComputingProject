"""Tests for scripts/check_comment_style.py.

A style checker that never fires is indistinguishable from no checker at all,
so every rule is tested from both sides: a violation must be reported, and the
constructs it could plausibly confuse — URLs, glob patterns, floor division,
identifiers quoted in prose — must not be.

Each test builds a throwaway Git repository because the checker deliberately
audits tracked files only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from check_comment_style import audit, main, strip_quoted_strings  # noqa: E402


def make_repo(root: Path, files: Dict[str, str]) -> Path:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


def rules(root: Path) -> List[str]:
    return [violation.rule for violation in audit(root)]


# --------------------------------------------------------------------------
# Prohibited comment syntax
# --------------------------------------------------------------------------


def test_cpp_style_comment_in_shell_is_reported(tmp_path: Path):
    make_repo(tmp_path, {"run.sh": "#!/usr/bin/env bash\n// this should be a hash comment\necho hi\n"})
    assert "prohibited-comment-syntax" in rules(tmp_path)


def test_block_comment_in_yaml_is_reported(tmp_path: Path):
    make_repo(tmp_path, {"c.yaml": "key: value\n/* not a YAML comment */\n"})
    assert "prohibited-comment-syntax" in rules(tmp_path)


def test_html_comment_in_toml_is_reported(tmp_path: Path):
    make_repo(tmp_path, {"p.toml": "<!-- not a TOML comment -->\nkey = 1\n"})
    assert "prohibited-comment-syntax" in rules(tmp_path)


@pytest.mark.parametrize(
    "name,content",
    [
        ("u.yaml", "docs: https://github.com/opencv/opencv_zoo\n"),
        ("g.sh", '#!/usr/bin/env bash\nfind . -not -path "./.git/*" -print\n'),
        ("glob.sh", "#!/usr/bin/env bash\nrm -rf results/raw/*\n"),
        ("div.py", "value = 44\nhead = value // 2\n"),
        ("subst.sh", '#!/usr/bin/env bash\npath="${name//a/b}"\necho "$path"\n'),
    ],
)
def test_comment_like_syntax_outside_comments_is_not_reported(tmp_path: Path, name: str, content: str):
    """URLs, globs, floor division and shell substitution are not comments."""
    make_repo(tmp_path, {name: content})
    assert "prohibited-comment-syntax" not in rules(tmp_path)


def test_strip_quoted_strings_preserves_offsets():
    line = 'value = "abc" + x'
    assert len(strip_quoted_strings(line)) == len(line)
    assert "abc" not in strip_quoted_strings(line)


# --------------------------------------------------------------------------
# British English
# --------------------------------------------------------------------------


def test_american_spelling_in_comment_is_reported(tmp_path: Path):
    make_repo(tmp_path, {"m.py": "# Normalize the vector before comparison.\nx = 1\n"})
    assert "american-spelling" in rules(tmp_path)


def test_american_spelling_in_code_is_not_reported(tmp_path: Path):
    """Identifiers and API names are never rewritten — only prose is checked."""
    make_repo(tmp_path, {"m.py": "def normalize_vector(v):\n    return v\n"})
    assert "american-spelling" not in rules(tmp_path)


def test_identifier_quoted_in_a_comment_is_not_reported(tmp_path: Path):
    """A comment may name a real function without triggering a spelling rule."""
    make_repo(tmp_path, {"m.py": "# Counts come from summarize_metrics(); see `normalize_vector`.\nx = 1\n"})
    assert "american-spelling" not in rules(tmp_path)


def test_artifact_is_an_accepted_project_term(tmp_path: Path):
    """'artifact' names artifacts.py and the artifact_type key, so it stands."""
    make_repo(tmp_path, {"m.py": "# Freeze the threshold artifact before evaluation.\nx = 1\n"})
    assert "american-spelling" not in rules(tmp_path)


# --------------------------------------------------------------------------
# Comment length
# --------------------------------------------------------------------------


def test_over_long_comment_is_reported(tmp_path: Path):
    make_repo(tmp_path, {"m.py": f"# {'word ' * 40}\nx = 1\n"})
    assert "comment-too-long" in rules(tmp_path)


def test_shebang_and_noqa_are_exempt(tmp_path: Path):
    content = "#!/usr/bin/env python3\nimport os  # noqa: F401 " + "x" * 120 + "\n"
    make_repo(tmp_path, {"m.py": content})
    assert "comment-too-long" not in rules(tmp_path)


# --------------------------------------------------------------------------
# Attribution blocks
# --------------------------------------------------------------------------


COMPLETE_BLOCK = (
    "##############\n"
    "# Title: YuNet face detection example\n"
    "# Author: OpenCV\n"
    "# Date: 2023\n"
    "# Availability: https://github.com/opencv/opencv_zoo\n"
    "##############\n"
    "x = 1\n"
)


def test_complete_attribution_block_passes(tmp_path: Path):
    make_repo(tmp_path, {"m.py": COMPLETE_BLOCK})
    assert "incomplete-attribution" not in rules(tmp_path)


@pytest.mark.parametrize("missing", ["Title", "Author", "Date", "Availability"])
def test_attribution_block_missing_a_field_is_reported(tmp_path: Path, missing: str):
    block = "\n".join(l for l in COMPLETE_BLOCK.splitlines() if not l.startswith(f"# {missing}:"))
    make_repo(tmp_path, {"m.py": block + "\n"})
    assert "incomplete-attribution" in rules(tmp_path)


def test_unstable_availability_is_reported(tmp_path: Path):
    block = COMPLETE_BLOCK.replace("https://github.com/opencv/opencv_zoo", "somewhere on the internet")
    make_repo(tmp_path, {"m.py": block})
    assert {"unstable-availability", "vague-provenance"} & set(rules(tmp_path))


def test_doi_availability_is_accepted(tmp_path: Path):
    block = COMPLETE_BLOCK.replace("https://github.com/opencv/opencv_zoo", "doi:10.1148/radiology.143.1.7063747")
    make_repo(tmp_path, {"m.py": block})
    assert "unstable-availability" not in rules(tmp_path)


@pytest.mark.parametrize(
    "line",
    [
        "# Author: Unknown",
        "# Date: Unknown",
        "# Availability: Internet",
        "# Source: Stack Overflow",
        "# Source: Google",
        "# Source: AI generated",
    ],
)
def test_vague_provenance_is_reported(tmp_path: Path, line: str):
    make_repo(tmp_path, {"m.py": f"{line}\nx = 1\n"})
    assert "vague-provenance" in rules(tmp_path)


# --------------------------------------------------------------------------
# Privacy
# --------------------------------------------------------------------------


def test_private_path_in_comment_is_reported(tmp_path: Path):
    make_repo(tmp_path, {"m.py": "# Reads from /Users/someone/SecureResearchData/datasets.\nx = 1\n"})
    assert "private-path" in rules(tmp_path)


def test_email_address_in_comment_is_reported(tmp_path: Path):
    make_repo(tmp_path, {"m.py": "# Contact researcher@example.com for access.\nx = 1\n"})
    assert "personal-email" in rules(tmp_path)


# --------------------------------------------------------------------------
# JSON validity and CLI contract
# --------------------------------------------------------------------------


def test_hash_comment_breaks_json_and_is_reported(tmp_path: Path):
    make_repo(tmp_path, {"d.json": '{\n  # not allowed in JSON\n  "a": 1\n}\n'})
    assert "invalid-json" in rules(tmp_path)


def test_valid_json_passes(tmp_path: Path):
    make_repo(tmp_path, {"d.json": json.dumps({"artifact_type": "run_manifest"})})
    assert "invalid-json" not in rules(tmp_path)


def test_clean_repository_reports_nothing(tmp_path: Path):
    make_repo(tmp_path, {"m.py": "# Freeze the threshold before held-out evaluation.\nx = 1\n"})
    assert audit(tmp_path) == []


def test_main_returns_nonzero_on_violation(tmp_path: Path, capsys):
    make_repo(tmp_path, {"m.py": "# Normalize the input.\nx = 1\n"})
    assert main(["--root", str(tmp_path)]) == 1
    assert "FAILED" in capsys.readouterr().out


def test_main_returns_zero_on_clean_repository(tmp_path: Path, capsys):
    make_repo(tmp_path, {"m.py": "# Freeze the threshold before held-out evaluation.\nx = 1\n"})
    assert main(["--root", str(tmp_path)]) == 0
    assert "passed" in capsys.readouterr().out
