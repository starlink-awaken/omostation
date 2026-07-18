"""Drive real G-DEL.1/2b/3/5b measurement harnesses — no hard-coded pass."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "bin" / "delivery"


def _load(name: str):
    path = DELIVERY / f"{name}.py"
    # unique module name avoids collision; register before exec for dataclasses
    mod_name = f"delivery_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.path.insert(0, str(DELIVERY))
    sys.modules[mod_name] = mod
    # sibling imports use bare module names
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_g_del_1_schedule_success_rate_above_99():
    sched = _load("scheduler")
    m = sched.measure_schedule_success_rate(n_nodes=4, agents_per_node=3, n_tasks=500)
    assert m["n_tasks"] == 500
    assert m["successes"] + m["failures"] == 500
    assert m["success_rate"] > 0.99
    assert m["meets_gate"] is True


def test_g_del_1_registry_assign_across_nodes():
    reg_mod = _load("agent_registry")
    sched_mod = _load("scheduler")
    reg = reg_mod.AgentRegistry()
    reg.register_node("n1")
    reg.register_node("n2")
    reg.register_agent(node_id="n1", role_id="implementer", agent_id="a1")
    reg.register_agent(node_id="n2", role_id="implementer", agent_id="a2")
    s = sched_mod.TaskScheduler(reg)
    r = s.schedule_one(sched_mod.Task(task_id="t1", role_id="implementer"))
    assert r.success is True
    assert r.agent_id in {"a1", "a2"}
    assert r.node_id in {"n1", "n2"}


def test_g_del_2b_collab_completion_rate_above_95():
    collab = _load("role_collab")
    m = collab.measure_collab_completion_rate(n_runs=100)
    assert m["completion_rate"] > 0.95
    assert m["meets_gate"] is True
    r = collab.run_collab_handshake()
    assert r.completed is True
    assert "complete" in r.steps


def test_g_del_3_sync_p99_under_100ms():
    sync = _load("state_sync")
    m = sync.measure_sync_latency(n_nodes=4, n_ops=200)
    assert m["p99_ms"] < 100.0
    assert m["meets_gate"] is True
    cluster = sync.StateSyncCluster(["a", "b"])
    cluster.put("a", "k", 42)
    assert cluster.get("b", "k") == 42


def test_g_del_5b_accuracy_and_kill_switch():
    em = _load("emergence")
    m = em.measure_emergence_accuracy()
    assert m["accuracy"] > 0.80
    assert m["kill_switch_blocks_detect"] is True
    assert m["kill_switch_blocks_write"] is True
    assert m["meets_gate"] is True
    # drive real detector
    det = em.EmergenceDetector(em.KillSwitch(enabled=True))
    assert det.detect("swarm consensus multi-agent vote") is True
    det.kill.kill()
    assert det.detect("swarm consensus multi-agent vote") is False
