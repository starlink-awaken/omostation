"""Tests for ecos.services.events_sse."""

import json


from ecos.services import events_sse


class TestMakeEvent:
    def test_basic_event(self):
        event = events_sse.make_event("bos://memory/kos/search")
        assert event["bos_uri"] == "bos://memory/kos/search"
        assert event["uri"] == "bos://memory/kos/search"
        assert event["source"] == "ecos.services.events_sse"
        assert event["data"] == {}
        assert "timestamp" in event

    def test_with_data(self):
        event = events_sse.make_event("bos://vault/_state", {"status": "ok"})
        assert event["data"] == {"status": "ok"}

    def test_custom_source(self):
        event = events_sse.make_event("bos://test", source="custom.source")
        assert event["source"] == "custom.source"


class TestWriteEvent:
    def test_writes_to_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(events_sse, "_EVENTS_FILE", tmp_path / "events.jsonl")
        event = events_sse.write_event("bos://test/event", {"key": "value"})
        assert event["bos_uri"] == "bos://test/event"
        assert event["data"] == {"key": "value"}
        lines = (tmp_path / "events.jsonl").read_text().strip().split("\n")
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["bos_uri"] == "bos://test/event"

    def test_appends_multiple(self, tmp_path, monkeypatch):
        monkeypatch.setattr(events_sse, "_EVENTS_FILE", tmp_path / "events.jsonl")
        events_sse.write_event("bos://a")
        events_sse.write_event("bos://b")
        events_sse.write_event("bos://c")
        lines = (tmp_path / "events.jsonl").read_text().strip().split("\n")
        assert len(lines) == 3

    def test_creates_parent_dir(self, tmp_path, monkeypatch):
        target = tmp_path / "deep" / "nested" / "events.jsonl"
        monkeypatch.setattr(events_sse, "_EVENTS_FILE", target)
        events_sse.write_event("bos://test")
        assert target.exists()
