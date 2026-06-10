"""Tests for Pipeline + EventBus integration.

EventBus is HTTP POST based (service-to-service via callback_url).
In-memory verification uses get_event_log() to assert events were published.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
from agora.core.event_bus import EventBus
from agora.core.registry import ServiceRegistry
from agora.core.router import Router
from agora.pipeline import Pipeline


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def pipeline(event_bus):
    reg = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test.json"))
    router = Router(reg)
    router.add_route("test.tool", "test")
    pl = Pipeline(reg, router, event_bus=event_bus)
    return pl


class TestPipelineEventBusIntegration:
    def test_publishes_started_event(self, pipeline, event_bus):
        asyncio.run(pipeline.run("derive-check", {}))
        events = event_bus.get_event_log(limit=100)
        assert any(e["type"] == "pipeline:started" for e in events)

    def test_publishes_completed_event(self, pipeline, event_bus):
        asyncio.run(pipeline.run("derive-check", {}))
        events = event_bus.get_event_log(limit=100)
        assert any(e["type"] == "pipeline:completed" for e in events)

    def test_started_payload_has_pipeline_name(self, pipeline, event_bus):
        asyncio.run(pipeline.run("derive-check", {}))
        events = event_bus.get_event_log(limit=100)
        derive_started = [
            e
            for e in events
            if e.get("payload", {}).get("pipeline") == "derive-check" and e["type"] == "pipeline:started"
        ]
        assert len(derive_started) >= 1

    def test_started_payload_has_step_count(self, pipeline, event_bus):
        asyncio.run(pipeline.run("full-pipeline", {}))
        events = event_bus.get_event_log(limit=100)
        started = [
            e
            for e in events
            if e["type"] == "pipeline:started" and e.get("payload", {}).get("pipeline") == "full-pipeline"
        ]
        assert len(started) > 0
        assert "step_count" in started[0]["payload"]

    def test_completed_payload_has_pipeline_name(self, pipeline, event_bus):
        asyncio.run(pipeline.run("derive-check", {}))
        events = event_bus.get_event_log(limit=100)
        derive_completed = [
            e
            for e in events
            if e.get("payload", {}).get("pipeline") == "derive-check" and e["type"] == "pipeline:completed"
        ]
        assert len(derive_completed) >= 1

    def test_pipeline_list_works(self, pipeline):
        names = pipeline.list_pipelines()
        assert "derive-check" in names
        assert "full-pipeline" in names

    def test_created_without_eventbus_does_not_crash(self):
        reg = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test.json"))
        pl = Pipeline(reg, Router(reg))
        result = asyncio.run(pl.run("derive-check", {}))
        assert result is not None

    def test_multiple_pipeline_runs_publish_events(self, pipeline, event_bus):
        asyncio.run(pipeline.run("derive-check", {}))
        asyncio.run(pipeline.run("full-pipeline", {}))
        events = event_bus.get_event_log(limit=100)
        started = [e for e in events if e["type"] == "pipeline:started"]
        assert len(started) >= 2
