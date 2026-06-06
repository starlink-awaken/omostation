"""Tests for EventBus — publish/subscribe/log engine."""

import tempfile
from pathlib import Path

from agora.core.event_bus import EventBus


def _new_bus():
    return EventBus(storage_path=str(Path(tempfile.mkdtemp()) / "test-events.json"))


class TestEventBusPublish:
    def test_publish_returns_event_id(self):
        bus = _new_bus()
        eid = bus.publish("test:done", {"ok": True}, "test-src")
        assert eid.startswith("evt_")

    def test_publish_stores_event(self):
        bus = _new_bus()
        bus.publish("index:done", {"docs": 100}, "kos")
        events = bus.get_event_log(10)
        assert len(events) == 1
        assert events[0]["type"] == "index:done"
        assert events[0]["payload"]["docs"] == 100
        assert events[0]["source"] == "kos"

    def test_publish_default_source(self):
        bus = _new_bus()
        bus.publish("test", {})
        events = bus.get_event_log(1)
        assert events[0]["source"] == "unknown"


class TestEventBusSubscribe:
    def test_subscribe_exact_match(self):
        bus = _new_bus()
        bus.subscribe("svc1", "index:done")
        bus.publish("index:done", {"x": 1}, "kos")
        sids = bus.list_subscriptions()
        assert len(sids) == 1
        assert sids[0]["pattern"] == "index:done"

    def test_subscribe_prefix_match(self):
        bus = _new_bus()
        bus.subscribe("svc1", "index:*")
        bus.publish("index:done", {}, "kos")
        sids = bus.list_subscriptions()
        assert sids[0]["pattern"] == "index:*"

    def test_subscribe_catch_all(self):
        bus = _new_bus()
        bus.subscribe("svc1", "*")
        bus.publish("anything.here", {}, "x")
        sids = bus.list_subscriptions()
        assert len(sids) == 1

    def test_unsubscribe(self):
        bus = _new_bus()
        sid = bus.subscribe("svc1", "test:*")
        assert bus.unsubscribe(sid) is True
        assert bus.unsubscribe("nonexistent") is False
        assert len(bus.list_subscriptions()) == 0

    def test_multiple_subscriptions(self):
        bus = _new_bus()
        bus.subscribe("a", "index:done")
        bus.subscribe("b", "index:*")
        bus.subscribe("c", "*")
        assert len(bus.list_subscriptions()) == 3


class TestEventBusLog:
    def test_empty_log(self):
        bus = _new_bus()
        assert bus.get_event_log(10) == []

    def test_log_limit(self):
        bus = _new_bus()
        for i in range(10):
            bus.publish(f"test:{i}", {"i": i})
        assert len(bus.get_event_log(5)) == 5
        assert len(bus.get_event_log(20)) == 10

    def test_log_since_filter(self):
        bus = _new_bus()
        bus.publish("test:1", {"n": 1})
        # Use a timestamp from before second event
        bus.publish("test:2", {"n": 2})
        since = "2020-01-01T00:00:00Z"
        filtered = bus.get_event_log(10, since=since)
        assert len(filtered) == 2


class TestEventBusMatch:
    def test_match_exact(self):
        bus = _new_bus()
        assert bus._match("index:done", "index:done") is True
        assert bus._match("index:done", "index:other") is False

    def test_match_prefix(self):
        bus = _new_bus()
        assert bus._match("index:*", "index:done") is True
        assert bus._match("index:*", "index:progress") is True
        assert bus._match("index:*", "other:done") is False

    def test_match_catch_all(self):
        bus = _new_bus()
        assert bus._match("*", "anything") is True
