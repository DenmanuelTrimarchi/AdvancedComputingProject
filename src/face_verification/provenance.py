"""Model file verification and software/hardware environment recording.

Every result artifact this project writes embeds the output of
``software_environment_report`` and the model hashes verified here, so a
reader can tell exactly what produced a number without trusting a claim in
prose.
"""

from __future__ import annotations

import hashlib
import platform
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Dict, Optional

from .config import EXPECTED_DEPENDENCY_VERSIONS


class ModelUnavailableError(RuntimeError):
    """Raised when a model file is missing or fails hash verification."""


class DependencyContractError(RuntimeError):
    """Raised when an installed dependency does not match the pinned contract."""


def sha256_of_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_file(path: Path, expected_sha256: str) -> str:
    """Return the file's SHA-256 if it matches ``expected_sha256``, else raise."""
    path = Path(path)
    if not path.is_file():
        raise ModelUnavailableError(f"Model file not found: {path}")
    actual = sha256_of_file(path)
    if actual != expected_sha256:
        raise ModelUnavailableError(
            f"Model hash mismatch for {path}: expected {expected_sha256}, got {actual}. "
            f"Do not proceed — re-download the exact pinned OpenCV Zoo release."
        )
    return actual


def check_dependency_contract(*, strict: bool = True) -> Dict[str, Dict[str, Optional[str]]]:
    report: Dict[str, Dict[str, Optional[str]]] = {}
    mismatched = []
    for package, expected in EXPECTED_DEPENDENCY_VERSIONS.items():
        try:
            installed = importlib_metadata.version(package)
        except importlib_metadata.PackageNotFoundError:
            installed = None
        report[package] = {"expected": expected, "installed": installed}
        if installed != expected:
            mismatched.append(package)
    if mismatched and strict:
        raise DependencyContractError(
            "Dependency version mismatch for: "
            + ", ".join(mismatched)
            + ". Reinstall with the pinned versions in pyproject.toml before running "
            "any evaluation that will be reported as evidence."
        )
    return report


def software_environment_report() -> Dict[str, object]:
    return {
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "dependencies": check_dependency_contract(strict=False),
    }
