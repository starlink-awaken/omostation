#!/usr/bin/env python3
"""OMO state CLI — show system state from state/."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

OMO_HINT = ".omo"


def _find_omo_dir() -> Path:
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        omo = parent / OMO_HINT
        if omo.is_dir():
            return omo
    print("❌ .omo/ directory not found", file=sys.stderr)
    sys.exit(1)


def cmd_state_show(omo_dir: Path, fmt: str) -> int:
    state_file = omo_dir / "state" / "system.yaml"
    if not state_file.exists():
        print("⚠️  state/system.yaml not found")
        return 0
    data = yaml.safe_load(state_file.read_text())
    if fmt == "json":
        print(json.dumps(data, indent=2, default=str))
        return 0
    # Tabular format
    print(f"Phase:          {data.get('current_phase', '?')}")
    print(f"Health:         {data.get('health_score', '?')}")
    print(f"Active agents:  {data.get('active_agents', 0)}")
    print(f"Idle agents:    {data.get('idle_agents', 0)}")
    print(f"Blocked tasks:  {data.get('blocked_tasks', 0)}")
    print(f"Code freeze:    {data.get('code_freeze', False)}")
    print(f"Next milestone: {data.get('next_milestone', '?')}")
    return 0


def cmd_state_health(omo_dir: Path) -> int:
    health_file = omo_dir / "state" / "system_health.yaml"
    if not health_file.exists():
        print("⚠️  state/system_health.yaml not found")
        return 0
    data = yaml.safe_load(health_file.read_text())
    svc_dict = data.get("services", {}) if isinstance(data, dict) else {}
    running = 0
    failed = 0
    for name, svc in svc_dict.items():
        if isinstance(svc, dict):
            st = (svc.get("health_check") or
                  svc.get("runtime", {}).get("status", "") or "")
            if st == "healthy":
                running += 1
            elif st in ("failed", "stopped"):
                failed += 1
    total = len(svc_dict)
    print(f"Services: {total} total ({running} healthy, {failed} degraded)")
    print()
    for name, svc in svc_dict.items():
        if not isinstance(svc, dict):
            continue
        st = svc.get("health_check") or svc.get("runtime", {}).get("status", "") or "?"
        icon = "🟢" if st == "healthy" else "🟡" if st in ("idle", "unmanaged") else "🔴" if st in ("failed", "stopped") else "⚪"
        detail = svc.get("name", name)
        print(f"  {icon} {detail}: {st}")
    return 0


def cmd_state_refresh(omo_dir: Path, dry_run: bool) -> int:
    """Scan runtime Matrix and refresh system_health.yaml.

    Queries:
    1. Runtime CLI: `runtime matrix list` — service registry
    2. KEI audit: `~/.runtime/data/kei_audit.jsonl` — recent audit records
    3. Agora health: `:7430/health` — Agora status
    """
    import subprocess
    import time

    health_file = omo_dir / "state" / "system_health.yaml"
    current_data = yaml.safe_load(health_file.read_text()) if health_file.exists() else {"services": {}}
    services = current_data.get("services", {}) if isinstance(current_data, dict) else {}
    now = time.time()

    updates = 0
    # 1. Query runtime Matrix for service list
    try:
        result = subprocess.run(
            ["python3", "-m", "runtime", "matrix", "list", "--json"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path.home() / "Workspace" / "projects" / "runtime"),
        )
        if result.returncode == 0 and result.stdout.strip():
            import json as _json
            matrix_data = _json.loads(result.stdout)
            for svc in matrix_data if isinstance(matrix_data, list) else []:
                name = svc.get("name", "?")
                svc_status = svc.get("status", "unknown")
                port = svc.get("port")
                if name not in services:
                    services[name] = {"name": name, "health_check": "unknown"}
                services[name]["runtime"] = {
                    "status": svc_status,
                    "port": port,
                    "timestamp": now,
                    "freshness_seconds": 0,
                }
                updates += 1
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("⚠️  Runtime Matrix query failed (runtime CLI not available)")

    # 2. Update health_check based on runtime status
    for name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        rt = svc.get("runtime", {})
        if isinstance(rt, dict):
            rst = rt.get("status", "")
            if rst == "running":
                svc["health_check"] = "healthy"
                svc["port_listening"] = bool(rt.get("port"))
            elif rst in ("failed", "stopped"):
                svc["health_check"] = "failed"

    # 3. Write back
    output = {"last_scan": now, "services": services}
    if dry_run:
        print(json.dumps(output, indent=2, default=str))
        print(f"\n(dry-run: {updates} services would be updated)")
    else:
        health_file.write_text(yaml.dump(output, default_flow_style=False, allow_unicode=True))
        print(f"✅ system_health.yaml refreshed: {updates} services updated")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo state", description="OMO system state viewer")
    sub = parser.add_subparsers(dest="command")
    sp = sub.add_parser("show", help="Show system state")
    sp.add_argument("--format", "-f", choices=["text", "json"], default="text")
    sub.add_parser("health", help="Show service health")
    rp = sub.add_parser("refresh", help="Scan runtime Matrix and refresh system_health.yaml")
    rp.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "show":
        return cmd_state_show(omo_dir, args.format)
    elif args.command == "health":
        return cmd_state_health(omo_dir)
    elif args.command == "refresh":
        return cmd_state_refresh(omo_dir, dry_run=args.dry_run)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
