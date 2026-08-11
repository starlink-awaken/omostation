from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from omlxc.domain import Job, JobState, RiskLevel
from omlxc.storage import SQLiteRuntimeStore, StorageDegradedError


def _rewrite_schema(database: Path, table_or_index: str, old: str, new: str) -> None:
    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE name = ?", (table_or_index,)
    ).fetchone()
    assert row is not None and old in str(row[0])
    version = int(connection.execute("PRAGMA schema_version").fetchone()[0])
    connection.execute("PRAGMA writable_schema = ON")
    connection.execute(
        "UPDATE sqlite_master SET sql = replace(sql, ?, ?) WHERE name = ?",
        (old, new, table_or_index),
    )
    connection.execute(f"PRAGMA schema_version = {version + 1}")
    connection.execute("PRAGMA writable_schema = OFF")
    connection.commit()
    connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("object_name", "old", "new"),
    [
        ("health_snapshots", "state TEXT NOT NULL", "state BLOB NOT NULL"),
        ("health_snapshots", "resource_id TEXT NOT NULL", "resource_id TEXT"),
        ("jobs", "DEFAULT 0", "DEFAULT 1"),
        ("health_snapshots", "CHECK(stale IN (0, 1))", "CHECK(stale IN (0, 1, 2))"),
        (
            "job_transitions",
            "REFERENCES jobs(job_id)",
            "REFERENCES jobs(job_id) ON DELETE CASCADE",
        ),
        (
            "health_latest_idx",
            "CREATE INDEX health_latest_idx",
            "CREATE UNIQUE INDEX health_latest_idx",
        ),
    ],
)
async def test_schema_metadata_or_constraint_drift_is_quarantined(
    tmp_path: Path, object_name: str, old: str, new: str
) -> None:
    database = tmp_path / f"{object_name}.db"
    store = await SQLiteRuntimeStore.open(database)
    await store.close()
    _rewrite_schema(database, object_name, old, new)

    degraded = await SQLiteRuntimeStore.open(
        database, quarantine_suffix_factory=lambda: "schema-invariant"
    )
    try:
        assert degraded.degraded
        assert not database.exists()
        assert (tmp_path / f"{object_name}.db.corrupt-schema-invariant").exists()
    finally:
        await degraded.close()


def _seed_all_persistent_values(database: Path) -> None:
    timestamp = "2026-08-11T00:00:00.000000+00:00"
    connection = sqlite3.connect(database)
    connection.executescript(
        f"""
        INSERT INTO health_snapshots
            (resource_kind, resource_id, state, observed_at, observed_monotonic, stale)
        VALUES ('node', 'node-a', 'healthy', '{timestamp}', 1, 0);
        INSERT INTO route_audits
            (request_id, observed_at, selected_placement_id, candidate_json,
             rejection_json, config_revision)
        VALUES ('req', '{timestamp}', NULL, '["p1"]', '{{}}', 'cfg');
        INSERT INTO request_metrics (request_id, observed_at, latency_ms, success)
        VALUES ('req', '{timestamp}', 1, 1);
        INSERT INTO jobs
            (job_id, idempotency_key, payload_fingerprint, kind, initiator, risk,
             state, progress, created_at, updated_at, attempt)
        VALUES ('job', NULL, 'sha256:x', 'placement.load', 'operator', 'r1',
                'pending', 0, '{timestamp}', '{timestamp}', 0);
        INSERT INTO job_transitions (job_id, from_state, to_state, progress, observed_at)
        VALUES ('job', NULL, 'pending', 0, '{timestamp}');
        INSERT INTO durable_events
            (event_id, schema_version, observed_at, priority, kind, payload_json)
        VALUES ('event', 1, '{timestamp}', 'high', 'job.pending', '{{}}');
        INSERT INTO config_revisions
            (revision_id, observed_at, rollback_reference, config_json, fingerprint)
        VALUES ('cfg', '{timestamp}', NULL, '{{}}',
                'sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a');
        INSERT INTO daily_metric_aggregates
            (day, request_count, error_count, latency_sum_ms)
        VALUES ('2026-08-11', 1, 0, 1);
        """
    )
    connection.commit()
    connection.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("health_snapshots", "observed_at"),
        ("route_audits", "observed_at"),
        ("request_metrics", "observed_at"),
        ("jobs", "created_at"),
        ("jobs", "updated_at"),
        ("job_transitions", "observed_at"),
        ("durable_events", "observed_at"),
        ("config_revisions", "observed_at"),
    ],
)
async def test_open_quarantines_each_noncanonical_persistent_timestamp(
    tmp_path: Path, table: str, column: str
) -> None:
    database = tmp_path / f"{table}-{column}.db"
    store = await SQLiteRuntimeStore.open(database)
    await store.close()
    _seed_all_persistent_values(database)
    connection = sqlite3.connect(database)
    connection.execute(f"UPDATE {table} SET {column} = ?", ("2026-08-11T00:00:00",))
    connection.commit()
    connection.close()

    degraded = await SQLiteRuntimeStore.open(
        database, quarantine_suffix_factory=lambda: "bad-value"
    )
    try:
        assert degraded.degraded
        assert not database.exists()
    finally:
        await degraded.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("table", "column", "damage"),
    [
        ("route_audits", "candidate_json", "candidate-shape"),
        ("route_audits", "rejection_json", "rejection-shape"),
        ("durable_events", "payload_json", "oversize"),
        ("config_revisions", "config_json", "oversize"),
    ],
)
async def test_open_quarantines_unsafe_persistent_json(
    tmp_path: Path, table: str, column: str, damage: str
) -> None:
    database = tmp_path / f"json-{table}-{column}.db"
    store = await SQLiteRuntimeStore.open(database)
    await store.close()
    _seed_all_persistent_values(database)
    value = {
        "candidate-shape": "[1]",
        "rejection-shape": '{"p1":1}',
        "oversize": '{"blob":"' + "x" * (64 * 1024) + '"}',
    }[damage]
    connection = sqlite3.connect(database)
    connection.execute(f"UPDATE {table} SET {column} = ?", (value,))
    connection.commit()
    connection.close()

    degraded = await SQLiteRuntimeStore.open(database, quarantine_suffix_factory=lambda: "bad-json")
    try:
        assert degraded.degraded
    finally:
        await degraded.close()


