"""Tests for BET-Y1Q2-T6-08: attribution chain (parent_run_id, spawn, trace)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import omo.workflow.core as core_mod
import omo.workflow.lifecycle as lifecycle_mod
from omo.workflow.lifecycle import (
    spawn_run,
    start_run,
    trace_attribution,
)


@pytest.fixture()
def registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    monkeypatch.setattr(core_mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(lifecycle_mod, "WORKSPACE", tmp_path)
    profiles = {
        "test-agent": {
            "id": "test-agent",
            "actor": "tester",
            "allowed_workflows": ["*"],
        },
        "coordinator": {
            "id": "coordinator",
            "actor": "human",
            "allowed_workflows": ["*"],
        },
        "planner": {"id": "planner", "actor": "agent-a", "allowed_workflows": ["*"]},
        "executor": {"id": "executor", "actor": "agent-b", "allowed_workflows": ["*"]},
        "orchestrator": {
            "id": "orchestrator",
            "actor": "alice",
            "allowed_workflows": ["*"],
        },
        "worker": {"id": "worker", "actor": "bob", "allowed_workflows": ["*"]},
    }
    return {
        "runner": {
            "run_state_dir": "runs",
            "ledger_path": "ledger/events.jsonl",
        },
        "workflows": [
            {
                "id": "test-workflow",
                "title": "Test",
                "purpose": "test",
                "agents": {"test-agent": {"actor": "tester"}},
                "allowed_lanes": [],
                "lock_scopes": [],
                "phases": {},
            }
        ],
        "agent_profiles": profiles,
    }


def _workflow(registry: dict) -> dict:
    return registry["workflows"][0]


def _context(actor: str = "tester", profile: str = "test-agent") -> dict[str, str]:
    return {
        "actor": actor,
        "profile": profile,
        "project": "",
        "format": "openspec",
        "source_file": "",
        "run_id": "",
    }


def _ledger_events(registry: dict) -> list[dict]:
    path = lifecycle_mod.WORKSPACE / registry["runner"]["ledger_path"]
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_start_run_without_parent(registry: dict) -> None:
    record = start_run(
        registry, _workflow(registry), _context(), "test objective", True, False
    )
    assert "parent_run_id" not in record
    assert "parent_agent" not in record


def test_start_run_with_parent(registry: dict) -> None:
    record = start_run(
        registry,
        _workflow(registry),
        _context(),
        "child objective",
        True,
        False,
        parent_run_id="parent-run-123",
        parent_agent="parent-agent-profile",
    )
    assert record["parent_run_id"] == "parent-run-123"
    assert record["parent_agent"] == "parent-agent-profile"


def test_start_run_ledger_includes_parent(registry: dict) -> None:
    start_run(
        registry,
        _workflow(registry),
        _context(),
        "child",
        False,
        False,
        parent_run_id="parent-abc",
        parent_agent="mom-profile",
    )
    events = _ledger_events(registry)
    assert len(events) == 1
    assert events[0]["parent_run_id"] == "parent-abc"
    assert events[0]["parent_agent"] == "mom-profile"


def test_start_run_ledger_no_parent_fields_when_absent(registry: dict) -> None:
    start_run(registry, _workflow(registry), _context(), "root", False, False)
    events = _ledger_events(registry)
    assert len(events) == 1
    assert "parent_run_id" not in events[0]
    assert "parent_agent" not in events[0]


def test_spawn_run_links_parent(registry: dict) -> None:
    parent = start_run(
        registry,
        _workflow(registry),
        _context("alice", "test-agent"),
        "parent work",
        False,
        False,
    )
    child = spawn_run(
        registry,
        parent["run_id"],
        _workflow(registry),
        _context("bob", "test-agent"),
        "child work",
    )
    assert child["parent_run_id"] == parent["run_id"]
    assert child["parent_agent"] == "test-agent"


def test_trace_attribution_single_run(registry: dict) -> None:
    root = start_run(
        registry,
        _workflow(registry),
        _context("alice", "test-agent"),
        "root work",
        False,
        False,
    )
    chain = trace_attribution(registry, root["run_id"])
    assert len(chain) == 1
    assert chain[0]["run_id"] == root["run_id"]
    assert chain[0]["actor"] == "alice"


def test_trace_attribution_chain(registry: dict) -> None:
    root = start_run(
        registry,
        _workflow(registry),
        _context("alice", "orchestrator"),
        "root",
        False,
        False,
    )
    child = spawn_run(
        registry,
        root["run_id"],
        _workflow(registry),
        _context("bob", "worker"),
        "child task",
    )
    chain = trace_attribution(registry, child["run_id"])
    assert len(chain) == 2
    assert chain[0]["run_id"] == root["run_id"]
    assert chain[0]["actor"] == "alice"
    assert chain[0]["agent_profile"] == "orchestrator"
    assert chain[1]["run_id"] == child["run_id"]
    assert chain[1]["actor"] == "bob"


def test_trace_attribution_missing_run(registry: dict) -> None:
    chain = trace_attribution(registry, "nonexistent-run-id")
    assert len(chain) == 1
    assert chain[0]["status"] == "missing"


def test_trace_attribution_three_levels(registry: dict) -> None:
    root = start_run(
        registry,
        _workflow(registry),
        _context("human", "coordinator"),
        "intent",
        False,
        False,
    )
    mid = spawn_run(
        registry,
        root["run_id"],
        _workflow(registry),
        _context("agent-a", "planner"),
        "plan",
        False,
        False,
    )
    leaf = spawn_run(
        registry,
        mid["run_id"],
        _workflow(registry),
        _context("agent-b", "executor"),
        "execute",
        False,
        False,
    )
    chain = trace_attribution(registry, leaf["run_id"])
    assert len(chain) == 3
    assert chain[0]["actor"] == "human"
    assert chain[1]["actor"] == "agent-a"
    assert chain[2]["actor"] == "agent-b"
