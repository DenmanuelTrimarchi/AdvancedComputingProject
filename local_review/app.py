"""Local-only, login-free Streamlit page for manually reviewing anonymised
duplicate-profile gallery cases.

Run with:
    streamlit run local_review/app.py --server.address=127.0.0.1 -- --db results/raw/review.sqlite

This page never displays a real name, real file path, or raw embedding —
only opaque identifiers, a similarity score, and the threshold that opened
the case. It is a demonstration of the review UI a moderator would use, not
the main research artefact — see docs/EVALUATION_PROTOCOL.md for that.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from database import connect, list_cases, set_status  # noqa: E402

DEFAULT_DB_PATH = Path("results/raw/review.sqlite")
STATUSES = ["open", "confirmed_duplicate", "false_match", "dismissed"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def main() -> None:
    st.set_page_config(page_title="Duplicate-profile review (local only)", layout="wide")
    args = _parse_args()

    st.title("Duplicate-profile review — local demonstration only")
    st.warning(
        "Similarity above threshold is evidence for human review, not proof of "
        "misuse or scam activity. No account is banned, suspended or accused by "
        "this page. Case, probe and candidate identifiers are opaque one-way "
        "hashes; no real name or file path is ever shown here."
    )

    status_filter = st.selectbox("Filter by status", ["all", *STATUSES])

    with connect(args.db) as connection:
        cases = list_cases(connection, status=None if status_filter == "all" else status_filter)

        if not cases:
            st.info("No cases match this filter.")
            return

        for case in cases:
            with st.container(border=True):
                st.write(f"**Case:** `{case.case_id}`")
                col1, col2, col3 = st.columns(3)
                col1.metric("Similarity", f"{case.similarity:.4f}")
                col2.metric("Threshold", f"{case.threshold:.4f}")
                col3.metric("Status", case.status)
                st.caption(f"Probe: `{case.probe_sample_id}` — Candidate identity: `{case.candidate_identity_hash}`")
                st.caption(
                    f"Opened: {case.created_at}"
                    + (f" — Decided: {case.decided_at}" if case.decided_at else "")
                )

                chosen = st.radio(
                    "Decision",
                    STATUSES,
                    index=STATUSES.index(case.status),
                    key=f"decision_{case.case_id}",
                    horizontal=True,
                )
                if chosen != case.status:
                    set_status(connection, case_id=case.case_id, status=chosen)
                    st.rerun()


if __name__ == "__main__":
    main()
