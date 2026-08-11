from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from omlxc.domain import Job, JobState, RiskLevel
from omlxc.storage import SQLiteRuntimeStore


def _job(job_id: str) -> Job:
    now = datetime(2026, 8, 11, 8, tzinfo=UTC)
    return Job(
        id=job_id,
        kind="placement.load",
        initiator="operator",
        risk=RiskLevel.R1,
        state=JobState.PENDING,
        progress=0.0,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("initial", "expected"),
    [
        (JobState.PENDING, JobState.CANCELLED),
        (JobState.PLANNING, JobState.CANCELLED),
        (JobState.AWAITING_CONFIRMATION, JobState.CANCELLED),
        (JobState.RUNNING, JobState.CANCELLING),
        (JobState.CANCELLING, JobState.CANCELLING),
        (JobState.SUCCEEDED, JobState.SUCCEEDED),
        (JobState.FAILED, JobState.FAILED),
        (JobState.CANCELLED, JobState.CANCELLED),
    ],
)
async def test_repeated_concurrent_cancel_is_one_atomic_transition_and_event(
    tmp_path: Path,
    initial: JobState,
    expected: JobState,
) -> None:
    store = await SQLiteRuntimeStore.open(tmp_path / f"{initial.value}.db")
    created = await store.create_job(
        _job(f"job-{initial.value}"),
        idempotency_key=f"key-{initial.value}",
        payload_fingerprint="sha256:cancel",
    )
    at = created.created_at + timedelta(seconds=1)
    if initial is not JobState.PENDING:
        path = [JobState.PLANNING]
        if initial is JobState.AWAITING_CONFIRMATION:
            path.append(JobState.AWAITING_CONFIRMATION)
        elif initial is not JobState.PLANNING:
            path.append(JobState.RUNNING)
        if initial is JobState.CANCELLING:
            path.append(JobState.CANCELLING)
        elif initial in {JobState.SUCCEEDED, JobState.FAILED}:
            path.append(initial)
        elif initial is JobState.CANCELLED:
            path = [JobState.CANCELLED]
        for index, state in enumerate(path):
            await store.transition_job(
                created.id,
                state,
                progress=0.1 * (index + 1),
                observed_at=at + timedelta(seconds=index),
                event_id=f"setup-{initial.value}-{state.value}",
            )

    before = await store.replay_durable_events(after_sequence=0)
    calls = [
        asyncio.create_task(
            store.request_job_cancel(
                created.id,
                observed_at=at + timedelta(seconds=10),
                event_id=f"cancel-{initial.value}-{index}",
            )
        )
        for index in range(8)
    ]
    try:
        results = await asyncio.gather(*calls, return_exceptions=True)
        assert not [result for result in results if isinstance(result, BaseException)]
        states = {result.state for result in results if not isinstance(result, BaseException)}
        assert states == {expected}
        after = await store.replay_durable_events(after_sequence=0)
        expected_new_events = (
            1
            if initial
            in {
                JobState.PENDING,
                JobState.PLANNING,
                JobState.AWAITING_CONFIRMATION,
                JobState.RUNNING,
            }
            else 0
        )
        assert len(after) - len(before) == expected_new_events
    finally:
        await store.close()
