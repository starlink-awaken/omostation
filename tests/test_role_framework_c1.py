"""STRAT-P81 Batch3 C1 — Role expansion (research/delivery) tests.

Verifies ADR-0235: 5 roles (3 first-ship + 2 second-wave) instantiate,
isolate, and enforce capability/message boundaries (eval 页 design).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_DELIVERY = Path(__file__).resolve().parent.parent / "bin" / "delivery"
if str(_DELIVERY) not in sys.path:
    sys.path.insert(0, str(_DELIVERY))

from role_framework import (  # noqa: E402
    ALL_ROLES,
    FIRST_SHIP_ROLES,
    LEGACY_ROLE_MAP,
    ROLE_CATALOG,
    ROLE_DELIVERY,
    ROLE_RESEARCH,
    SECOND_WAVE_ROLES,
    RoleMessage,
    RoleProtocolBus,
    RoleRegistry,
)


def test_five_roles_in_catalog():
    assert len(ALL_ROLES) == 5
    assert set(ALL_ROLES) == {
        "engineering",
        "governance",
        "audit",
        "research",
        "delivery",
    }
    assert SECOND_WAVE_ROLES == (ROLE_RESEARCH, ROLE_DELIVERY)
    assert set(FIRST_SHIP_ROLES).isdisjoint(SECOND_WAVE_ROLES)


def test_legacy_map_complete():
    for r in ALL_ROLES:
        assert r in LEGACY_ROLE_MAP


def test_all_roles_instantiate():
    reg = RoleRegistry()
    for r in ALL_ROLES:
        inst = reg.register(r)
        assert inst.role_id == r
        assert inst.spec is ROLE_CATALOG[r]


def test_research_delivery_no_code_write():
    # eval 页边界: research 只读知识面, delivery 只写投影, 都不可 claim 代码
    for forbidden in ("write-code", "claim-path"):
        assert forbidden not in ROLE_CATALOG[ROLE_RESEARCH].capabilities
        assert forbidden not in ROLE_CATALOG[ROLE_DELIVERY].capabilities


def test_governance_dispatch_research():
    reg = RoleRegistry()
    reg.register("governance", agent_id="gov")
    res = reg.register("research", agent_id="res")
    bus = RoleProtocolBus(reg)
    bus.publish(
        RoleMessage(
            id="1",
            type="research_request",
            from_agent="gov",
            from_role="governance",
            to_role="research",
            task_ref="t1",
        )
    )
    bus.publish(
        RoleMessage(
            id="2",
            type="research_result",
            from_agent="res",
            from_role="research",
            to_role="governance",
            task_ref="t1",
        )
    )
    assert len(bus.history) == 2


def test_governance_dispatch_delivery():
    reg = RoleRegistry()
    reg.register("governance", agent_id="gov")
    dly = reg.register("delivery", agent_id="dly")
    bus = RoleProtocolBus(reg)
    bus.publish(
        RoleMessage(
            id="1",
            type="delivery_request",
            from_agent="gov",
            from_role="governance",
            to_role="delivery",
            task_ref="t2",
        )
    )
    bus.publish(
        RoleMessage(
            id="2",
            type="delivery_registered",
            from_agent="dly",
            from_role="delivery",
            to_role="governance",
            task_ref="t2",
        )
    )
    assert len(bus.history) == 2


def test_research_cannot_send_assign():
    # 负向: research 无 assign 能力, 边界 enforce
    reg = RoleRegistry()
    reg.register("research", agent_id="res")
    reg.register("governance", agent_id="gov")
    bus = RoleProtocolBus(reg)
    with pytest.raises(PermissionError):
        bus.publish(
            RoleMessage(
                id="1",
                type="assign",
                from_agent="res",
                from_role="research",
                to_role="governance",
                task_ref="t3",
            )
        )


def test_existing_three_role_handshake_unbroken():
    # C1 扩展不能破坏现有 3 角色协议 (回归保护)
    from role_framework import run_three_role_handshake

    r = run_three_role_handshake()
    assert r["completed"] is True
    assert r["roles"] == ["engineering", "governance", "audit"]


def test_five_role_handshake_completes():
    # C1 深化 (P1, ADR-0235): 5 角色 dispatch 流全链路完成 (边界 enforce)
    from role_framework import run_five_role_handshake

    r = run_five_role_handshake()
    assert r["completed"] is True
    assert len(r["roles"]) == 5
    assert r["roles"] == ["governance", "research", "delivery", "engineering", "audit"]
    # 9 步完整流: research→delivery→assign→claim→handoff→verify→complete
    assert "research_result" in r["steps"]
    assert "delivery_registered" in r["steps"]
    assert "complete" in r["steps"]


def test_five_role_batch_meets_gate():
    # C1 深化: 5 角色 batch ≥15 任务 completion >95% (G-DEL.2b 5-role process-local 口径)
    from role_framework import measure_five_role_batch

    m = measure_five_role_batch(n_tasks=15)
    assert m["completion_rate"] == 1.0
    assert m["meets_gate"] is True
    assert m["meets_physical_gate"] is False  # process-local, 非物理达标
    assert m["gate"] == "G-DEL.2b-5role"
