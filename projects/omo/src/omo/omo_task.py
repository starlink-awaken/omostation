#!/usr/bin/env python3
"""OMO task CLI — list and inspect tasks from .omo/tasks/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _find_omo_dir() -> Path:
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        omo = parent / ".omo"
        if omo.is_dir():
            return omo
    print("❌ .omo/ directory not found", file=sys.stderr)
    sys.exit(1)


def cmd_task_list(omo_dir: Path, status: str | None) -> int:
    """List tasks filtered by status directory."""
    if status:
        dirs = [omo_dir / "tasks" / status]
    else:
        dirs = [omo_dir / "tasks" / s for s in ("active", "planned", "done")]
    total = 0
    for d in dirs:
        if not d.exists():
            continue
        files = sorted(d.glob("*.yaml"))
        if not files:
            continue
        label = d.relative_to(omo_dir / "tasks")
        print(f"=== {label} ({len(files)} tasks) ===")
        for f in files[:20]:
            data = f.read_text().split("\n")[:3]
            tid = ""
            for line in data:
                if line.startswith("id:") or line.startswith("title:"):
                    tid += line.strip() + " "
            print(f"  {f.stem}: {tid[:60]}")
        if len(files) > 20:
            print(f"  ... and {len(files)-20} more")
        total += len(files)
    print(f"\nTotal: {total} tasks")
    return 0


def cmd_task_create(omo_dir: Path, title: str, desc: str, priority: str) -> int:
    import uuid
    import yaml
    from datetime import datetime
    
    task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
    status = "planned"
    task_dir = omo_dir / "tasks" / status
    task_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = task_dir / f"{task_id}.yaml"
    data = {
        "id": task_id,
        "title": title,
        "description": desc,
        "status": status,
        "priority": priority,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    
    file_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    print(f"Created task: {file_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="omo task", description="OMO task browser")
    sub = parser.add_subparsers(dest="command")
    
    tl = sub.add_parser("list", help="List tasks")
    tl.add_argument("--status", "-s", choices=["active", "planned", "done"], help="Filter by status")
    
    tc = sub.add_parser("create", help="Create a new task")
    tc.add_argument("--title", required=True, help="Task title")
    tc.add_argument("--desc", default="", help="Task description")
    tc.add_argument("--priority", default="P2", help="Task priority (P0, P1, P2)")
    
    args = parser.parse_args(argv)
    omo_dir = _find_omo_dir()
    
    if args.command == "list":
        return cmd_task_list(omo_dir, args.status)
    elif args.command == "create":
        return cmd_task_create(omo_dir, args.title, args.desc, args.priority)
        
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
