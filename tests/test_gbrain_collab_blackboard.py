"""C 波 C3 — gbrain 协作黑板复用+隔离测试 (Round 3, workorder).

验证 FileSharedContextStore (G-DEL.4, gbrain AgentSharedContextStore Python twin):
  复用 case ≥3: write/read 跨 agent / readers 限定可见 / list_visible 聚合
  隔离: scope 边界 (scope-a 不串 scope-b) + readers 隔离 + writer 永可见
"""
from __future__ import annotations

import sys
from pathlib import Path

_DELIVERY = Path(__file__).resolve().parent.parent / "bin" / "delivery"
sys.path.insert(0, str(_DELIVERY))

from shared_context_store import FileSharedContextStore  # noqa: E402


def test_reuse1_cross_agent_write_read(tmp_path):
    """复用1: agent-A write → agent-B read (空 readers, scope 内全可见)."""
    store = FileSharedContextStore(root=tmp_path)
    store.write("agent-A", "collab.handoff", "ready", scope="bet-x")
    rec = store.read("agent-B", "collab.handoff", scope="bet-x")
    assert rec is not None
    assert rec.value == "ready"
    assert rec.writer == "agent-A"


def test_reuse2_readers_scoped_visibility(tmp_path):
    """复用2: readers 限定 → 只 listed reader 可见, 其他不可见."""
    store = FileSharedContextStore(root=tmp_path)
    store.write("agent-A", "secret", "data", scope="s", readers=["agent-B"])
    assert store.read("agent-B", "secret", scope="s") is not None
    assert store.read("agent-C", "secret", scope="s") is None


def test_reuse3_list_visible_aggregation(tmp_path):
    """复用3: list_visible 聚合多记录 (跨 key 复用)."""
    store = FileSharedContextStore(root=tmp_path)
    store.write("agent-A", "k1", "v1", scope="s")
    store.write("agent-A", "k2", "v2", scope="s")
    visible = store.list_visible("agent-B", scope="s")
    assert len(visible) == 2


def test_isolation_scope_boundary(tmp_path):
    """隔离1: scope-a 的 key 不在 scope-b (黑板边界)."""
    store = FileSharedContextStore(root=tmp_path)
    store.write("agent-A", "k", "in-a", scope="scope-a")
    assert store.read("agent-B", "k", scope="scope-b") is None
    assert store.read("agent-B", "k", scope="scope-a") is not None


def test_isolation_writer_always_visible(tmp_path):
    """隔离2: writer 永远可见自己的写 (即使 readers 不含自己)."""
    store = FileSharedContextStore(root=tmp_path)
    store.write("agent-A", "k", "v", scope="s", readers=["agent-B"])
    assert store.read("agent-A", "k", scope="s") is not None
