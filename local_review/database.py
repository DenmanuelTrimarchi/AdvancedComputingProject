"""Local-only SQLite storage for the optional gallery-review demonstration.

Every column is either an opaque hash, a numeric score, or a review
decision — never a real name, real file path, or raw embedding vector.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

ALLOWED_STATUSES = {"open", "confirmed_duplicate", "false_match", "dismissed"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS review_cases (
    case_id TEXT PRIMARY KEY,
    probe_sample_id TEXT NOT NULL,
    candidate_identity_hash TEXT NOT NULL,
    similarity REAL NOT NULL,
    threshold REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    decided_at TEXT
);
"""


@dataclass(frozen=True)
class ReviewCase:
    case_id: str
    probe_sample_id: str
    candidate_identity_hash: str
    similarity: float
    threshold: float
    status: str
    created_at: str
    decided_at: Optional[str]


@contextmanager
def connect(db_path: Path) -> Iterator[sqlite3.Connection]:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path))
    try:
        connection.execute(SCHEMA)
        connection.row_factory = sqlite3.Row
        yield connection
        connection.commit()
    finally:
        connection.close()


def upsert_case(
    connection: sqlite3.Connection,
    *,
    case_id: str,
    probe_sample_id: str,
    candidate_identity_hash: str,
    similarity: float,
    threshold: float,
) -> None:
    connection.execute(
        """
        INSERT INTO review_cases
            (case_id, probe_sample_id, candidate_identity_hash, similarity, threshold, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'open', ?)
        ON CONFLICT(case_id) DO UPDATE SET
            probe_sample_id=excluded.probe_sample_id,
            candidate_identity_hash=excluded.candidate_identity_hash,
            similarity=excluded.similarity,
            threshold=excluded.threshold
        """,
        (case_id, probe_sample_id, candidate_identity_hash, similarity, threshold, _utc_now()),
    )


def list_cases(connection: sqlite3.Connection, *, status: Optional[str] = None) -> List[ReviewCase]:
    if status is not None and status not in ALLOWED_STATUSES:
        raise ValueError(f"Unknown status filter: {status}")
    if status:
        rows = connection.execute(
            "SELECT * FROM review_cases WHERE status = ? ORDER BY similarity DESC", (status,)
        )
    else:
        rows = connection.execute("SELECT * FROM review_cases ORDER BY similarity DESC")
    return [_row_to_case(row) for row in rows]


def set_status(connection: sqlite3.Connection, *, case_id: str, status: str) -> None:
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Unknown status: {status}; must be one of {sorted(ALLOWED_STATUSES)}")
    connection.execute(
        "UPDATE review_cases SET status = ?, decided_at = ? WHERE case_id = ?",
        (status, _utc_now(), case_id),
    )


def _row_to_case(row: sqlite3.Row) -> ReviewCase:
    return ReviewCase(
        case_id=row["case_id"],
        probe_sample_id=row["probe_sample_id"],
        candidate_identity_hash=row["candidate_identity_hash"],
        similarity=row["similarity"],
        threshold=row["threshold"],
        status=row["status"],
        created_at=row["created_at"],
        decided_at=row["decided_at"],
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
