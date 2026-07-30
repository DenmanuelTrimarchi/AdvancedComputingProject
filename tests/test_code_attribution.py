"""Provenance and comment-style assertions for this repository's tracked files.

tests/test_comment_style.py establishes that the checker reports violations on
synthetic inputs; the tests here apply it to the repository itself. Two
conditions carry the most weight: no source may be recorded unless it has been
verified, and the attribution header must stay confined to the code that
genuinely warrants one.
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
import tokenize
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_comment_style import (  # noqa: E402
    ATTRIBUTION_FENCE,
    audit,
    comment_body,
    is_auditable,
    tracked_files,
)

REGISTER = REPO_ROOT / "docs" / "CODE_ATTRIBUTION.md"


def python_files() -> List[Path]:
    return [p for p in tracked_files(REPO_ROOT) if p.suffix == ".py" and p.is_file()]


def all_comments(path: Path) -> List[str]:
    try:
        source = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []
    if path.suffix == ".py":
        try:
            return [
                t.string
                for t in tokenize.generate_tokens(io.StringIO(source).readline)
                if t.type == tokenize.COMMENT
            ]
        except (tokenize.TokenError, SyntaxError):
            return []
    return [line[line.index("#"):] for line in source.splitlines() if "#" in line]


def repository_comments() -> List[tuple[Path, str]]:
    pairs: List[tuple[Path, str]] = []
    for path in tracked_files(REPO_ROOT):
        if path.is_file() and is_auditable(path, REPO_ROOT):
            pairs.extend((path, comment) for comment in all_comments(path))
    return pairs


# --------------------------------------------------------------------------
# The repository itself is clean
# --------------------------------------------------------------------------


def test_repository_passes_the_comment_style_audit():
    violations = audit(REPO_ROOT)
    assert violations == [], "\n".join(str(v) for v in violations)


def test_every_tracked_json_file_is_valid():
    """Committed results are machine-read by the report scripts."""
    violations = [v for v in audit(REPO_ROOT) if v.rule == "invalid-json"]
    assert violations == [], "\n".join(str(v) for v in violations)


# --------------------------------------------------------------------------
# No invented provenance
# --------------------------------------------------------------------------


FORBIDDEN_PROVENANCE = re.compile(
    r"(?:author|date|availability|source)\s*:\s*"
    r"(?:unknown|n/?a|internet|the internet|google|stack\s*overflow|chatgpt|ai[\s-]generated|various)\b",
    re.IGNORECASE,
)


def test_no_vague_or_invented_provenance_anywhere():
    offenders = [
        f"{path.relative_to(REPO_ROOT)}: {comment.strip()}"
        for path, comment in repository_comments()
        if FORBIDDEN_PROVENANCE.search(comment_body(comment))
    ]
    assert offenders == [], "\n".join(offenders)


def test_attribution_headers_are_not_applied_to_every_file():
    """The header marks genuinely adapted code; universal use would void it."""
    files = python_files()
    with_header = [p for p in files if ATTRIBUTION_FENCE in p.read_text(encoding="utf-8")]
    assert len(with_header) < len(files), "every Python file carries an attribution header"


def test_attribution_headers_present_are_complete():
    """Any header that does exist must carry all four fields."""
    incomplete = [
        v for v in audit(REPO_ROOT) if v.rule in {"incomplete-attribution", "unstable-availability"}
    ]
    assert incomplete == [], "\n".join(str(v) for v in incomplete)


# --------------------------------------------------------------------------
# Privacy of comment text
# --------------------------------------------------------------------------


def test_no_comment_contains_a_private_path_or_email():
    violations = [v for v in audit(REPO_ROOT) if v.rule in {"private-path", "personal-email"}]
    assert violations == [], "\n".join(str(v) for v in violations)


def test_no_comment_names_a_benchmark_identity():
    """LFW directories are person names; none may appear in a comment.

    The datasets are never committed, so this guards the one route by which a
    real identity could still reach the public repository.
    """
    identity_like = re.compile(r"\b[A-Z][a-z]+_[A-Z][a-z]+(?:_[A-Z][a-z]+)*\b")
    offenders = [
        f"{path.relative_to(REPO_ROOT)}: {match}"
        for path, comment in repository_comments()
        for match in identity_like.findall(comment_body(comment))
    ]
    assert offenders == [], "\n".join(offenders)


# --------------------------------------------------------------------------
# The register itself
# --------------------------------------------------------------------------


def test_attribution_register_exists_and_states_its_scope():
    assert REGISTER.is_file(), "docs/CODE_ATTRIBUTION.md is missing"
    text = REGISTER.read_text(encoding="utf-8")
    assert "materially adapted" in text
    assert "docs/MODEL_PROVENANCE.md" in text


def test_register_lists_no_unverified_source():
    text = REGISTER.read_text(encoding="utf-8")
    assert not FORBIDDEN_PROVENANCE.search(text)
    for placeholder in ("TODO", "TBC", "FIXME", "???"):
        assert placeholder not in text, f"register contains placeholder {placeholder!r}"


def test_register_files_exist():
    """Every repository file named in the register must actually exist."""
    text = REGISTER.read_text(encoding="utf-8")
    referenced = set(re.findall(r"`((?:src|scripts|local_review|tests|docs)/[\w/.]+\.\w+)`", text))
    missing = sorted(name for name in referenced if not (REPO_ROOT / name).exists())
    assert missing == [], f"register references missing files: {missing}"


# --------------------------------------------------------------------------
# Behaviour is unchanged
# --------------------------------------------------------------------------


def test_every_tracked_python_file_compiles():
    """A comment edit must never leave a source file unparseable."""
    files = [str(p) for p in python_files()]
    completed = subprocess.run(
        [sys.executable, "-m", "py_compile", *files], capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stderr
