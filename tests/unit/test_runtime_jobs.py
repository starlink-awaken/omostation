from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib.util import find_spec
from pathlib import Path

import pytest

from omlxc.domain import Job, JobState, RiskLevel


def _job(*, job_id: str = "job-1", state: JobState = JobState.PENDING) -> Job:
    now = datetime(2026, 8, 11, 8, tzinfo=UTC)
    return Job(
        id=job_id,
        kind="placement.load",
        initiator="operator",
        risk=RiskLevel.R1,
        state=state,
        progress=0.0,
        created_at=now,
        updated_at=now,
        rollback_reference="rollback:placement-a",
    )


def test_runtime_job_repository_is_available() -> None:
    assert find_spec("omlxc.storage.jobs") is not None


@pytest.mark.asyncio
async def test_job_idempotency_returns_same_job_and_rejects_payload_conflict(
    tmp_path: Path,
) -> None:
    from omlxc.storage import JobConflictError, SQLiteRuntimeStore

    store = await SQLiteRuntimeStore.open(tmp_path / "state.db")
    first = await store.create_job(
        _job(), idempotency_key="load-a", payload_fingerprint="sha256:aaa"
    )
    duplicate = await store.create_job(
        _job(job_id="job-other"),
        idempotency_key="load-a",
        payload_fingerprint="sha256:aaa",
    )
    assert duplicate == first
    with pytest.raises(JobConflictError):
        await store.create_job(
            _job(job_id="job-conflict"),
            idempotency_key="load-a",
            payload_fingerprint="sha256:different",
        )
    await store.close()


@pytest.mark.asyncio
async def test_job_transition_progress_and_durable_event_commit_atomically(tmp_path: Path) -> None:
    from omlxc.storage import SQLiteRuntimeStore

    store = await SQLiteRuntimeStore.open(tmp_path / "state.db")
    await store.create_job(_job(), idempotency_key="load-a", payload_fingerprint="sha256:a")
    at = datetime(2026, 8, 11, 8, tzinfo=UTC) + timedelta(seconds=1)
    planning = await store.transition_job(
        "job-1", JobState.PLANNING, progress=0.2, observed_at=at, event_id="event-plan"
    )
    assert planning.state is JobState.PLANNING
    assert planning.progress == 0.2
    with pytest.raises(ValueError, match="monotonic"):
        await store.transition_job(
            "job-1",
            JobState.RUNNING,
            progress=0.1,
            observed_at=at + timedelta(seconds=1),
            event_id="event-backward",
        )
    events = await store.replay_durable_events(after_sequence=0)
    assert [event.event_id for event in events] == ["job-job-1-created", "event-plan"]
    await store.close()


@pytest.mark.asyncio
async def test_cancel_is_cooperative_repeatable_and_terminal_noop(tmp_path: Path) -> None:
    from omlxc.storage import SQLiteRuntimeStore

    store = await SQLiteRuntimeStore.open(tmp_path / "state.db")
    await store.create_job(_job(), idempotency_key="load-a", payload_fingerprint="sha256:a")
    cancelled = await store.request_job_cancel(
        "job-1", observed_at=datetime(2026, 8, 11, 9, tzinfo=UTC), event_id="cancel-1"
    )
    repeated = await store.request_job_cancel(
        "job-1", observed_at=datetime(2026, 8, 11, 9, tzinfo=UTC), event_id="cancel-2"
    )
    assert cancelled.state is JobState.CANCELLED
    assert repeated == cancelled
    await store.close()


@pytest.mark.asyncio
async def test_restart_recovers_only_nonterminal_jobs_by_explicit_operation_policy(
    tmp_path: Path,
) -> None:
    from omlxc.storage import RunningRecoveryPolicy, SQLiteRuntimeStore

    database = tmp_path / "state.db"
    store = await SQLiteRuntimeStore.open(database)
    await store.create_job(_job(), idempotency_key="load-a", payload_fingerprint="sha256:a")
    at = datetime(2026, 8, 11, 9, tzinfo=UTC)
    await store.transition_job(
        "job-1", JobState.PLANNING, progress=0.1, observed_at=at, event_id="plan"
    )
    await store.transition_job(
        "job-1",
        JobState.RUNNING,
        progress=0.2,
        observed_at=at + timedelta(seconds=1),
        event_id="run",
    )
    await store.close()

    reopened = await SQLiteRuntimeStore.open(database)
    recovered = await reopened.recover_jobs(
        {"placement.load": RunningRecoveryPolicy.REQUEUE},
        observed_at=at + timedelta(seconds=2),
    )
    assert [(job.id, job.state, job.attempt) for job in recovered] == [
        ("job-1", JobState.PENDING, 1)
    ]
    assert await reopened.recover_jobs({}, observed_at=at + timedelta(seconds=3)) == ()
    await reopened.close()
