from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from omlxc.events import EventBus, EventPriority, RuntimeEvent
from omlxc.storage import SQLiteRuntimeStore


def _event(*, kind: str = "job.running") -> RuntimeEvent:
    return RuntimeEvent.create(
        event_id="same-event-id",
        priority=EventPriority.HIGH,
        kind=kind,
        timestamp=datetime(2026, 8, 11, tzinfo=UTC),
        payload={"state": "running"},
        job_id="job-1",
    )


@pytest.mark.asyncio
async def test_durable_event_same_content_is_idempotent_but_conflict_never_publishes_live(
    tmp_path: Path,
) -> None:
    from omlxc.storage import EventConflictError

    store = await SQLiteRuntimeStore.open(tmp_path / "state.db")
    bus = EventBus(capacity=4)
    subscription = bus.subscribe()
    first = await bus.publish_durable(store, _event())
    assert (await subscription.receive()).event_id == "same-event-id"
    duplicate = await bus.publish_durable(store, _event())
    assert duplicate == first
    assert (await subscription.receive()).event_id == "same-event-id"

    with pytest.raises(EventConflictError):
        await bus.publish_durable(store, _event(kind="job.failed"))
    marker = RuntimeEvent.create(
        event_id="marker",
        priority=EventPriority.LOW,
        kind="test.marker",
        timestamp=datetime(2026, 8, 11, tzinfo=UTC),
        payload={},
    )
    await bus.publish(marker)
    assert await subscription.receive() == marker
    replay = await store.replay_durable_events(after_sequence=0)
    assert len(replay) == 1
    assert replay[0].sequence == first
    assert replay[0].kind == "job.running"
    await subscription.close()
    await bus.close()
    await store.close()
