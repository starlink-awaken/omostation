#!/usr/bin/env python3
"""OMO goal CLI — read and display Phase goals from _truth/goals/."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


from omo.omo_io import write_yaml_atomic


def _find_omo_dir() -> Path:
    """Find .omo/ directory by walking up from cwd."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        omo = parent / ".omo"
        if omo.is_dir():
            return omo
    print("❌ .omo/ directory not found", file=sys.stderr)
    sys.exit(1)


def cmd_goal_list(omo_dir: Path) -> int:
    """List all Phase goals from current.yaml."""
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        print("⚠️  No current goals found (goals/current.yaml)")
        return 0
    data = yaml.safe_load(goal_file.read_text())
    phase = data.get("phase", "?")
    theme = data.get("theme", "")
    status = data.get("status", "?")
    wave = data.get("current_wave", "?")
    print(f"Phase {phase} — {theme}")
    print(f"Status: {status} | Wave: {wave}")
    print()

    goals = data.get("goals", [])
    if not goals:
        print("  (no goals defined)")
        return 0
    for g in goals:
        gid = g.get("id", "?")
        desc = g.get("desc", "")
        pct = g.get("progress", 0)
        st = g.get("status", "?")
        icon = "✅" if st == "done" else "🔄" if st == "active" else "⏳"
        print(f"  {icon} {gid}: {desc}")
        print(f"     Progress: {pct}% | Status: {st}")
    print(f"\n{len(goals)} goals total")
    return 0


def cmd_goal_status(omo_dir: Path) -> int:
    """Show Phase goal completion status (JSON for machine consumption)."""
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        print(json.dumps({"error": "no goals file"}))
        return 1
    data = yaml.safe_load(goal_file.read_text())
    goals = data.get("goals", [])
    done = sum(1 for g in goals if g.get("status") == "done")
    active = sum(1 for g in goals if g.get("status") == "active")
    pending = sum(1 for g in goals if g.get("status") not in ("done", "active"))
    print(json.dumps({
        "phase": data.get("phase"),
        "wave": data.get("current_wave"),
        "total": len(goals),
        "done": done,
        "active": active,
        "pending": pending,
    }, indent=2))
    return 0


def cmd_goal_create(omo_dir: Path, goal_id: str, description: str) -> int:
    """Add a new goal to goals/current.yaml."""
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        print("❌ goals/current.yaml not found", file=sys.stderr)
        return 1
    data = yaml.safe_load(goal_file.read_text())
    goals = data.get("goals", [])
    # Check duplicate
    for g in goals:
        if g.get("id") == goal_id:
            print(f"❌ Goal {goal_id} already exists", file=sys.stderr)
            return 1
    new_goal = {
        "id": goal_id,
        "desc": description,
        "progress": 0.0,
        "status": "pending",
        "tasks": [],
    }
    goals.append(new_goal)
    data["goals"] = goals
    write_yaml_atomic(goal_file, data)
    print(f"✅ Goal {goal_id} created")
    return 0


def cmd_goal_progress(omo_dir: Path, goal_id: str, progress: float) -> int:
    """Update progress for a specific goal."""
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        print("❌ goals/current.yaml not found", file=sys.stderr)
        return 1
    data = yaml.safe_load(goal_file.read_text())
    for g in data.get("goals", []):
        if g.get("id") == goal_id:
            g["progress"] = progress
            if progress >= 100:
                g["status"] = "done"
            elif progress > 0:
                g["status"] = "active"
            write_yaml_atomic(goal_file, data)
            print(f"✅ Goal {goal_id}: progress → {progress}%")
            return 0
    print(f"❌ Goal {goal_id} not found", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo goal", description="OMO Phase goal management")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List all Phase goals")
    sub.add_parser("status", help="Show goal completion (JSON)")
    gc = sub.add_parser("create", help="Create a new goal")
    gc.add_argument("--id", required=True, help="Goal ID (e.g. G29.1)")
    gc.add_argument("--desc", required=True, help="Goal description")
    gp = sub.add_parser("progress", help="Update goal progress")
    gp.add_argument("--id", required=True, help="Goal ID")
    gp.add_argument("--pct", type=float, required=True, help="Progress percentage (0-100)")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_goal_list(omo_dir)
    elif args.command == "status":
        return cmd_goal_status(omo_dir)
    elif args.command == "create":
        return cmd_goal_create(omo_dir, args.id, args.desc)
    elif args.command == "progress":
        return cmd_goal_progress(omo_dir, args.id, args.pct)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
