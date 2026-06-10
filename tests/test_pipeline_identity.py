from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from agora.core.event_bus import EventBus
from agora.core.registry import ServiceRegistry
from agora.pipeline import Pipeline


class _FakeRouter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def route(self, tool_name: str, args: dict, caller_id="unknown") -> dict[str, object]:
        self.calls.append({"tool_name": tool_name, "args": args, "caller_id": caller_id})
        return {"tool": tool_name, "ok": True}


def _make_pipeline(event_bus: EventBus | None = None) -> tuple[Pipeline, _FakeRouter]:
    registry = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test.json"))
    router = _FakeRouter()
    pipeline = Pipeline(registry, router, event_bus=event_bus)
    pipeline.define(
        "identity-aware",
        [{"tool": "tool.alpha", "args": {"goal": "{{goal}}"}, "output_as": "alpha"}],
    )
    return pipeline, router


def test_run_passes_structured_identity_to_router() -> None:
    pipeline, router = _make_pipeline()
    identity = {"subject_type": "user", "subject_id": "alice", "tenant": "tenant-a"}

    asyncio.run(pipeline.run("identity-aware", {"goal": "ship it"}, caller_identity=identity))

    assert router.calls == [
        {
            "tool_name": "tool.alpha",
            "args": {"goal": "ship it"},
            "caller_id": identity,
        }
    ]


def test_pipeline_events_include_normalized_identity_payload() -> None:
    event_bus = EventBus(storage_path=str(Path(tempfile.mkdtemp()) / "events.json"))
    pipeline, _ = _make_pipeline(event_bus=event_bus)
    identity = {"subject_type": "user", "subject_id": "alice", "tenant": "tenant-a"}

    asyncio.run(pipeline.run("identity-aware", {"goal": "ship it"}, caller_identity=identity))

    events = event_bus.get_event_log(limit=20)
    started = next(
        event
        for event in events
        if event["type"] == "pipeline:started" and event["payload"]["pipeline"] == "identity-aware"
    )
    completed = next(
        event
        for event in events
        if event["type"] == "pipeline:completed" and event["payload"]["pipeline"] == "identity-aware"
    )

    assert started["payload"]["identity"]["subject_id"] == "alice"
    assert started["payload"]["identity"]["subject_type"] == "user"
    assert started["payload"]["identity"]["tenant"] == "tenant-a"
    assert completed["payload"]["identity"]["subject_id"] == "alice"
    assert completed["payload"]["identity"]["subject_type"] == "user"
