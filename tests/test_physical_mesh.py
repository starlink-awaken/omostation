"""Physical multi-host mesh — real TCP nodes on localhost (count as 1 machine)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "bin" / "delivery"


def _load(name: str):
    path = DELIVERY / f"{name}.py"
    mod_name = f"delivery_{name}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.path.insert(0, str(DELIVERY))
    sys.modules[mod_name] = mod
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_count_physical_machines_collapses_localhost():
    mp = _load("measure_physical")
    pc = _load("physical_client")
    eps = [
        pc.Endpoint("a", "127.0.0.1", 18765),
        pc.Endpoint("b", "localhost", 18766),
    ]
    assert mp.count_physical_machines(eps) == 1


def test_count_physical_machines_two_real_hosts():
    mp = _load("measure_physical")
    pc = _load("physical_client")
    eps = [
        pc.Endpoint("local-mac", "127.0.0.1", 18765),
        pc.Endpoint("macmini", "192.168.31.210", 18765),
    ]
    assert mp.count_physical_machines(eps) == 2


def test_two_local_nodes_protocol_and_no_physical_pass():
    """Two local TCP nodes work, but physical_hosts=1 so official gate stays false."""
    pc = _load("physical_client")
    mp = _load("measure_physical")

    port_a, port_b = 19765, 19766
    script = DELIVERY / "physical_node.py"
    procs = []
    try:
        for nid, port in (("n-a", port_a), ("n-b", port_b)):
            procs.append(
                subprocess.Popen(
                    [
                        sys.executable,
                        str(script),
                        "--bind",
                        "127.0.0.1",
                        "--port",
                        str(port),
                        "--node-id",
                        nid,
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            )
        eps = [
            pc.Endpoint("n-a", "127.0.0.1", port_a),
            pc.Endpoint("n-b", "127.0.0.1", port_b),
        ]
        # wait
        for ep in eps:
            deadline = time.time() + 5
            ok = False
            while time.time() < deadline:
                try:
                    if pc.rpc(ep, {"op": "hello"}, timeout=1).get("ok"):
                        ok = True
                        break
                except OSError:
                    time.sleep(0.1)
            assert ok, f"node {ep.node_id} not up"

        hosts = mp.count_physical_machines(eps)
        assert hosts == 1
        g1 = mp.measure_schedule(eps, n_tasks=40, physical_hosts=hosts)
        assert g1["meets_sim_harness"] is True
        assert g1["success_rate"] > 0.99
        # official physical gate requires ≥2 machines
        assert g1["meets_physical_gate"] is False
        assert g1["meets_gate"] is False

        g3 = mp.measure_sync(eps, n_ops=20, physical_hosts=hosts)
        assert g3["meets_physical_gate"] is False
    finally:
        for p in procs:
            p.terminate()
            try:
                p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                p.kill()


def test_stamp_physical_two_hosts_pass_g_del_3_not_g_del_1():
    """G-DEL.3 min=2 can pass; G-DEL.1 min=4 stays BLOCKED (ADR-0226)."""
    cal = _load("caliber")
    g3 = cal.stamp_physical_goal(
        {
            "gate": "G-DEL.3",
            "env": "physical multi-host TCP",
            "env_class": "physical_multi_host",
        },
        sim_ok=True,
        physical_hosts=2,
    )
    assert g3["meets_physical_gate"] is True
    assert g3["gate_status"] == "OPEN"

    g1 = cal.stamp_physical_goal(
        {
            "gate": "G-DEL.1",
            "env": "physical multi-host TCP",
            "env_class": "physical_multi_host",
            "success_rate": 1.0,
        },
        sim_ok=True,
        physical_hosts=2,
    )
    assert g1["meets_physical_gate"] is False
    assert g1["gate_status"] == "BLOCKED"
    assert "min_physical_hosts=4" in g1["blocked_reason"]

    g1_ok = cal.stamp_physical_goal(
        {"gate": "G-DEL.1", "env_class": "physical_multi_host"},
        sim_ok=True,
        physical_hosts=4,
    )
    assert g1_ok["meets_physical_gate"] is True
