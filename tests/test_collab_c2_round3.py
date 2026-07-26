"""C 波 C2 — 协作管线执行 D2 真实任务测试 (Round 3, 吃狗粮).

验证 D2 卡评估通过协作管线 (3角色 orchestrator→implementer→verifier) 执行,
非单 agent 直做. workorder C2: ≥8 任务协作完成.
"""
from __future__ import annotations

import sys
from pathlib import Path

_DELIVERY = Path(__file__).resolve().parent.parent / "bin" / "delivery"
sys.path.insert(0, str(_DELIVERY))

from collab_round3_d2 import (  # noqa: E402
    run_d2_triage_via_collab,
    run_d2_batch_via_collab,
)


def test_single_card_collab_triage():
    """单卡协作评估: 3角色轨迹 assign→claim→handoff→verify→complete."""
    r = run_d2_triage_via_collab("needs-human-p81-m1-acceptance", "close")
    assert r["completed"] is True
    assert r["verdict"]["verified"] is True
    assert "assign" in r["trail"]
    assert "handoff" in r["trail"]
    assert "verify_result" in r["trail"]
    assert "complete" in r["trail"]


def test_batch_d2_collab_ge8_tasks():
    """D2 全部卡协作评估: ≥8 任务协作完成 (workorder C2)."""
    batch = run_d2_batch_via_collab()
    assert batch["n_tasks"] >= 8
    assert batch["all_completed"] is True
    assert "collab-pipeline" in batch["mode"]


def test_collab_trail_distinct_from_single_agent():
    """协作轨迹含 assign/claim/handoff/verify (单 agent 直做无这些)."""
    r = run_d2_triage_via_collab("needs-human-p80-physical-hosts", "keep")
    assert r["n_messages"] >= 5
