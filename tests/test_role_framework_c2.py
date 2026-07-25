"""STRAT-P81 Batch3 C2 — Collaboration protocol deepening tests.

Verifies ADR-0236: multi-round negotiation + conflict resolution +
task decomposition (role_framework C2 extension).
"""
from __future__ import annotations

import sys
from pathlib import Path

_DELIVERY = Path(__file__).resolve().parent.parent / "bin" / "delivery"
if str(_DELIVERY) not in sys.path:
    sys.path.insert(0, str(_DELIVERY))

from role_framework import (  # noqa: E402
    RoleMessage,
    decompose_into_subtasks,
    resolve_message_conflict,
    run_multi_round_negotiation,
)


def test_multi_round_negotiation_satisfied():
    r = run_multi_round_negotiation(max_rounds=3, satisfy_after=2)
    assert r["satisfied"] is True
    assert r["rounds_executed"] == 2
    assert len(r["negotiation_log"]) == 2
    assert r["roles"] == ["governance", "research"]


def test_multi_round_negotiation_exhausted():
    # satisfy_after > max_rounds → 轮次耗尽, 未满意
    r = run_multi_round_negotiation(max_rounds=3, satisfy_after=5)
    assert r["satisfied"] is False
    assert r["rounds_executed"] == 3


def test_conflict_resolution_precedence():
    # audit (证据) 优先于 research (调研)
    msgs = [
        RoleMessage(
            id="1",
            type="research_result",
            from_agent="r",
            from_role="research",
            to_role="governance",
            task_ref="t",
        ),
        RoleMessage(
            id="2",
            type="verify_result",
            from_agent="a",
            from_role="audit",
            to_role="governance",
            task_ref="t",
        ),
    ]
    winner = resolve_message_conflict(msgs)
    assert winner is not None
    assert winner.from_role == "audit"


def test_conflict_resolution_governance_highest():
    # governance 仲裁优先级最高
    msgs = [
        RoleMessage(
            id="1",
            type="progress",
            from_agent="e",
            from_role="engineering",
            to_role="governance",
            task_ref="t",
        ),
        RoleMessage(
            id="2",
            type="progress",
            from_agent="g",
            from_role="governance",
            to_role=None,
            task_ref="t",
        ),
    ]
    winner = resolve_message_conflict(msgs)
    assert winner.from_role == "governance"


def test_conflict_resolution_empty():
    assert resolve_message_conflict([]) is None


def test_task_decomposition():
    d = decompose_into_subtasks("big-task", ["sub1", "sub2", "sub3"])
    assert d["total"] == 3
    assert d["completed"] == 3
    assert d["aggregate_rate"] == 1.0
    assert len(d["subtasks"]) == 3
    assert all(s["completed"] for s in d["subtasks"])


def test_task_decomposition_empty():
    d = decompose_into_subtasks("empty-task", [])
    assert d["total"] == 0
    assert d["aggregate_rate"] == 0.0
