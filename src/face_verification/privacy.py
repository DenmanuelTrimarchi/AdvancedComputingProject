"""Guards that keep committed outputs free of names, absolute paths and
raw embedding vectors.

Used both by the artifact writers (defensively) and directly by
``tests/test_artifact_privacy.py``.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, List, Mapping, Sequence

OPAQUE_ID_SALT = "face-verification-opaque-id-v1"

_FORBIDDEN_KEY_SUBSTRINGS = ("embedding", "path", "identity", "name")
_ALLOWED_KEY_EXCEPTIONS = {"strategy", "identity_count", "identity_hash", "candidate_identity_hash"}


def opaque_id(value: str, *, salt: str = OPAQUE_ID_SALT) -> str:
    """Deterministic, one-way identifier for a real identity/sample name.

    Deterministic (not random) so re-running the pipeline with the same
    inputs reproduces the same opaque IDs, without ever storing the
    reversible mapping in a committed artifact.
    """
    digest = hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()
    return digest[:16]


def scrub_filename(path: Path) -> str:
    """Return only the filename component, never an absolute or repo-relative path."""
    return Path(path).name


class PrivacyLeakError(ValueError):
    pass


def assert_no_leakage(record: Mapping[str, Any], *, context: str = "") -> None:
    """Raise ``PrivacyLeakError`` if any key/value in ``record`` looks like it
    holds a real name, an absolute filesystem path, or a raw embedding
    vector. Recurses into nested mappings."""
    for key, value in record.items():
        label = f"{context}.{key}" if context else str(key)
        lowered_key = key.lower() if isinstance(key, str) else str(key)

        if key not in _ALLOWED_KEY_EXCEPTIONS:
            for banned in _FORBIDDEN_KEY_SUBSTRINGS:
                if banned in lowered_key:
                    raise PrivacyLeakError(f"{label}: key name may leak private data")

        if isinstance(value, str) and (value.startswith("/") or value.startswith("~")):
            raise PrivacyLeakError(f"{label}: value looks like an absolute path: {value}")

        if (
            isinstance(value, (list, tuple))
            and len(value) >= 32
            and all(isinstance(item, (int, float)) for item in value)
        ):
            raise PrivacyLeakError(f"{label}: value looks like a raw embedding vector")

        if isinstance(value, Mapping):
            assert_no_leakage(value, context=label)


_TEXT_ARTIFACT_SUFFIXES = (".json", ".csv", ".md")


def default_forbidden_path_substrings(*, env: Mapping[str, str] | None = None) -> List[str]:
    """Substrings that must never appear in a public aggregate result: the
    researcher's home directory, common absolute-path prefixes, and the
    expanded value of every private-storage location environment variable."""
    source = os.environ if env is None else env
    substrings = {"/Users/", "\\Users\\", "/home/", str(Path.home())}
    for variable in ("FACE_DATA_ROOT", "FACE_PROTOCOL_ROOT", "FACE_MODEL_ROOT", "FACE_CACHE_ROOT"):
        value = source.get(variable)
        if value:
            substrings.add(value)
    return sorted(s for s in substrings if s)


def find_path_leaks(root: Path, *, forbidden_substrings: Sequence[str]) -> List[str]:
    """Recursively scan every JSON/CSV/Markdown file under ``root`` for any
    forbidden substring (e.g. an absolute filesystem path). Returns a list of
    ``"file:line: forbidden substring"`` findings; an empty list means clean.
    Never raises on unreadable/binary files — those are simply skipped."""
    findings: List[str] = []
    root = Path(root)
    if not root.exists():
        return findings
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _TEXT_ARTIFACT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for needle in forbidden_substrings:
                if needle and needle in line:
                    findings.append(f"{path}:{line_number}: contains forbidden substring {needle!r}")
    return findings
