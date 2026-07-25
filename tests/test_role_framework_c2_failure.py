"""STRAT-P81 Round2 C波 — C1 协议升级端到端 + C2 失败路径测试.

验证协作能处理不完美 (非 100% 单向下发): 含真实冲突的复合任务端到端 + ≥5 失败场景
确定性处理. 补上轮 15/15=100% 全成功的盲区.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DELIVERY = Path(__file__).resolve().parent.parent / "bin" / "delivery"
if str(_DELIVERY) not in sys.path:
    sys.path.insert(0, str(_DELIVERY))

from role_framework import (  # noqa: E402
    run_collab_pipeline_with_conflict,
    run_failure_scenario_suite,
    simulate_failure_scenario,
)


def test_c1_pipeline_conflict_resolved():
    """C1: 端到端冲突复合任务, audit 消解胜出 (≥3角色/≥2轮/1次冲突)."""
    p = run_collab_pipeline_with_conflict()
    assert p["pipeline_ok"] is True
    assert len(p["roles_involved"]) >= 3  # ≥3 角色
    assert p["negotiation_rounds"] >= 2  # ≥2 轮协商
    assert "engineering" in p["conflict_parties"]  # 含真实冲突
    assert "audit" in p["conflict_parties"]
    assert p["resolved_winner"] == "audit"  # 冲突消解 audit 胜 (优先级 > engineering)


def test_c1_no_conflict_mode():
    """C1: inject_conflict=False → 无冲突, resolved_winner=None."""
    p = run_collab_pipeline_with_conflict(inject_conflict=False)
    assert p["conflict_injected"] is False
    assert p["resolved_winner"] is None


def test_c2_five_scenarios_all_deterministic():
    """C2: ≥5 失败场景全确定性处理, no_silent_loss."""
    s = run_failure_scenario_suite()
    assert s["scenarios_run"] >= 5
    assert s["all_deterministic_handled"] is True
    assert s["no_silent_loss"] is True


def test_c2_reject_deterministic():
    """C2 reject: 产物驳回 → handshake 不 complete (确定性, recoverable)."""
    r = simulate_failure_scenario("reject")
    assert r["deterministic_handled"] is True
    assert r["recoverable"] is True


def test_c2_exhaust_unsatisfied_not_silent():
    """C2 exhaust: 协商耗尽 → unsatisfied (不可恢复但写卡, 不静默丢)."""
    r = simulate_failure_scenario("exhaust")
    assert r["deterministic_handled"] is True
    assert r["recoverable"] is False  # 耗尽不可恢复
    assert r["no_silent_loss"] is True  # 但写卡, 不静默丢


def test_c2_escalate_governance_arbiter():
    """C2 escalate: 冲突升级 → governance 仲裁胜出."""
    r = simulate_failure_scenario("escalate")
    assert r["deterministic_handled"] is True
    assert r["detail"]["arbiter"] == "governance"


def test_c2_unknown_scenario_raises():
    """C2 未知场景 → ValueError (不静默吞)."""
    with pytest.raises(ValueError):
        simulate_failure_scenario("nonexistent")
