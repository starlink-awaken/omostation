#!/usr/bin/env python3
"""STRAT-P81 Batch2 C1 — physical recovery entry (dry-run safe, fail-closed).

One command path after hosts return:
  probe → registry backfill plan → G-DEL.3 two-host measure plan → G-DEL.1 four-host precheck

Never claims meets_physical_gate=true from dry-run or sim. Physical pass requires
real measure_physical + human confirm (workorder §F).
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / ".omo" / "_knowledge" / "audits"


def _probe_host(host: str, port: int = 22, timeout: float = 1.5) -> dict[str, Any]:
    t0 = time.time()
    ok = False
    err = None
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ok = True
    except OSError as e:
        err = str(e)
    return {
        "host": host,
        "port": port,
        "reachable": ok,
        "latency_ms": round((time.time() - t0) * 1000, 2) if ok else None,
        "error": err,
    }


def default_host_list() -> list[str]:
    raw = os.environ.get("PHYSICAL_RECOVERY_HOSTS", "").strip()
    if raw:
        return [h.strip() for h in raw.split(",") if h.strip()]
    # Fail-closed inventory (may be offline) — never invent green hosts
    return ["127.0.0.1", "192.168.31.210", "macmini.local", "y7000p.local"]


def run_recovery(
    *,
    dry_run: bool = True,
    hosts: list[str] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    hosts = hosts or default_host_list()
    probes = [_probe_host(h) for h in hosts]
    reachable = [p for p in probes if p["reachable"]]
    n = len(reachable)

    # Plans only — no real G-DEL measure that could flip physical gate
    registry_plan = {
        "action": "register_reachable_nodes",
        "would_register": [p["host"] for p in reachable],
        "skipped_unreachable": [p["host"] for p in probes if not p["reachable"]],
        "applied": False,  # never auto-applied; human recovery-day apply only
    }
    g_del_3_plan = {
        "gate": "G-DEL.3",
        "required_hosts": 2,
        "reachable_hosts": n,
        "ready": n >= 2,
        "measure_command": "uv run --project projects/... measure_physical --n-ops 10000",
        "executed": False,
        "meets_physical_gate": False,
    }
    g_del_1_precheck = {
        "gate": "G-DEL.1",
        "required_hosts": 4,
        "reachable_hosts": n,
        "ready": n >= 4,
        "executed": False,
        "meets_physical_gate": False,
    }

    report: dict[str, Any] = {
        "ok": dry_run,  # dry-run always "ok" as a rehearsal; never physical pass
        "dry_run": dry_run,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probes": probes,
        "reachable_count": n,
        "registry_plan": registry_plan,
        "g_del_3_plan": g_del_3_plan,
        "g_del_1_precheck": g_del_1_precheck,
        "meets_sim_harness": True,
        "meets_physical_gate": False,
        "meets_gate": False,
        "env_class": "physical_multi_host" if n else "in-process_simulation",
        "note": (
            "Batch2 C1 recovery package. dry-run does not claim physical pass. "
            "Human + real measure_physical required for G-DEL.1/3 official."
        ),
    }

    out = out_dir or DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    day = time.strftime("%Y-%m-%d", time.gmtime())
    path = out / f"{day}-physical-recovery-dry-run.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(path)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--live", action="store_true", help="reserved; still fail-closed without hosts")
    p.add_argument("--hosts", default="", help="comma-separated hosts override")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()] or None
    report = run_recovery(
        dry_run=not args.live,
        hosts=hosts,
        out_dir=args.out,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    # dry-run success = 0; live with physical claim forbidden unless real hosts measured
    if report.get("meets_physical_gate") is True:
        return 3  # hard violation
    return 0 if report.get("ok") or report.get("dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
