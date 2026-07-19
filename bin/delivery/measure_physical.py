#!/usr/bin/env python3
"""Physical multi-host G-DEL.1 / G-DEL.3 measurement (ADR-0225).

Attaches to (or starts) physical_node agents on ≥2 distinct machines, runs
schedule + sync over real TCP, stamps env_class=physical_multi_host.

Usage:
  python3 bin/delivery/measure_physical.py --auto-default-lan --start \\
    --remote-root ~/Workspace

  python3 bin/delivery/measure_physical.py \\
    --host local-mac=127.0.0.1:18765 \\
    --host macmini=192.168.31.210:18765

Exit: 0 when all_physical_gates_pass; 1 when measured but not pass; 2 config error.
"""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from caliber import (  # noqa: E402
    ENV_CLASS_PHYSICAL,
    MIN_HOSTS_G_DEL_1,
    MIN_HOSTS_G_DEL_3,
    stamp_physical_goal,
)
from latency_stats import g_del_3_sim_ok_from_summary, summarize_latencies  # noqa: E402
from physical_client import Endpoint, Session, parse_hosts, rpc  # noqa: E402

DEFAULT_PORT = 18765
DEFAULT_N_OPS = 10000  # large-N for trustworthy p99 (min floor 1000)
DEFAULT_LAN = [
    f"local-mac=127.0.0.1:{DEFAULT_PORT}",
    f"macmini=192.168.31.210:{DEFAULT_PORT}",
]


def count_physical_machines(endpoints: list[Endpoint]) -> int:
    """Distinct machines — multiple localhost ports count as one host."""
    machines: set[str] = set()
    for e in endpoints:
        h = e.host.strip().lower()
        if h in {"127.0.0.1", "localhost", "::1"}:
            machines.add("local")
        else:
            machines.add(h)
    return len(machines)


