"""cockpit memory CLI unit tests (inject invoke)."""

from __future__ import annotations

import argparse

from cockpit.commands import memory as mem_cmd


def test_cmd_memory_status_uses_invoke(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake(cmd: str, kwargs=None, args_list=None):
        calls.append((cmd, dict(kwargs or {})))
        return {"ok": True, "version": "0.7.0", "neo4j_configured": True}

    monkeypatch.setattr(mem_cmd, "_invoke_mos", fake)
    rc = mem_cmd.cmd_memory_status(argparse.Namespace(json=True, role=None, agent_profile=None))
    assert rc == 0
    assert calls[0][0] == "status"


def test_cmd_memory_recall_builds_scope(monkeypatch):
    calls: list[tuple[str, dict]] = []

    def fake(cmd: str, kwargs=None, args_list=None):
        calls.append((cmd, dict(kwargs or {})))
        return {"ok": True, "hits": [], "count": 0, "empty": True}

    monkeypatch.setattr(mem_cmd, "_invoke_mos", fake)
    rc = mem_cmd.cmd_memory_recall(
        argparse.Namespace(
            query="x",
            intent="temporal_fact",
            limit=5,
            as_of=None,
            principal_id="u1",
            agent_profile="claude",
            scene_id="s1",
            role=None,
            json=True,
        )
    )
    assert rc == 0
    assert calls[0][0] == "recall"
    assert calls[0][1]["scope"]["principal_id"] == "u1"
    assert calls[0][1]["intent"] == "temporal_fact"


def test_cmd_memory_write_requires_type(monkeypatch):
    monkeypatch.setattr(mem_cmd, "_invoke_mos", lambda *a, **k: {"ok": True})
    rc = mem_cmd.cmd_memory_write(
        argparse.Namespace(
            mem_type=None,
            type=None,
            content="x",
            content_ref=None,
            confidence=0.8,
            json=True,
        )
    )
    assert rc == 2


def test_cmd_memory_overview(monkeypatch):
    monkeypatch.setattr(
        mem_cmd,
        "_invoke_mos",
        lambda *a, **k: {"ok": True, "version": "0.7.0", "neo4j_configured": False, "neo4j_available": False, "rbac_enforced": True},
    )
    rc = mem_cmd.cmd_memory(argparse.Namespace(memory_command=None))
    assert rc == 0
