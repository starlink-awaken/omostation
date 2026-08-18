#!/usr/bin/env python3
"""agent-clone-onboard.py 集成测试."""

from __future__ import annotations

import importlib
import json
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
    (runs_dir / "test1.yaml").write_text(f"""\
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
    assert "test-agent" in agents
    assert "closed-agent" not in agents


def test_clone_exists_false(tmp_path, monkeypatch):
    """无 identity 文件时返回 False."""
    monkeypatch.setattr(ob, "AGENTS_DIR", tmp_path)
    assert ob.clone_exists("nonexistent") is False


def test_clone_exists_true(tmp_path, monkeypatch):
    """有 identity 文件时返回 True."""
    monkeypatch.setattr(ob, "AGENTS_DIR", tmp_path)
    identity_dir = tmp_path / "myagent" / "ws" / ".git"
    identity_dir.mkdir(parents=True)
    (identity_dir / "agent-clone-identity.json").write_text('{"agent_id": "myagent"}')
    assert ob.clone_exists("myagent") is True


def test_onboard_dry_run(tmp_path, monkeypatch):
    """dry-run 不实际创建."""
    monkeypatch.setattr(ob, "AGENTS_DIR", tmp_path)
    result = ob.onboard_agent("test-agent", dry_run=True)
    assert result["status"] == "would_create"
    assert not (tmp_path / "test-agent" / "ws").exists()


def test_extract_agent_from_runid():
    """从 run_id 提取 agent/workflow 标识."""
    result = ob.extract_agent_from_runid("20260803T135152Z-test-workflow-abc12345")
    assert result == "test"  # parts[1]


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
