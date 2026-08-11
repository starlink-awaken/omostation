"""Versioned SQLite store with a single bounded writer actor."""

from __future__ import annotations

import asyncio
import json
import math
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, TypeVar

import aiosqlite

from omlxc.domain import Job, JobState, RiskLevel, transition_job

from .jobs import JobConflictError, RunningRecoveryPolicy, StoredJob
from .models import (
    DailyMetricAggregate,
    DurableEventRecord,
    HealthRecord,
    MetricRecord,
    StorageDegradedError,
    UnsupportedSchemaError,
)

SCHEMA_VERSION = 1
MAX_PAGE_SIZE = 500
_T = TypeVar("_T")


@dataclass(slots=True)
class _WriteRequest:
    operation: Callable[[aiosqlite.Connection], Awaitable[Any]]
    result: asyncio.Future[Any]


class SQLiteRuntimeStore:
    """SQLite runtime state whose mutations all pass through one actor queue."""

    def __init__(
        self,
        path: Path,
        writer: aiosqlite.Connection | None,
        reader: aiosqlite.Connection | None,
        *,
        writer_queue_capacity: int,
        metric_buffer_capacity: int,
        diagnostic: str | None = None,
    ) -> None:
        self._path = path
        self._writer = writer
        self._reader = reader
        self._queue: asyncio.Queue[_WriteRequest | None] = asyncio.Queue(
            maxsize=writer_queue_capacity
        )
        self._metric_capacity = metric_buffer_capacity
        self._metrics: list[MetricRecord] = []
        self._closed = False
        self._recovery_complete = False
        self._diagnostic = diagnostic
        self._actor = (
            asyncio.create_task(self._writer_loop(), name="omlxc-sqlite-writer")
            if writer is not None
            else None
        )

    @classmethod
    async def open(
        cls,
        path: Path,
        *,
        writer_queue_capacity: int = 128,
        metric_buffer_capacity: int = 256,
        quarantine_suffix_factory: Callable[[], str] | None = None,
    ) -> SQLiteRuntimeStore:
        if writer_queue_capacity <= 0 or metric_buffer_capacity <= 0:
            raise ValueError("storage queue capacities must be greater than zero")
        path = path.expanduser()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        writer = await aiosqlite.connect(path)
        try:
            await _configure(writer)
            await _migrate(writer)
        except aiosqlite.DatabaseError:
            await writer.close()
            suffix_factory = quarantine_suffix_factory or (
                lambda: datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            )
            suffix = suffix_factory()
            if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", suffix):
                raise ValueError("quarantine suffix is invalid") from None
            quarantine = path.with_name(f"{path.name}.corrupt-{suffix}")
            os.replace(path, quarantine)
            os.chmod(quarantine, 0o600)
            return cls(
                path,
                None,
                None,
                writer_queue_capacity=writer_queue_capacity,
                metric_buffer_capacity=metric_buffer_capacity,
                diagnostic=f"storage_corruption_quarantined:{quarantine.name}",
            )
        except BaseException:
            await writer.close()
            raise
        os.chmod(path, 0o600)
        reader = await aiosqlite.connect(path)
        await _configure(reader)
        return cls(
            path,
            writer,
            reader,
            writer_queue_capacity=writer_queue_capacity,
            metric_buffer_capacity=metric_buffer_capacity,
        )

    @property
    def degraded(self) -> bool:
        return self._diagnostic is not None

    @property
    def diagnostic(self) -> str:
        return self._diagnostic or "storage_healthy"

    async def _writer_loop(self) -> None:
        writer = self._writer
        if writer is None:
            return
        while True:
            request = await self._queue.get()
            if request is None:
                self._queue.task_done()
                return
            try:
                await writer.execute("BEGIN IMMEDIATE")
                value = await request.operation(writer)
                await writer.commit()
            except BaseException as exc:
                await writer.rollback()
                if not request.result.done():
                    request.result.set_exception(exc)
            else:
                if not request.result.done():
                    request.result.set_result(value)
            finally:
                self._queue.task_done()

    async def _write(self, operation: Callable[[aiosqlite.Connection], Awaitable[_T]]) -> _T:
        if self._closed:
            raise StorageDegradedError("runtime storage is closed")
        if self.degraded:
            raise StorageDegradedError("runtime storage is degraded read-only")
        loop = asyncio.get_running_loop()
        result: asyncio.Future[_T] = loop.create_future()
        await self._queue.put(_WriteRequest(operation=operation, result=result))
        return await result

    async def schema_version(self) -> int:
        reader = self._require_reader()
        cursor = await reader.execute("PRAGMA user_version")
        row = await cursor.fetchone()
        await cursor.close()
        return int(row[0]) if row is not None else 0

    async def pragma_state(self) -> dict[str, int | str]:
        reader = self._require_reader()
        values: dict[str, int | str] = {}
        pragmas = (
            ("busy_timeout", "PRAGMA busy_timeout"),
            ("foreign_keys", "PRAGMA foreign_keys"),
            ("journal_mode", "PRAGMA journal_mode"),
        )
        for name, statement in pragmas:
            cursor = await reader.execute(statement)
            row = await cursor.fetchone()
            await cursor.close()
            if row is None or row[0] is None:
                raise StorageDegradedError(f"SQLite PRAGMA {name} is unavailable")
            value = row[0]
            values[name] = value.lower() if isinstance(value, str) else int(value)
        return values

    async def save_health(self, record: HealthRecord) -> None:
        observed_at = _utc_text(record.observed_at)
        if not math.isfinite(record.observed_monotonic):
            raise ValueError("health monotonic observation must be finite")

        async def operation(connection: aiosqlite.Connection) -> None:
            await connection.execute(
                """
                INSERT INTO health_snapshots (
                    resource_kind, resource_id, state, observed_at,
                    observed_monotonic, stale
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.resource_kind,
                    record.resource_id,
                    record.state,
                    observed_at,
                    record.observed_monotonic,
                    int(record.stale),
                ),
            )

        await self._write(operation)

    async def latest_health(self, resource_kind: str, resource_id: str) -> HealthRecord | None:
        cursor = await self._require_reader().execute(
            """
            SELECT resource_kind, resource_id, state, observed_at, observed_monotonic, stale
            FROM health_snapshots
            WHERE resource_kind = ? AND resource_id = ?
            ORDER BY observed_at DESC, sequence DESC
            LIMIT 1
            """,
            (resource_kind, resource_id),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return HealthRecord(
            resource_kind=str(row[0]),
            resource_id=str(row[1]),
            state=str(row[2]),
            observed_at=_parse_utc(str(row[3])),
            observed_monotonic=float(row[4]),
            stale=bool(row[5]),
        )

    def accept_metric(self, record: MetricRecord) -> bool:
        if self._closed:
            raise StorageDegradedError("runtime storage is closed")
        if self.degraded:
            raise StorageDegradedError("runtime storage is degraded read-only")
        _utc_text(record.observed_at)
        if not math.isfinite(record.latency_ms) or record.latency_ms < 0:
            raise ValueError("metric latency must be finite and non-negative")
        if len(self._metrics) >= self._metric_capacity:
            return False
        self._metrics.append(record)
        return True

    async def flush_metrics(self) -> int:
        if not self._metrics:
            return 0
        batch = tuple(self._metrics)

        async def operation(connection: aiosqlite.Connection) -> int:
            await connection.executemany(
                """
                INSERT INTO request_metrics
                    (request_id, observed_at, latency_ms, success)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        metric.request_id,
                        _utc_text(metric.observed_at),
                        metric.latency_ms,
                        int(metric.success),
                    )
                    for metric in batch
                ],
            )
            return len(batch)

        written = await self._write(operation)
        del self._metrics[:written]
        return written

    async def metric_count(self) -> int:
        cursor = await self._require_reader().execute("SELECT COUNT(*) FROM request_metrics")
        row = await cursor.fetchone()
        await cursor.close()
        return int(row[0]) if row else 0

    async def apply_retention(self, *, now: datetime, retention_days: int = 30) -> int:
        if retention_days < 1:
            raise ValueError("retention_days must be positive")
        cutoff = _utc(now) - timedelta(days=retention_days)
        cutoff_text = _utc_text(cutoff)

        async def operation(connection: aiosqlite.Connection) -> int:
            await connection.execute(
                """
                INSERT INTO daily_metric_aggregates
                    (day, request_count, error_count, latency_sum_ms)
                SELECT substr(observed_at, 1, 10), COUNT(*),
                       SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), SUM(latency_ms)
                FROM request_metrics
                WHERE observed_at < ?
                GROUP BY substr(observed_at, 1, 10)
                ON CONFLICT(day) DO UPDATE SET
                    request_count = daily_metric_aggregates.request_count
                                    + excluded.request_count,
                    error_count = daily_metric_aggregates.error_count
                                  + excluded.error_count,
                    latency_sum_ms = daily_metric_aggregates.latency_sum_ms
                                     + excluded.latency_sum_ms
                """,
                (cutoff_text,),
            )
            cursor = await connection.execute(
                "DELETE FROM request_metrics WHERE observed_at < ?", (cutoff_text,)
            )
            return max(cursor.rowcount, 0)

        return await self._write(operation)

    async def daily_metric_aggregate(self, day: date) -> DailyMetricAggregate | None:
        cursor = await self._require_reader().execute(
            """
            SELECT day, request_count, error_count, latency_sum_ms
            FROM daily_metric_aggregates WHERE day = ?
            """,
            (day.isoformat(),),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row is None:
            return None
        return DailyMetricAggregate(
            day=date.fromisoformat(str(row[0])),
            request_count=int(row[1]),
            error_count=int(row[2]),
            latency_sum_ms=float(row[3]),
        )

    async def append_durable_event(
        self,
        *,
        event_id: str,
        schema_version: int,
        observed_at: datetime,
        priority: str,
        kind: str,
        payload_json: str,
        job_id: str | None,
        resource_id: str | None,
    ) -> int:
        timestamp = _utc_text(observed_at)

        async def operation(connection: aiosqlite.Connection) -> int:
            cursor = await connection.execute(
                """
                INSERT INTO durable_events (
                    event_id, schema_version, observed_at, priority, kind,
                    payload_json, job_id, resource_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(event_id) DO NOTHING
                """,
                (
                    event_id,
                    schema_version,
                    timestamp,
                    priority,
                    kind,
                    payload_json,
                    job_id,
                    resource_id,
                ),
            )
            if cursor.rowcount == 0:
                existing = await connection.execute(
                    "SELECT sequence FROM durable_events WHERE event_id = ?", (event_id,)
                )
                row = await existing.fetchone()
                await existing.close()
                if row is None:
                    raise StorageDegradedError("durable event could not be persisted")
                return int(row[0])
            if cursor.lastrowid is None:
                raise StorageDegradedError("durable event sequence is unavailable")
            return int(cursor.lastrowid)

        return await self._write(operation)

    async def create_job(
        self,
        job: Job,
        *,
        idempotency_key: str | None,
        payload_fingerprint: str,
    ) -> StoredJob:
        if not payload_fingerprint:
            raise ValueError("job payload fingerprint is required")
        created_at = _utc_text(job.created_at)
        updated_at = _utc_text(job.updated_at)

        async def operation(connection: aiosqlite.Connection) -> StoredJob:
            if idempotency_key is not None:
                cursor = await connection.execute(
                    "SELECT * FROM jobs WHERE idempotency_key = ?", (idempotency_key,)
                )
                existing = await cursor.fetchone()
                await cursor.close()
                if existing is not None:
                    stored = _stored_job(existing)
                    if stored.payload_fingerprint != payload_fingerprint or stored.kind != job.kind:
                        raise JobConflictError(
                            "idempotency key payload conflicts with existing Job"
                        )
                    return stored
            try:
                await connection.execute(
                    """
                    INSERT INTO jobs (
                        job_id, idempotency_key, payload_fingerprint, kind, initiator,
                        risk, state, progress, created_at, updated_at,
                        rollback_reference, attempt, error_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                    """,
                    (
                        job.id,
                        idempotency_key,
                        payload_fingerprint,
                        job.kind,
                        job.initiator,
                        job.risk.value,
                        job.state.value,
                        job.progress,
                        created_at,
                        updated_at,
                        job.rollback_reference,
                    ),
                )
            except aiosqlite.IntegrityError:
                raise JobConflictError("Job identity conflicts with existing state") from None
            await connection.execute(
                """
                INSERT INTO job_transitions
                    (job_id, from_state, to_state, progress, observed_at)
                VALUES (?, NULL, ?, ?, ?)
                """,
                (job.id, job.state.value, job.progress, created_at),
            )
            await _insert_job_event(
                connection,
                event_id=f"job-{job.id}-created",
                job_id=job.id,
                state=job.state,
                progress=job.progress,
                observed_at=job.created_at,
            )
            cursor = await connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job.id,))
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise StorageDegradedError("created Job is unavailable")
            return _stored_job(row)

        return await self._write(operation)

    async def get_job(self, job_id: str) -> StoredJob | None:
        cursor = await self._require_reader().execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        )
        row = await cursor.fetchone()
        await cursor.close()
        return _stored_job(row) if row is not None else None

    async def transition_job(
        self,
        job_id: str,
        target: JobState,
        *,
        progress: float,
        observed_at: datetime,
        event_id: str,
        error_code: str | None = None,
        rollback_reference: str | None = None,
    ) -> StoredJob:
        if not 0 <= progress <= 1 or not math.isfinite(progress):
            raise ValueError("Job progress must be finite and within [0, 1]")
        timestamp = _utc_text(observed_at)

        async def operation(connection: aiosqlite.Connection) -> StoredJob:
            cursor = await connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise KeyError("Job does not exist")
            current = _stored_job(row)
            transition_job(current.state, target)
            if progress < current.progress:
                raise ValueError("Job progress must be monotonic")
            reference = (
                rollback_reference if rollback_reference is not None else current.rollback_reference
            )
            await connection.execute(
                """
                UPDATE jobs SET state = ?, progress = ?, updated_at = ?,
                                rollback_reference = ?, error_code = ?
                WHERE job_id = ?
                """,
                (target.value, progress, timestamp, reference, error_code, job_id),
            )
            await connection.execute(
                """
                INSERT INTO job_transitions
                    (job_id, from_state, to_state, progress, observed_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (job_id, current.state.value, target.value, progress, timestamp),
            )
            await _insert_job_event(
                connection,
                event_id=event_id,
                job_id=job_id,
                state=target,
                progress=progress,
                observed_at=observed_at,
            )
            updated = await connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            updated_row = await updated.fetchone()
            await updated.close()
            if updated_row is None:
                raise StorageDegradedError("updated Job is unavailable")
            return _stored_job(updated_row)

        return await self._write(operation)

    async def request_job_cancel(
        self, job_id: str, *, observed_at: datetime, event_id: str
    ) -> StoredJob:
        current = await self.get_job(job_id)
        if current is None:
            raise KeyError("Job does not exist")
        if current.state in {JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLED}:
            return current
        target = JobState.CANCELLING if current.state is JobState.RUNNING else JobState.CANCELLED
        return await self.transition_job(
            job_id,
            target,
            progress=current.progress,
            observed_at=observed_at,
            event_id=event_id,
        )

    async def recover_jobs(
        self,
        policies: dict[str, RunningRecoveryPolicy],
        *,
        observed_at: datetime,
    ) -> tuple[StoredJob, ...]:
        if self._recovery_complete:
            return ()
        timestamp = _utc_text(observed_at)

        async def operation(connection: aiosqlite.Connection) -> tuple[StoredJob, ...]:
            cursor = await connection.execute(
                """
                SELECT * FROM jobs
                WHERE state NOT IN (?, ?, ?)
                ORDER BY created_at ASC, job_id ASC
                """,
                (JobState.SUCCEEDED.value, JobState.FAILED.value, JobState.CANCELLED.value),
            )
            rows = await cursor.fetchall()
            await cursor.close()
            recovered: list[StoredJob] = []
            for row in rows:
                current = _stored_job(row)
                if current.state is JobState.PENDING:
                    recovered.append(current)
                    continue
                policy = policies.get(current.kind, RunningRecoveryPolicy.FAIL)
                target = (
                    JobState.PENDING
                    if current.state is JobState.RUNNING and policy is RunningRecoveryPolicy.REQUEUE
                    else JobState.FAILED
                )
                attempt = current.attempt + 1
                error_code = None if target is JobState.PENDING else "runtime_interrupted"
                await connection.execute(
                    """
                    UPDATE jobs SET state = ?, updated_at = ?, attempt = ?, error_code = ?
                    WHERE job_id = ?
                    """,
                    (target.value, timestamp, attempt, error_code, current.id),
                )
                await connection.execute(
                    """
                    INSERT INTO job_transitions
                        (job_id, from_state, to_state, progress, observed_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (current.id, current.state.value, target.value, current.progress, timestamp),
                )
                await _insert_job_event(
                    connection,
                    event_id=f"job-{current.id}-recovery-{attempt}",
                    job_id=current.id,
                    state=target,
                    progress=current.progress,
                    observed_at=observed_at,
                )
                refreshed = await connection.execute(
                    "SELECT * FROM jobs WHERE job_id = ?", (current.id,)
                )
                refreshed_row = await refreshed.fetchone()
                await refreshed.close()
                if refreshed_row is not None:
                    recovered.append(_stored_job(refreshed_row))
            return tuple(recovered)

        recovered = await self._write(operation)
        self._recovery_complete = True
        return recovered

    async def replay_durable_events(
        self, *, after_sequence: int, limit: int = 100
    ) -> tuple[DurableEventRecord, ...]:
        if after_sequence < 0 or limit < 1 or limit > MAX_PAGE_SIZE:
            raise ValueError("durable event cursor or page size is invalid")
        cursor = await self._require_reader().execute(
            """
            SELECT sequence, event_id, schema_version, observed_at, priority, kind,
                   payload_json, job_id, resource_id
            FROM durable_events
            WHERE sequence > ?
            ORDER BY sequence ASC
            LIMIT ?
            """,
            (after_sequence, limit),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return tuple(
            DurableEventRecord(
                sequence=int(row[0]),
                event_id=str(row[1]),
                schema_version=int(row[2]),
                observed_at=_parse_utc(str(row[3])),
                priority=str(row[4]),
                kind=str(row[5]),
                payload_json=str(row[6]),
                job_id=str(row[7]) if row[7] is not None else None,
                resource_id=str(row[8]) if row[8] is not None else None,
            )
            for row in rows
        )

    async def close(self) -> int:
        if self._closed:
            return 0
        if self.degraded:
            self._closed = True
            return 0
        flushed = await self.flush_metrics()
        self._closed = True
        await self._queue.put(None)
        actor = self._actor
        reader = self._reader
        writer = self._writer
        if actor is not None:
            await actor
        if reader is not None:
            await reader.close()
        if writer is not None:
            await writer.close()
        return flushed

    def _require_reader(self) -> aiosqlite.Connection:
        if self._closed or self._reader is None:
            raise StorageDegradedError("runtime storage is unavailable")
        return self._reader


async def _configure(connection: aiosqlite.Connection) -> None:
    await connection.execute("PRAGMA busy_timeout = 5000")
    await connection.execute("PRAGMA foreign_keys = ON")
    cursor = await connection.execute("PRAGMA journal_mode = WAL")
    row = await cursor.fetchone()
    await cursor.close()
    if row is None or str(row[0]).lower() != "wal":
        raise StorageDegradedError("SQLite WAL mode is unavailable")
    await connection.commit()


async def _migrate(connection: aiosqlite.Connection) -> None:
    cursor = await connection.execute("PRAGMA user_version")
    row = await cursor.fetchone()
    await cursor.close()
    version = int(row[0]) if row else 0
    if version > SCHEMA_VERSION:
        raise UnsupportedSchemaError("database schema is newer than this runtime")
    if version == SCHEMA_VERSION:
        return
    if version != 0:
        raise UnsupportedSchemaError("database schema migration path is unavailable")
    await connection.executescript(
        """
        BEGIN IMMEDIATE;
        CREATE TABLE health_snapshots (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_kind TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            state TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            observed_monotonic REAL NOT NULL,
            stale INTEGER NOT NULL CHECK(stale IN (0, 1))
        );
        CREATE INDEX health_latest_idx
            ON health_snapshots(resource_kind, resource_id, observed_at DESC, sequence DESC);
        CREATE TABLE route_audits (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            selected_placement_id TEXT,
            candidate_json TEXT NOT NULL,
            rejection_json TEXT NOT NULL,
            config_revision TEXT NOT NULL
        );
        CREATE TABLE request_metrics (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            latency_ms REAL NOT NULL,
            success INTEGER NOT NULL CHECK(success IN (0, 1))
        );
        CREATE INDEX request_metrics_observed_idx ON request_metrics(observed_at);
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            idempotency_key TEXT UNIQUE,
            payload_fingerprint TEXT NOT NULL,
            kind TEXT NOT NULL,
            initiator TEXT NOT NULL,
            risk TEXT NOT NULL,
            state TEXT NOT NULL,
            progress REAL NOT NULL CHECK(progress >= 0 AND progress <= 1),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            rollback_reference TEXT,
            attempt INTEGER NOT NULL DEFAULT 0,
            error_code TEXT
        );
        CREATE TABLE job_transitions (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL REFERENCES jobs(job_id),
            from_state TEXT,
            to_state TEXT NOT NULL,
            progress REAL NOT NULL,
            observed_at TEXT NOT NULL
        );
        CREATE TABLE durable_events (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            schema_version INTEGER NOT NULL,
            observed_at TEXT NOT NULL,
            priority TEXT NOT NULL,
            kind TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            job_id TEXT,
            resource_id TEXT
        );
        CREATE TABLE config_revisions (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            revision_id TEXT NOT NULL UNIQUE,
            observed_at TEXT NOT NULL,
            rollback_reference TEXT,
            fingerprint TEXT NOT NULL
        );
        CREATE TABLE daily_metric_aggregates (
            day TEXT PRIMARY KEY,
            request_count INTEGER NOT NULL,
            error_count INTEGER NOT NULL,
            latency_sum_ms REAL NOT NULL
        );
        PRAGMA user_version = 1;
        COMMIT;
        """
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def _utc_text(value: datetime) -> str:
    return _utc(value).isoformat(timespec="microseconds")


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return _utc(parsed)


def _stored_job(row: Any) -> StoredJob:
    return StoredJob(
        id=str(row[0]),
        idempotency_key=str(row[1]) if row[1] is not None else None,
        payload_fingerprint=str(row[2]),
        kind=str(row[3]),
        initiator=str(row[4]),
        risk=RiskLevel(str(row[5])),
        state=JobState(str(row[6])),
        progress=float(row[7]),
        created_at=_parse_utc(str(row[8])),
        updated_at=_parse_utc(str(row[9])),
        rollback_reference=str(row[10]) if row[10] is not None else None,
        attempt=int(row[11]),
        error_code=str(row[12]) if row[12] is not None else None,
    )


async def _insert_job_event(
    connection: aiosqlite.Connection,
    *,
    event_id: str,
    job_id: str,
    state: JobState,
    progress: float,
    observed_at: datetime,
) -> None:
    await connection.execute(
        """
        INSERT INTO durable_events (
            event_id, schema_version, observed_at, priority, kind,
            payload_json, job_id, resource_id
        ) VALUES (?, 1, ?, 'high', ?, ?, ?, NULL)
        """,
        (
            event_id,
            _utc_text(observed_at),
            f"job.{state.value}",
            json.dumps(
                {"progress": progress, "state": state.value},
                separators=(",", ":"),
                sort_keys=True,
            ),
            job_id,
        ),
    )