@pytest.mark.asyncio
async def test_open_quarantines_config_fingerprint_mismatch(tmp_path: Path) -> None:
    database = tmp_path / "fingerprint.db"
    store = await SQLiteRuntimeStore.open(database)
    await store.close()
    _seed_all_persistent_values(database)
    connection = sqlite3.connect(database)
    connection.execute("UPDATE config_revisions SET fingerprint = ?", ("sha256:" + "0" * 64,))
    connection.commit()
    connection.close()

    degraded = await SQLiteRuntimeStore.open(
        database, quarantine_suffix_factory=lambda: "bad-fingerprint"
    )
    try:
        assert degraded.degraded
        assert not database.exists()
    finally:
        await degraded.close()


@pytest.mark.asyncio
async def test_read_conversion_failure_is_content_free_storage_error(tmp_path: Path) -> None:
    database = tmp_path / "read-race.db"
    store = await SQLiteRuntimeStore.open(database)
    now = datetime(2026, 8, 11, tzinfo=UTC)
    await store.create_job(
        Job(
            id="job",
            kind="placement.load",
            initiator="operator",
            risk=RiskLevel.R1,
            state=JobState.PENDING,
            progress=0,
            created_at=now,
            updated_at=now,
        ),
        idempotency_key=None,
        payload_fingerprint="sha256:x",
    )
    try:
        connection = sqlite3.connect(database)
        connection.execute("UPDATE jobs SET state = 'secret-invalid-state' WHERE job_id = 'job'")
        connection.commit()
        connection.close()

        with pytest.raises(StorageDegradedError) as raised:
            await store.get_job("job")
        assert str(raised.value) == "stored runtime value is invalid"
    finally:
        await store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "health-time",
        "route-json",
        "config-json",
        "config-fingerprint",
        "event-time",
        "event-conflict-read",
        "aggregate-day",
    ],
)
async def test_every_repository_read_maps_conversion_failure_to_fixed_error(
    tmp_path: Path, case: str
) -> None:
    database = tmp_path / f"read-{case}.db"
    created = await SQLiteRuntimeStore.open(database)
    await created.close()
    _seed_all_persistent_values(database)
    store = await SQLiteRuntimeStore.open(database)
    try:
        mutation = {
            "health-time": ("UPDATE health_snapshots SET observed_at = ?", "not-a-time"),
            "route-json": ("UPDATE route_audits SET candidate_json = ?", "[1]"),
            "config-json": ("UPDATE config_revisions SET config_json = ?", "[]"),
            "config-fingerprint": (
                "UPDATE config_revisions SET fingerprint = ?",
                "sha256:" + "0" * 64,
            ),
            "event-time": ("UPDATE durable_events SET observed_at = ?", "not-a-time"),
            "event-conflict-read": ("UPDATE durable_events SET payload_json = ?", "[]"),
            "aggregate-day": (
                "UPDATE daily_metric_aggregates SET request_count = ?",
                "not-a-count",
            ),
        }[case]
        connection = sqlite3.connect(database)
        connection.execute(mutation[0], (mutation[1],))
        connection.commit()
        connection.close()

        async def read() -> object:
            if case == "health-time":
                return await store.latest_health("node", "node-a")
            if case == "route-json":
                return await store.list_route_audits(after_sequence=0)
            if case in {"config-json", "config-fingerprint"}:
                return await store.latest_config_revision()
            if case == "event-time":
                return await store.replay_durable_events(after_sequence=0)
            if case == "event-conflict-read":
                return await store.append_durable_event(
                    event_id="event",
                    schema_version=1,
                    observed_at=datetime(2026, 8, 11, tzinfo=UTC),
                    priority="high",
                    kind="job.pending",
                    payload_json="{}",
                    job_id=None,
                    resource_id=None,
                )
            return await store.daily_metric_aggregate(datetime(2026, 8, 11).date())

        with pytest.raises(StorageDegradedError) as raised:
            await read()
        assert str(raised.value) == "stored runtime value is invalid"
    finally:
        await store.close()
