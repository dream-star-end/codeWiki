from __future__ import annotations

from pathlib import Path

from app.services.db import get_conn, init_db


def init_jobs_db() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "db" / "schema_sqlite_jobs.sql"
    with get_conn() as conn:
        conn.executescript(schema_path.read_text(encoding="utf-8"))


def upsert_job(job_id: str, status: str, progress: int, error: str | None) -> None:
    init_jobs_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (id, status, progress, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                progress=excluded.progress,
                error=excluded.error,
                updated_at=datetime('now')
            """,
            (job_id, status, progress, error),
        )


def read_job(job_id: str) -> dict | None:
    init_jobs_db()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    return dict(row) if row else None
