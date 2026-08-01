#!/usr/bin/env python3
"""OMO goal CLI — read and display Phase goals from _truth/goals/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from omo.omo_ingress import create_goal, reconcile_goals, update_goal_progress
from omo.omo_paths import find_omo_dir
from omo.omo_shared import load_yaml_required


def _find_omo_dir() -> Path:
    """Find the authoritative workspace .omo directory."""
    return find_omo_dir()


def cmd_goal_list(omo_dir: Path) -> int:
    """List all Phase goals from current.yaml."""
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        print("⚠️  No current goals found (goals/current.yaml)")
        return 0
    data = load_yaml_required(goal_file)
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
    data = load_yaml_required(goal_file)
    goals = data.get("goals", [])
    done = sum(1 for g in goals if g.get("status") == "done")
    active = sum(1 for g in goals if g.get("status") == "active")
    pending = sum(1 for g in goals if g.get("status") not in ("done", "active"))
    print(
        json.dumps(
            {
                "phase": data.get("phase"),
                "wave": data.get("current_wave"),
                "total": len(goals),
                "done": done,
                "active": active,
                "pending": pending,
            },
            indent=2,
        )
    )
    return 0


def cmd_goal_create(
    omo_dir: Path, goal_id: str, description: str, source_ref: str = ""
) -> int:
    """Create a goal through the governed ingress broker."""
    goal_file = omo_dir / "goals" / "current.yaml"
    if not goal_file.exists():
        print("❌ goals/current.yaml not found", file=sys.stderr)
        return 1
    try:
        create_goal(
            omo_dir,
            goal_id=goal_id,
            title=goal_id,
            description=description,
            ingress_plane="projects/omo",
            source_ref=source_ref or f"omo:goal:create:{goal_id}",
        )
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    print(f"✅ Governed goal {goal_id} created")
    print(
        f"Artifact: {omo_dir / '_delivery' / 'ingress' / 'goals' / f'{goal_id}.yaml'}"
    )
    return 0


def cmd_goal_progress(omo_dir: Path, goal_id: str, progress: float) -> int:
    """Update progress for a specific goal through governed ingress."""
    try:
        updated = update_goal_progress(
            omo_dir,
            goal_id=goal_id,
            progress=progress,
            actor="projects/omo",
            source_ref=f"omo:goal:progress:{goal_id}:{progress}",
        )
    except FileNotFoundError:
        print("❌ goals/current.yaml not found", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    print(f"✅ Goal {goal_id}: progress → {updated['progress']}%")
    print(f"Status: {updated['status']}")
    return 0


def cmd_goal_reconcile(
    omo_dir: Path,
    *,
    phase: int,
    current_wave: str,
    execution_mode: str,
    theme: str,
    archive_completed: bool,
    source_ref: str,
) -> int:
    """Reconcile phase/state fields through the governed goal broker."""
    try:
        payload = reconcile_goals(
            omo_dir,
            phase=phase,
            current_wave=current_wave,
            execution_mode=execution_mode,
            theme=theme,
            archive_completed=archive_completed,
            actor="projects/omo",
            source_ref=source_ref,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    print(
        f"✅ Goals reconciled: phase={payload.get('phase')} "
        f"wave={payload.get('current_wave')} "
        f"mode={payload.get('execution_mode')}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo goal", description="OMO Phase goal management"
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List all Phase goals")
    sub.add_parser("status", help="Show goal completion (JSON)")
    gc = sub.add_parser("create", help="Create a new goal")
    gc.add_argument("--id", required=True, help="Goal ID (e.g. G29.1)")
    gc.add_argument("--desc", required=True, help="Goal description")
    gc.add_argument(
        "--source-ref", default="", help="Stable source ref for ingress registry"
    )
    gp = sub.add_parser("progress", help="Update goal progress")
    gp.add_argument("--id", required=True, help="Goal ID")
    gp.add_argument(
        "--pct", type=float, required=True, help="Progress percentage (0-100)"
    )
    gr = sub.add_parser("reconcile", help="Reconcile governed phase and goal state")
    gr.add_argument("--phase", type=int, required=True, help="Current phase")
    gr.add_argument("--wave", dest="current_wave", required=True, help="Current wave")
    gr.add_argument(
        "--execution-mode",
        default="waiting-for-scenario/next-bet",
        help="Execution mode (default: waiting-for-scenario/next-bet)",
    )
    gr.add_argument("--theme", default="", help="Current phase theme")
    gr.add_argument(
        "--archive-completed",
        action="store_true",
        help="Archive goals already marked done/completed",
    )
    gr.add_argument("--source-ref", default="", help="Stable mutation source reference")
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    if args.command == "list":
        return cmd_goal_list(omo_dir)
    elif args.command == "status":
        return cmd_goal_status(omo_dir)
    elif args.command == "create":
        return cmd_goal_create(omo_dir, args.id, args.desc, args.source_ref)
    elif args.command == "progress":
        return cmd_goal_progress(omo_dir, args.id, args.pct)
    elif args.command == "reconcile":
        return cmd_goal_reconcile(
            omo_dir,
            phase=args.phase,
            current_wave=args.current_wave,
            execution_mode=args.execution_mode,
            theme=args.theme,
            archive_completed=args.archive_completed,
            source_ref=args.source_ref,
        )
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
