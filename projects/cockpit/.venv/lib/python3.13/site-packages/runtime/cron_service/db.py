"""SQLite persistence for cron-service jobs."""

import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from .models import Job, JobCreate, JobUpdate

_local = threading.local()


def _get_db_path() -> Path:
    """Return the SQLite database path under ~/.cron-service/."""
    from . import config

    d = Path(config.DATA_DIR).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d / "cron.db"


def _get_conn() -> sqlite3.Connection:
    """Get a thread-local connection (WAL mode)."""
    if not hasattr(_local, "conn") or _local.conn is None:
        path = _get_db_path()
        _local.conn = sqlite3.connect(str(path))
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA busy_timeout=5000")
    return _local.conn


def init_db():
    """Create tables if they don't exist."""
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            schedule TEXT NOT NULL,
            script TEXT,
            prompt TEXT,
            no_agent INTEGER NOT NULL DEFAULT 1,
            deliver TEXT NOT NULL DEFAULT 'local',
            workdir TEXT,
            timeout INTEGER NOT NULL DEFAULT 120,
            repeat TEXT NOT NULL DEFAULT '∞',
            enabled INTEGER NOT NULL DEFAULT 1,
            last_run_at TEXT,
            last_status TEXT,
            last_output TEXT,
            last_error TEXT,
            run_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.commit()


# ── CRUD ──────────────────────────────────────────────────────────


def _row_to_job(row) -> Job:
    d = dict(row)
    d["no_agent"] = bool(d["no_agent"])
    d["enabled"] = bool(d["enabled"])
    for key in ("last_run_at", "created_at", "updated_at"):
        val = d.get(key)
        if val:
            d[key] = datetime.fromisoformat(val)
    return Job(**d)


def list_jobs(enabled_only: bool = False) -> list[Job]:
    conn = _get_conn()
    q = "SELECT * FROM jobs"
    if enabled_only:
        q += " WHERE enabled = 1"
    q += " ORDER BY created_at"
    return [_row_to_job(r) for r in conn.execute(q).fetchall()]


def get_job(job_id: str) -> Job | None:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def create_job(data: JobCreate) -> Job:
    job = Job(**data.model_dump())
    # Set last_run_at to creation time so the scheduler doesn't
    # immediately run a newly created job — it waits for the next tick.
    now = datetime.now(UTC)
    job.last_run_at = now
    conn = _get_conn()
    now_iso = now.isoformat()
    conn.execute(
        """
        INSERT INTO jobs (id, name, schedule, script, prompt, no_agent,
                          deliver, workdir, timeout, repeat, enabled,
                          created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            job.id,
            job.name,
            job.schedule,
            job.script,
            job.prompt,
            int(job.no_agent),
            job.deliver,
            job.workdir,
            job.timeout,
            job.repeat,
            int(job.enabled),
            now_iso,
            now_iso,
        ),
    )
    conn.commit()
    return job


def update_job(job_id: str, data: JobUpdate) -> Job | None:
    existing = get_job(job_id)
    if not existing:
        return None

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return existing

    updates["updated_at"] = datetime.now(UTC).isoformat()
    # Convert bools to int for SQLite
    for key in ("no_agent", "enabled"):
        if key in updates:
            updates[key] = int(updates[key])

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [job_id]

    conn = _get_conn()
    conn.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return get_job(job_id)


def delete_job(job_id: str) -> bool:
    conn = _get_conn()
    cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    return cur.rowcount > 0


def record_run(job_id: str, status: str, output: str = "", error: str = ""):
    """Update job with run result."""
    now = datetime.now(UTC).isoformat()
    conn = _get_conn()
    conn.execute(
        """
        UPDATE jobs SET last_run_at = ?, last_status = ?,
                        last_output = ?, last_error = ?,
                        run_count = run_count + 1, updated_at = ?
        WHERE id = ?
    """,
        (now, status, output[:10000], error[:5000], now, job_id),
    )
    conn.commit()


class JobStore:
    """Compatibility facade over module-level CRUD helpers."""

    init_db = staticmethod(init_db)
    list_jobs = staticmethod(list_jobs)
    get_job = staticmethod(get_job)
    create_job = staticmethod(create_job)
    update_job = staticmethod(update_job)
    delete_job = staticmethod(delete_job)
    record_run = staticmethod(record_run)
