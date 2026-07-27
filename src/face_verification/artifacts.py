"""Content-addressed, schema-versioned artifact writing.

Every artifact this project writes is self-describing enough that a reader
never has to trust an unlabelled number: schema version, creation timestamp,
and (added by the caller) software/model provenance and dataset hashes.
Writes are atomic (write-to-temp-then-rename) so a crash mid-write never
leaves a half-written result file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

SCHEMA_VERSION = 1


class ArtifactError(RuntimeError):
    pass


def _json_default(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serialisable")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_of_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def write_json_artifact(path: Path, payload: Mapping[str, Any]) -> str:
    body: Dict[str, Any] = dict(payload)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("created_at", utc_now_iso())
    text = json.dumps(body, indent=2, sort_keys=True, default=_json_default) + "\n"
    _atomic_write(Path(path), text)
    return sha256_of_text(text)


def write_csv_artifact(path: Path, rows: Sequence[Mapping[str, Any]], *, fieldnames: Sequence[str]) -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(fieldnames))
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    text = buffer.getvalue()
    _atomic_write(Path(path), text)
    return sha256_of_text(text)


def write_markdown_artifact(path: Path, text: str) -> str:
    if not text.endswith("\n"):
        text += "\n"
    _atomic_write(Path(path), text)
    return sha256_of_text(text)


def read_json_artifact(path: Path) -> Dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise ArtifactError(f"Artifact does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))
