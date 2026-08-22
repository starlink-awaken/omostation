#!/usr/bin/env python3
"""agent-clone-onboard.py 集成测试."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

_BIN_GAC = Path(__file__).resolve().parent
sys.path.insert(0, str(_BIN_GAC))
sys.path.insert(0, str(_BIN_GAC.parents[1]))

ob = importlib.import_module("agent-clone-onboard")


def test_detect_active_agents(tmp_path, monkeypatch):
    """从 workflow runs 检测活跃 agent."""
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    # 活跃 run
    (runs_dir / "test1.yaml").write_text("""\
run_id: 20260803T135152Z-test-workflow-abc12345
status: active
actor: test-agent
objective: test
context:
  actor: test-agent
""")
    # 已关闭 run (应忽略)
    (runs_dir / "test2.yaml").write_text("""\
run_id: 20260803T135152Z-other-def67890
status: closed
actor: closed-agent
""")
    monkeypatch.setattr(ob, "RUNS_DIR", runs_dir)
    agents = ob.detect_active_agents()
    detected = list(agents.values())
    assert [item["agent_id"] for item in detected] == ["test-agent"]
    assert detected[0]["delivery_attempt_id"].startswith("run-")


def test_detect_active_agents_keeps_parallel_attempts_for_one_actor(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    for run_id, attempt_id in (
        ("run-parallel-a", "attempt-001"),
        ("run-parallel-b", "attempt-002"),
    ):
        (runs_dir / f"{attempt_id}.yaml").write_text(
            "\n".join(
                (
                    f"run_id: {run_id}",
                    "status: active",
                    "context:",
                    "  actor: shared-actor",
                    f"  delivery_attempt_id: {attempt_id}",
                )
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(ob, "RUNS_DIR", runs_dir)
    agents = ob.detect_active_agents()

    assert set(agents) == {
        "shared-actor:attempt-001",
        "shared-actor:attempt-002",
    }
    assert {item["agent_id"] for item in agents.values()} == {"shared-actor"}


def test_clone_exists_false(tmp_path, monkeypatch):
    """无 identity 文件时返回 False."""
    monkeypatch.setattr(ob, "AGENTS_DIR", tmp_path)
    assert ob.clone_exists("nonexistent", "attempt-001") is False


def test_clone_exists_true(tmp_path, monkeypatch):
    """有 identity 文件时返回 True."""
    monkeypatch.setattr(ob, "AGENTS_DIR", tmp_path)
    identity_dir = tmp_path / "myagent" / "attempts" / "attempt-001" / "ws" / ".git"
    identity_dir.mkdir(parents=True)
    (identity_dir / "agent-clone-identity.json").write_text(
        json.dumps(
            {
                "schema": "agent-clone-identity/v2",
                "agent_id": "myagent",
                "actor_id": "myagent",
                "delivery_attempt_id": "attempt-001",
                "working_branch": "agent/myagent--attempt-001",
            }
        )
    )
    assert ob.clone_exists("myagent", "attempt-001") is True
    assert ob.clone_exists("myagent", "attempt-002") is False


def test_onboard_dry_run(tmp_path, monkeypatch):
    """dry-run 不实际创建."""
    monkeypatch.setattr(ob, "AGENTS_DIR", tmp_path)
    result = ob.onboard_agent(
        "test-agent",
        delivery_attempt_id="attempt-001",
        dry_run=True,
    )
    assert result["status"] == "would_create"
    assert result["delivery_attempt_id"] == "attempt-001"
    assert not (tmp_path / "test-agent" / "attempts" / "attempt-001" / "ws").exists()


def test_onboard_apply_routes_once_through_governance_lifecycle(tmp_path, monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess:
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    monkeypatch.setattr(ob, "AGENTS_DIR", tmp_path)
    monkeypatch.setattr(ob, "run", fake_run)
    result = ob.onboard_agent(
        "test-agent",
        delivery_attempt_id="attempt-001",
        dry_run=False,
        profile="governance",
    )

    assert result["status"] == "created"
    assert len(calls) == 1
    assert calls[0][1:4] == [str(ob.LIFECYCLE), "onboard", "--agent-id"]
    assert calls[0][calls[0].index("--delivery-attempt-id") + 1] == "attempt-001"
    assert calls[0][calls[0].index("--destination") + 1].endswith(
        "test-agent/attempts/attempt-001/ws"
    )
    assert calls[0][-2:] == ["--profile", "governance"]


def test_extract_agent_from_runid():
    """从 run_id 提取 agent/workflow 标识."""
    result = ob.extract_agent_from_runid("20260803T135152Z-test-workflow-abc12345")
    assert result == "test"  # parts[1]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