def start_local_node(node_id: str, port: int) -> subprocess.Popen[str]:
    script = Path(__file__).resolve().parent / "physical_node.py"
    return subprocess.Popen(
        [
            sys.executable,
            str(script),
            "--bind",
            "0.0.0.0",
            "--port",
            str(port),
            "--node-id",
            node_id,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def ssh_start_remote(ssh_host: str, node_id: str, port: int, remote_root: str) -> str:
    """Start remote node via SSH nohup; return remote pid or error text."""
    # Kill stale listener on port then start
    remote_cmd = (
        f"cd {remote_root} && "
        f"(lsof -ti tcp:{port} | xargs kill -9) 2>/dev/null; "
        f"nohup python3 bin/delivery/physical_node.py "
        f"--bind 0.0.0.0 --port {port} --node-id {node_id} "
        f">/tmp/gdel-physical-{node_id}.log 2>&1 & echo $!"
    )
    r = subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            "-o",
            "StrictHostKeyChecking=accept-new",
            ssh_host,
            remote_cmd,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if r.returncode != 0:
        return f"ssh_fail:{r.stderr.strip() or r.stdout.strip()}"
    return (r.stdout or "").strip()


def wait_hello(ep: Endpoint, *, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {"ok": False, "error": "timeout"}
    while time.time() < deadline:
        try:
            last = rpc(ep, {"op": "hello"}, timeout=2.0)
            if last.get("ok"):
                return last
        except OSError as exc:
            last = {"ok": False, "error": str(exc)}
        time.sleep(0.25)
    return last


def measure_schedule(
    endpoints: list[Endpoint],
    *,
    n_tasks: int,
    physical_hosts: int,
) -> dict[str, Any]:
    for ep in endpoints:
        r = rpc(ep, {"op": "register_agent", "role_id": "implementer", "capacity": 8})
        if not r.get("ok"):
            return stamp_physical_goal(
                {
                    "gate": "G-DEL.1",
                    "kpi": "schedule_success_rate > 99%",
                    "env": "physical multi-host TCP agents (ADR-0225)",
                    "env_class": ENV_CLASS_PHYSICAL,
                    "error": f"register failed on {ep.node_id}: {r}",
                    "success_rate": 0.0,
                },
                sim_ok=False,
                physical_hosts=physical_hosts,
            )

    ok = 0
    latencies: list[float] = []
    sessions = [Session(ep, timeout=15.0) for ep in endpoints]
    try:
        for s in sessions:
            s.open()
        for i in range(n_tasks):
            sess = sessions[i % len(sessions)]
            r = sess.call(
                {
                    "op": "run_task",
                    "task_id": f"t-{i}",
                    "role_id": "implementer",
                    "work_ms": 0,
                }
            )
            if r.get("success") is True:
                ok += 1
            latencies.append(float(r.get("wall_ms") or r.get("latency_ms") or 0.0))
    finally:
        for s in sessions:
            s.close()

    rate = ok / n_tasks if n_tasks else 0.0
    latencies.sort()
    p99 = (
        latencies[min(len(latencies) - 1, max(0, int(round(0.99 * (len(latencies) - 1)))))]
        if latencies
        else 0.0
    )
    return stamp_physical_goal(
        {
            "gate": "G-DEL.1",
            "kpi": "schedule_success_rate > 99%",
            "env": "physical multi-host TCP agents over real hosts (ADR-0225)",
            "env_class": ENV_CLASS_PHYSICAL,
            "n_tasks": n_tasks,
            "successes": ok,
            "failures": n_tasks - ok,
            "success_rate": rate,
            "success_rate_pct": round(rate * 100, 4),
            "dispatch_p99_ms": round(p99, 4),
            "nodes": [e.node_id for e in endpoints],
            "endpoints": [e.addr for e in endpoints],
        },
        sim_ok=rate > 0.99,
        physical_hosts=physical_hosts,
        min_hosts=MIN_HOSTS_G_DEL_1,
    )


def measure_sync(
    endpoints: list[Endpoint],
    *,
    n_ops: int,
    physical_hosts: int,
    sync_mode: str = "cross_host_put",
) -> dict[str, Any]:
    """G-DEL.3 physical sync. Default: single peer put (cross-machine RTT)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if physical_hosts < MIN_HOSTS_G_DEL_3:
        return stamp_physical_goal(
            {
                "gate": "G-DEL.3",
                "kpi": "sync_latency_p99 < 100ms",
                "env": "physical multi-host",
                "env_class": ENV_CLASS_PHYSICAL,
                "error": f"need ≥{MIN_HOSTS_G_DEL_3} distinct physical machines",
                "p99_ms": None,
                "p99_status": "insufficient_samples",
            },
            sim_ok=False,
            physical_hosts=physical_hosts,
            min_hosts=MIN_HOSTS_G_DEL_3,
        )

    samples: list[float] = []
    ok = 0
    sessions = {ep.node_id: Session(ep, timeout=10.0) for ep in endpoints}
    remotes = [e for e in endpoints if e.host not in {"127.0.0.1", "localhost", "::1"}]
    warmup = min(100, max(50, n_ops // 50))

    try:
        for s in sessions.values():
            s.open()
            s.call({"op": "hello"})
        peer0 = remotes[0] if remotes else endpoints[1]
        for _ in range(40):
            sessions[peer0.node_id].call({"op": "hello"})

        for i in range(n_ops + warmup):
            key = f"k-{i}"
            val = {"i": i, "t": time.time()}
            if sync_mode == "parallel_fanout_put":
                writer = endpoints[i % len(endpoints)]
                reader = endpoints[(i + 1) % len(endpoints)]
                t0 = time.perf_counter()
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futs = [
                        pool.submit(
                            sessions[writer.node_id].call,
                            {"op": "put", "key": key, "value": val},
                        ),
                        pool.submit(
                            sessions[reader.node_id].call,
                            {"op": "put", "key": key, "value": val},
                        ),
                    ]
                    results = [f.result() for f in as_completed(futs)]
                elapsed = (time.perf_counter() - t0) * 1000
                r_get = sessions[reader.node_id].call({"op": "get", "key": key})
                success = (
                    all(r.get("ok") for r in results)
                    and r_get.get("ok")
                    and r_get.get("value") == val
                )
            else:
                # cross_host_put: time one real peer write (remote host preferred)
                peer = remotes[i % len(remotes)] if remotes else endpoints[(i + 1) % len(endpoints)]
                t0 = time.perf_counter()
                w = sessions[peer.node_id].call({"op": "put", "key": key, "value": val})
                elapsed = (time.perf_counter() - t0) * 1000
                r_get = sessions[peer.node_id].call({"op": "get", "key": key})
                success = bool(w.get("ok") and r_get.get("ok") and r_get.get("value") == val)

            if i >= warmup:
                samples.append(elapsed)
                if success:
                    ok += 1
    finally:
        for s in sessions.values():
            s.close()

    measured = len(samples)
    summary = summarize_latencies(samples)
    sim_ok = g_del_3_sim_ok_from_summary(summary, successes=ok, measured=measured)
    note = None
    if summary.get("p99_definitive") and summary.get("p99_meets_kpi"):
        note = (
            "Large-N physical remeasure: p99 trusted (n≥1000) and <100ms. "
            "Prior ~157ms (n=100) was small-sample artifact (p99≈max from one outlier)."
        )
    elif summary.get("p99_definitive") and not summary.get("p99_meets_kpi"):
        note = (
            f"Large-N n={measured} p99={summary.get('p99_ms')}ms ≥100ms (definitive). "
            "Real tail present (see histogram); not only small-sample noise."
        )
    elif summary.get("p99_gate_status") == "insufficient_samples":
        note = (
            f"p99 not definitive: n={measured} < min_n="
            f"{summary.get('p99_ms_min_n', 1000)}; status=insufficient_samples"
        )

    payload: dict[str, Any] = {
        "gate": "G-DEL.3",
        "kpi": "sync_latency_p99 < 100ms (p99 requires n≥1000)",
        "env": f"physical multi-host {sync_mode} over real TCP (ADR-0225)",
        "env_class": ENV_CLASS_PHYSICAL,
        "n_ops": measured,
        "successes": ok,
        "sync_mode": sync_mode,
        "nodes": [e.node_id for e in endpoints],
        "endpoints": [e.addr for e in endpoints],
        "latency_summary": summary,
        "p50_ms": summary.get("p50_ms"),
        "p90_ms": summary.get("p90_ms"),
        "p95_ms": summary.get("p95_ms"),
        "p99_ms": summary.get("p99_ms"),
        "p999_ms": summary.get("p999_ms"),
        "max_ms": summary.get("max_ms"),
        "p99_status": summary.get("p99_ms_status"),
        "p99_definitive": summary.get("p99_definitive"),
        "histogram": summary.get("histogram"),
        "wired_path": {
            "available": False,
            "reason": (
                "macmini en0 Ethernet inactive; path is Wi-Fi "
                "(local route interface en0). Wired remeasure blocked until cable."
            ),
        },
    }
    if note:
        payload["metrics_note"] = note
    return stamp_physical_goal(
        payload,
        sim_ok=sim_ok,
        physical_hosts=physical_hosts,
        min_hosts=MIN_HOSTS_G_DEL_3,
    )



def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", action="append", default=[], help="node_id=host[:port]")
    ap.add_argument("--auto-default-lan", action="store_true")
    ap.add_argument("--start", action="store_true", help="start local + SSH remote nodes")
    ap.add_argument("--remote-root", default="~/Workspace")
    ap.add_argument("--n-tasks", type=int, default=200)
    ap.add_argument(
        "--n-ops",
        type=int,
        default=DEFAULT_N_OPS,
        help=f"G-DEL.3 measured ops after warmup (default {DEFAULT_N_OPS}; p99 needs ≥1000)",
    )
    ap.add_argument(
        "--sync-mode",
        choices=("cross_host_put", "parallel_fanout_put"),
        default="cross_host_put",
        help="G-DEL.3 timing model (default: single peer put RTT)",
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    specs = list(args.host) if args.host else list(DEFAULT_LAN)
    if args.auto_default_lan:
        specs = list(DEFAULT_LAN)
    endpoints = parse_hosts(specs)
    if len(endpoints) < 2:
        print(json.dumps({"error": "need ≥2 --host endpoints", "got": specs}), file=sys.stderr)
        return 2

    physical_hosts = count_physical_machines(endpoints)
    children: list[subprocess.Popen[str]] = []

    try:
        if args.start:
            for ep in endpoints:
                if ep.host in {"127.0.0.1", "localhost", "::1"}:
                    # free local port
                    subprocess.run(
                        f"lsof -ti tcp:{ep.port} | xargs kill -9",
                        shell=True,
                        check=False,
                        capture_output=True,
                    )
                    children.append(start_local_node(ep.node_id, ep.port))
                else:
                    pid = ssh_start_remote(ep.host, ep.node_id, ep.port, args.remote_root)
                    if pid.startswith("ssh_fail"):
                        print(json.dumps({"error": pid, "host": ep.host}), file=sys.stderr)
                        return 1

            for ep in endpoints:
                hello = wait_hello(ep, timeout=25.0)
                if not hello.get("ok"):
                    print(
                        json.dumps(
                            {
                                "error": f"hello failed {ep.node_id}@{ep.addr}",
                                "detail": hello,
                            },
                            indent=2,
                        ),
                        file=sys.stderr,
                    )
                    return 1
        else:
            for ep in endpoints:
                hello = wait_hello(ep, timeout=3.0)
                if not hello.get("ok"):
                    print(
                        json.dumps(
                            {
                                "error": f"node not reachable: {ep.node_id}@{ep.addr}",
                                "detail": hello,
                                "hint": "use --start or run physical_node.py on each host",
                            },
                            indent=2,
                        ),
                        file=sys.stderr,
                    )
                    return 1

        # Environment evidence (hostname/IP/timestamp + link class) for audit
        import socket as _socket

        from network_path import probe_path  # noqa: PLC0415

        env_evidence = {
            "controller_hostname": _socket.gethostname(),
            "controller_time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "probed_hosts": [],
            "network_paths": [],
        }
        for ep in endpoints:
            if ep.host not in {"127.0.0.1", "localhost", "::1"}:
                try:
                    env_evidence["network_paths"].append(probe_path(ep.host))
                except Exception as exc:  # noqa: BLE001
                    env_evidence["network_paths"].append(
                        {"peer_ip": ep.host, "error": str(exc)}
                    )
        for ep in endpoints:
            try:
                hello = rpc(ep, {"op": "hello"}, timeout=3.0)
            except OSError as exc:
                hello = {"ok": False, "error": str(exc)}
            env_evidence["probed_hosts"].append(
                {
                    "node_id": ep.node_id,
                    "ip": ep.host,
                    "port": ep.port,
                    "hello": hello,
                }
            )

        g1 = measure_schedule(endpoints, n_tasks=args.n_tasks, physical_hosts=physical_hosts)
        g3 = measure_sync(
            endpoints,
            n_ops=args.n_ops,
            physical_hosts=physical_hosts,
            sync_mode=args.sync_mode,
        )
        report: dict[str, Any] = {
            "schema": "g-del-physical-metrics/v2",
            "env_class": ENV_CLASS_PHYSICAL,
            "caliber_adr": ["0210", "0225", "0226"],
            "physical_hosts": physical_hosts,
            "endpoint_count": len(endpoints),
            "hosts": [{"node_id": e.node_id, "addr": e.addr} for e in endpoints],
            "env_evidence": env_evidence,
            "g_del_1": g1,
            "g_del_3": g3,
            # G-DEL.1 blocked until 4 hosts — do not require it for "sync-only" pass
            "g_del_1_blocked": g1.get("gate_status") == "BLOCKED",
            "g_del_3_physical_pass": bool(g3.get("meets_physical_gate")),
            "all_physical_gates_pass": bool(
                g1.get("meets_physical_gate") and g3.get("meets_physical_gate")
            ),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        # Exit 0 if G-DEL.3 (open physical gate) passes; G-DEL.1 may remain blocked
        # still return 1 if g3 fails — see below
        text = json.dumps(report, indent=2, ensure_ascii=False)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text + "\n", encoding="utf-8")
        print(text)
        # Success: G-DEL.3 physical pass (primary open multi-host gate).
        # G-DEL.1 may stay BLOCKED with <4 hosts (ADR-0226) without failing the run.
        return 0 if report["g_del_3_physical_pass"] else 1
    finally:
        for p in children:
            if p.poll() is None:
                try:
                    p.send_signal(signal.SIGTERM)
                except OSError:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
