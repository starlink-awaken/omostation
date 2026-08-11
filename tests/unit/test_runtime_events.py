from __future__ import annotations

import math
from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path

import anyio
import pytest


def test_runtime_events_module_is_available() -> None:
    assert find_spec("omlxc.events") is not None


def test_secret_like_text_is_recursively_redacted_even_under_innocent_key() -> None:
    from omlxc.events import EventPriority, RuntimeEvent

    event = RuntimeEvent.create(
        event_id="event-redaction",
        priority=EventPriority.HIGH,
        kind="adapter.failure",
        timestamp=datetime(2026, 8, 11, tzinfo=UTC),
        payload={"detail": {"message": "Authorization: Bearer top-secret"}},
    )
    assert event.payload["detail"]["message"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_subscribers_are_independent_and_low_priority_backpressure_is_counted() -> None:
    from omlxc.events import EventBus, EventPriority, RuntimeEvent

    bus = EventBus(capacity=1)
    fast = bus.subscribe()
    slow = bus.subscribe()
    event1 = RuntimeEvent.create(
        event_id="event-1",
        priority=EventPriority.LOW,
        kind="metric.sample",
        timestamp=datetime(2026, 8, 11, tzinfo=UTC),
        payload={"latency_ms": 4.0},
    )
    event2 = RuntimeEvent.create(
        event_id="event-2",
        priority=EventPriority.LOW,
        kind="metric.sample",
        timestamp=datetime(2026, 8, 11, tzinfo=UTC),
        payload={"latency_ms": 5.0},
    )
    await bus.publish(event1)
    assert await fast.receive() == event1
    outcome = await bus.publish(event2)
    assert outcome.delivered == 1
    assert outcome.dropped == 1
    assert bus.dropped_low_priority == 1
    assert await fast.receive() == event2
    assert await slow.receive() == event1
    await fast.close()
    await slow.close()
    await bus.close()


@pytest.mark.asyncio
async def test_payload_is_deeply_immutable_redacted_and_rejects_unsafe_values() -> None:
    from omlxc.events import EventPriority, InvalidEventError, RuntimeEvent

    payload = {"nested": [{"authorization": "Bearer secret", "ok": 1}]}
    event = RuntimeEvent.create(
        event_id="event-safe",
        priority=EventPriority.HIGH,
        kind="security.denied",
        timestamp=datetime(2026, 8, 11, tzinfo=UTC),
        payload=payload,
    )
    payload["nested"] = []
    assert event.payload["nested"][0]["authorization"] == "[REDACTED]"
    with pytest.raises(TypeError):
        event.payload["new"] = "value"  # type: ignore[index]
    with pytest.raises(InvalidEventError):
        RuntimeEvent.create(
            event_id="bad-number",
            priority=EventPriority.LOW,
            kind="metric.sample",
            timestamp=datetime(2026, 8, 11, tzinfo=UTC),
            payload={"value": math.inf},
        )
    with pytest.raises(InvalidEventError):
        RuntimeEvent.create(
            event_id="bad-time",
            priority=EventPriority.LOW,
            kind="metric.sample",
            timestamp=datetime(2026, 8, 11),
            payload={},
        )
    with pytest.raises(InvalidEventError, match="size"):
        RuntimeEvent.create(
            event_id="oversized",
            priority=EventPriority.LOW,
            kind="metric.sample",
            timestamp=datetime(2026, 8, 11, tzinfo=UTC),
            payload={"blob": "x" * (64 * 1024)},
        )
    with pytest.raises(InvalidEventError, match="schema"):
        RuntimeEvent.create(
            event_id="future-schema",
            priority=EventPriority.LOW,
            kind="metric.sample",
            timestamp=datetime(2026, 8, 11, tzinfo=UTC),
            payload={},
            schema_version=2,
        )


@pytest.mark.asyncio
async def test_high_priority_event_is_durable_before_publish_and_cursor_replays(
    tmp_path: Path,
) -> None:
    from omlxc.events import EventBus, EventPriority, RuntimeEvent
    from omlxc.storage import SQLiteRuntimeStore

    store = await SQLiteRuntimeStore.open(tmp_path / "state.db")
    bus = EventBus(capacity=1)
    subscriber = bus.subscribe()
    event = RuntimeEvent.create(
        event_id="job-event-1",
        priority=EventPriority.HIGH,
        kind="job.running",
        timestamp=datetime(2026, 8, 11, tzinfo=UTC),
        payload={"state": "running"},
        job_id="job-1",
    )
    sequence = await bus.publish_durable(store, event)
    assert sequence == 1
    assert await subscriber.receive() == event
    replay = await store.replay_durable_events(after_sequence=0, limit=50)
    assert [(item.sequence, item.event_id, item.kind) for item in replay] == [
        (1, "job-event-1", "job.running")
    ]
    await subscriber.close()
    await bus.close()
    await store.close()


@pytest.mark.asyncio
async def test_subscriber_close_unblocks_receive_deterministically() -> None:
    from omlxc.events import EventBus, EventSubscriptionClosed

    bus = EventBus(capacity=1)
    subscription = bus.subscribe()
    ready = anyio.Event()

    async def receiver() -> None:
        ready.set()
        with pytest.raises(EventSubscriptionClosed):
            await subscription.receive()

    async with anyio.create_task_group() as group:
        group.start_soon(receiver)
        await ready.wait()
        await subscription.close()
    await bus.close()


@pytest.mark.asyncio
async def test_multiple_producers_reach_multiple_subscribers_without_unbounded_state() -> None:
    from omlxc.events import EventBus, EventPriority, RuntimeEvent

    bus = EventBus(capacity=20)
    first = bus.subscribe()
    second = bus.subscribe()

    async def producer(index: int) -> None:
        await bus.publish(
            RuntimeEvent.create(
                event_id=f"event-{index}",
                priority=EventPriority.LOW,
                kind="metric.sample",
                timestamp=datetime(2026, 8, 11, tzinfo=UTC),
                payload={"index": index},
            )
        )

    async with anyio.create_task_group() as group:
        for index in range(20):
            group.start_soon(producer, index)
    first_ids = {str((await first.receive()).event_id) for _ in range(20)}
    second_ids = {str((await second.receive()).event_id) for _ in range(20)}
    expected = {f"event-{index}" for index in range(20)}
    assert first_ids == second_ids == expected
    await first.close()
    await second.close()
    await bus.close()
