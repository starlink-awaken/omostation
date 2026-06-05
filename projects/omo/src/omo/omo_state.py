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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo state", description="OMO system state viewer")
    sub = parser.add_subparsers(dest="command")
    sp = sub.add_parser("show", help="Show system state")
    sp.add_argument("--format", "-f", choices=["text", "json"], default="text")
    sub.add_parser("health", help="Show service health")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "show":
        return cmd_state_show(omo_dir, args.format)
    elif args.command == "health":
        return cmd_state_health(omo_dir)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
