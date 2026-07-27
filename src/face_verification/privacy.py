"""Guards that keep committed outputs free of names, absolute paths and
raw embedding vectors.

Used both by the artifact writers (defensively) and directly by
``tests/test_artifact_privacy.py``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

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
