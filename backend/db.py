# backend/db.py

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config import JOBS_DB_PATH

# Job lifecycle. FAILED can be entered from any step; `current_step` then
# records which step was running when the failure happened.
STEPS = [
    "PENDING", "INGESTING", "NORMALIZING", "LABELING", "CATEGORIZING",
    "DETECTING_PATTERNS", "BUILDING_FEATURES", "SCORING_RISK",
    "GENERATING_RECOMMENDATIONS", "DETECTING_ANOMALIES", "EXPLAINING", "DONE",
]
TERMINAL_STATES = {"DONE", "FAILED"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id        TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL,
    status        TEXT NOT NULL,
    current_step  TEXT,
    error_message TEXT,
    uploaded_files TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_account ON jobs(account_id, created_at);
"""

# sqlite3 connections are cheap; a process-wide lock serialises writers so
# the background pipeline thread and request threads never interleave.
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db(path: Path = JOBS_DB_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def _connect(path: Path = JOBS_DB_PATH):
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        with _lock:
            yield conn
            conn.commit()
    finally:
        conn.close()


def create_job(job_id: str, account_id: str, uploaded_files: list[str]) -> dict:
    now = _now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, account_id, status, current_step, error_message, uploaded_files, created_at, updated_at) "
            "VALUES (?, ?, 'PENDING', NULL, NULL, ?, ?, ?)",
            (job_id, account_id, ", ".join(uploaded_files), now, now),
        )
    return get_job(job_id)


def update_job_status(job_id: str, status: str, current_step: Optional[str] = None,
                      error_message: Optional[str] = None) -> None:
    # For in-progress statuses the step *is* the status; on FAILED the caller
    # passes the step that blew up so it survives the status change.
    step = current_step if current_step is not None else (status if status not in TERMINAL_STATES else None)
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, current_step = ?, error_message = ?, updated_at = ? WHERE job_id = ?",
            (status, step, error_message, _now(), job_id),
        )


def get_job(job_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def get_latest_job_for_account(account_id: str) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE account_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1",
            (account_id,),
        ).fetchone()
    return dict(row) if row else None


def delete_jobs_for_account(account_id: str) -> int:
    with _connect() as conn:
        cur = conn.execute("DELETE FROM jobs WHERE account_id = ?", (account_id,))
    return cur.rowcount
