"""Tests for the AetherForge-to-OMO governed write bridge."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from swarm_engine import governed_io


def test_write_json_uses_omo_broker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes: list[tuple[Path, str]] = []

    def fake_write(path: Path, payload: str) -> None:
        writes.append((path, payload))

    monkeypatch.setattr(
        governed_io,
        "_omo_primitives",
        lambda _root: (fake_write, object, object),
    )
    target = tmp_path / ".omo" / "state" / "probe.json"

    governed_io.write_json(target, {"ok": True}, sort_keys=True)

    assert writes[0][0] == target
    assert json.loads(writes[0][1]) == {"ok": True}


def test_append_jsonl_uses_locked_omo_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict[str, Any] = {}

    class FakeLock:
        def __init__(self, path: Path) -> None:
            calls["lock_path"] = path

    class FakeLog:
        def __init__(self, path: Path, *, lock: FakeLock) -> None:
            calls["log_path"] = path
            calls["lock"] = lock

        def append(self, record: dict[str, Any], **kwargs: Any) -> None:
            calls["record"] = record
            calls["kwargs"] = kwargs

    monkeypatch.setattr(
        governed_io,
        "_omo_primitives",
        lambda _root: (object, FakeLog, FakeLock),
    )
    target = tmp_path / ".omo" / "state" / "events.jsonl"

    governed_io.append_jsonl(target, {"event": "probe"})

    assert calls["log_path"] == target
    assert calls["lock_path"] == target.with_suffix(".jsonl.lock")
    assert calls["record"] == {"event": "probe"}
    assert calls["kwargs"] == {"default": str}


def test_rejects_ungoverned_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must be under"):
        governed_io.write_text(tmp_path / "runtime" / "probe.txt", "nope")
