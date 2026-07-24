"""Batch1 B1/B3/C1/C3 — drive real role_framework, registry, failover, memory."""
from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "bin" / "delivery"


def _load(name: str):
    path = DELIVERY / f"{name}.py"
    mod_name = f"batch1_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str(DELIVERY))
    sys.modules[mod_name] = mod
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_three_roles_register_load_switch():
    rf = _load("role_framework")
    reg = rf.RoleRegistry()
    e = reg.register(rf.ROLE_ENGINEERING, agent_id="e1")
    g = reg.register(rf.ROLE_GOVERNANCE, agent_id="g1")
    a = reg.register(rf.ROLE_AUDIT, agent_id="a1")
    assert {e.role_id, g.role_id, a.role_id} == set(rf.FIRST_SHIP_ROLES)
    assert reg.load("e1").role_id == rf.ROLE_ENGINEERING
    switched = reg.switch("e1", rf.ROLE_AUDIT)
    assert switched.role_id == rf.ROLE_AUDIT
    assert reg.load("e1").role_id == rf.ROLE_AUDIT


def test_protocol_message_replay_and_boundaries():
    rf = _load("role_framework")
    result = rf.run_three_role_handshake()
    assert result["completed"] is True
    assert "complete" in result["steps"]
    replay = result["replay"]
    assert len(replay) >= 4
    types = [m["type"] for m in replay]
    assert "assign" in types
    assert "handoff" in types
    # engineering cannot send assign
    bus = rf.RoleProtocolBus()
    bus.registry.register(rf.ROLE_ENGINEERING, agent_id="e1")
    try:
        bus.publish(
            rf.RoleMessage(
                id="1",
                type="assign",
                from_agent="e1",
                from_role=rf.ROLE_ENGINEERING,
                to_role=rf.ROLE_AUDIT,
                task_ref="t",
            )
        )
        raised = False
    except PermissionError:
        raised = True
    assert raised is True


def test_role_memory_share_and_isolate():
    mem = _load("role_memory")
    store = mem.RoleMemoryStore()
    store.write("engineering", "shared.plan", "plan-v1", readers=None)
    store.write(
        "engineering",
        "secret.notes",
        "private-eng",
        readers=["engineering"],
    )
    # shared: audit can read
    assert store.read("audit", "shared.plan") == "plan-v1"
    # private: audit cannot read engineering private
    assert store.read("audit", "secret.notes") is None
    # writer can read own private
    assert store.read("engineering", "secret.notes") == "private-eng"
    # governance private blocked from engineering
    store.write(
        "governance",
        "gov.only",
        "g-secret",
        readers=["governance"],
    )
    assert store.read("engineering", "gov.only") is None
    assert store.read("governance", "gov.only") == "g-secret"


def test_registry_four_nodes_heartbeat_false_death():
    reg_mod = _load("agent_registry")
    reg = reg_mod.AgentRegistry()
    for i in range(4):
        reg.register_node(f"n{i}")
        reg.register_agent(node_id=f"n{i}", role_id="implementer", agent_id=f"a{i}")
    assert len(reg.snapshot()["nodes"]) == 4
    reg.heartbeat("a0", healthy=True)
    # force stale heartbeat on a1
    rec = reg._require("a1")
    rec.last_heartbeat = time.time() - 120
    dead = reg.detect_false_death(stale_after_s=30)
    assert "a1" in dead
    assert reg._require("a1").healthy is False
    # healthy still schedulable
    alive = reg.list_agents(healthy_only=True)
    assert all(a.agent_id != "a1" for a in alive)
    assert len(alive) >= 3


def test_failover_drill_dry_run():
    drill = _load("failover_drill")
    report = drill.run_drill(dry_run=True, n_nodes=4)
    assert report["ok"] is True
    assert report["migrated_away_from_dead_node"] is True
    assert report["meets_sim_harness"] is True
    assert report["meets_physical_gate"] is False
    assert report["meets_gate"] is False
    assert all(t["node_id"] != "node-0" for t in report["tasks"] if t["success"])


def test_g_del_2b_batch_30_tasks():
    rf = _load("role_framework")
    m = rf.measure_three_role_batch(n_tasks=30)
    assert m["n_tasks"] == 30
    assert m["completion_rate"] > 0.95
    assert m["env_class"] in {
        "in-process_simulation",
        "process_local",
    } or "process" in str(m.get("env", "")).lower() or m.get("meets_sim_harness") is True or m.get(
        "meets_gate"
    ) is True
    # must not claim physical
    assert m.get("meets_physical_gate") is not True


def test_run_backlog_collab_binds_real_task_path(tmp_path: Path):
    """B2: real backlog collab must use task_id as task_ref and verify path exists."""
    rf = _load("role_framework")
    card = tmp_path / "REMEDIATE-TEST-FIX.yaml"
    card.write_text(
        "id: REMEDIATE-TEST-FIX\ntitle: test fix\nstatus: open\n",
        encoding="utf-8",
    )
    r = rf.run_backlog_collab(
        task_id="REMEDIATE-TEST-FIX",
        task_path=str(card),
        title="test fix",
        work_summary="review remediation card",
    )
    assert r["completed"] is True
    assert r["task_ref"] == "REMEDIATE-TEST-FIX"
    assert r["task_path"] == str(card)
    assert r["handoff_evidence"]["task_path"] == str(card)
    assert any(
        m.get("payload", {}).get("evidence", {}).get("task_id") == "REMEDIATE-TEST-FIX"
        or m.get("payload", {}).get("task_id") == "REMEDIATE-TEST-FIX"
        for m in r["replay"]
    )
