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


def cmd_goal_trace(omo_dir: Path, goal_id: str) -> int:
    """从顶层 Vision/Goal 逐层向下追溯到 Bet, Tasks, Workflows 与 MOS Beliefs"""
    ws_root = omo_dir.parent
    goal_file = omo_dir / "goals" / "current.yaml"
    print(f"═══ 全景追溯 (Vision-to-Execution Trace): Goal [{goal_id}] ═══\n")
    
    # 1. Goal 信息
    if goal_file.exists():
        data = load_yaml_required(goal_file)
        goals = data.get("active_goals") or data.get("goals") or []
        target_g = None
        for g in goals:
            if isinstance(g, dict) and g.get("id") == goal_id:
                target_g = g
                break
        if target_g:
            print(f"[Layer 1: Goal] {target_g.get('id')} — {target_g.get('desc', target_g.get('title', ''))}")
            print(f"  Status: {target_g.get('status', 'active')} | Progress: {target_g.get('progress', 0)}%")
        else:
            print(f"[Layer 1: Goal] {goal_id} (Declared in current.yaml)")
    print()

    # 2. 关联 Bet
    ledger_file = ws_root / "docs" / "plans" / "3y-bet-ledger.yaml"
    matched_bets = []
    if ledger_file.exists():
        import yaml
        ldata = {}
        for d in yaml.safe_load_all(ledger_file.read_text(encoding="utf-8")):
            if isinstance(d, dict):
                ldata.update(d)
        for b in ldata.get("bets", []):
            if isinstance(b, dict) and b.get("goal_id") == goal_id:
                matched_bets.append(b)
    print(f"[Layer 2: C2G Bets] (找到 {len(matched_bets)} 个关联 Bet):")
    for b in matched_bets:
        print(f"  • [{b.get('id')}] {b.get('title')} ({b.get('status')})")
    print()

    # 3. 关联 Tasks
    planned_dir = omo_dir / "tasks" / "planned"
    matched_tasks = []
    if planned_dir.exists():
        from omo.omo_shared import load_yaml_value
        for tf in planned_dir.glob("*.yaml"):
            tval = load_yaml_value(tf)
            if isinstance(tval, dict) and tval.get("goal_id") == goal_id:
                matched_tasks.append(tval)
    print(f"[Layer 3: OMO Tasks] (找到 {len(matched_tasks)} 个计划任务):")
    for t in matched_tasks:
        print(f"  • [{t.get('id')}] {t.get('title')}")
    print()

    # 4. MOS 关联信念
    try:
        from omo.omo_belief import MOSBeliefManager
        beliefs = MOSBeliefManager(root=ws_root).query_beliefs()
    except Exception:
        beliefs = []
    print(f"[Layer 5: MOS Agent Beliefs] (积累 {len(beliefs)} 项感知):")
    for b in beliefs[:3]:
        print(f"  • [{b.get('topic')}] {b.get('belief')}")

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(prog="omo goal", description="Manage Phase goals")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List Phase goals")
    sub.add_parser("status", help="Show completion status as JSON")

    p_trace = sub.add_parser("trace", help="Trace goal down to bets, tasks and beliefs")
    p_trace.add_argument("id", help="Goal ID")

    p_create = sub.add_parser("create", help="Create a new goal")
    p_create.add_argument("id", help="Goal ID")
    p_create.add_argument("desc", help="Goal description")
    p_create.add_argument("--source-ref", default="", help="Stable mutation source reference")

    p_prog = sub.add_parser("progress", help="Update goal progress")
    p_prog.add_argument("id", help="Goal ID")
    p_prog.add_argument("pct", type=int, help="Percentage (0-100)")

    gr = sub.add_parser("reconcile", help="Reconcile current goals file for wave/phase")
    gr.add_argument("--phase", required=True, help="Current phase number")
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
    elif args.command == "trace":
        return cmd_goal_trace(omo_dir, args.id)
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
