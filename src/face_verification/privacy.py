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


_TEXT_ARTIFACT_SUFFIXES = (".json", ".csv", ".md", ".txt")
_IMAGE_ARTIFACT_SUFFIXES = (".png",)

# Storage-location names that identify this researcher's private layout even
# when they appear without a leading absolute-path prefix (e.g. inside a
# rendered evidence image's embedded metadata, or a relative-looking string).
_PRIVATE_LOCATION_MARKERS = ("SecureResearchData", "Library/CloudStorage")


def default_forbidden_path_substrings(*, env: Mapping[str, str] | None = None) -> List[str]:
    """Substrings that must never appear in a public aggregate result: the
    researcher's home directory, common absolute-path prefixes, known
    private-storage location names, and the expanded value of every
    private-storage location environment variable."""
    source = os.environ if env is None else env
    substrings = {"/Users/", "\\Users\\", "/home/", str(Path.home())}
    substrings.update(_PRIVATE_LOCATION_MARKERS)
    for variable in ("FACE_DATA_ROOT", "FACE_PROTOCOL_ROOT", "FACE_MODEL_ROOT", "FACE_CACHE_ROOT"):
        value = source.get(variable)
        if value:
            substrings.add(value)
    return sorted(s for s in substrings if s)


def _png_text_metadata(path: Path) -> str:
    """Every tEXt/iTXt/zTXt chunk in a PNG, concatenated. Matplotlib writes a
    ``Software`` chunk by default and callers may add their own, so a
    rendered figure can leak a path that never appears in the visible pixels.

    A corrupt or truncated PNG yields "" — there is nothing to read, and the
    file is not publishable evidence anyway. A *missing Pillow* is different:
    it would make every PNG silently pass, turning this check into a no-op
    that still reports "clean". Pillow is a pinned core dependency, so its
    absence is raised rather than swallowed.
    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - Pillow is a pinned dependency
        raise PrivacyLeakError(
            "Pillow is not installed, so PNG metadata cannot be scanned. Refusing to report a "
            "clean result from a check that did not run."
        ) from exc

    try:
        with Image.open(path) as image:
            return "\n".join(f"{key}: {value}" for key, value in (image.info or {}).items() if isinstance(value, str))
    except OSError:
        return ""


def find_path_leaks(root: Path, *, forbidden_substrings: Sequence[str]) -> List[str]:
    """Recursively scan every JSON/CSV/Markdown/text file under ``root`` — and
    the embedded text metadata of every PNG — for any forbidden substring
    (e.g. an absolute filesystem path). Returns a list of
    ``"file:line: forbidden substring"`` findings; an empty list means clean.
    Never raises on unreadable/binary files — those are simply skipped."""
    findings: List[str] = []
    root = Path(root)
    if not root.exists():
        return findings
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in _TEXT_ARTIFACT_SUFFIXES:
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            location = "{path}:{line}"
        elif suffix in _IMAGE_ARTIFACT_SUFFIXES:
            text = _png_text_metadata(path)
            location = "{path} (embedded PNG metadata, entry {line})"
        else:
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for needle in forbidden_substrings:
                if needle and needle in line:
                    where = location.format(path=path, line=line_number)
                    findings.append(f"{where}: contains forbidden substring {needle!r}")
    return findings
