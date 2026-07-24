#!/usr/bin/env python3
"""Archive completed/historical task YAML into the tracked cold tree.

Phase45 W3.1 / STRAT-P81 S0.2 (skeptic-hardened):
  - Destination is **tracked** ``.omo/tasks/archived/`` (NOT gitignored
    ``.omo/_archive/`` — moving into gitignore would destroy repo history).
  - Active metric for phase45 acceptance = count of ``*.yaml`` under
    ``.omo/tasks`` **excluding** ``archived/`` (plan: 退出活跃 view).
  - Dry-run by default; pass ``--apply`` to execute moves.
  - Never deletes; preserves relative paths under archived/.
  - After --apply, stage with ``git add -A -- .omo/tasks`` so renames enter the
    index (disk-only moves leave mass D without A/R — skeptic fail).

Exit codes:
  0 success
  1 configuration / path error
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
TASKS = WORKSPACE / ".omo" / "tasks"
# Tracked cold tree (plan wording). Must NOT use gitignored .omo/_archive/.
COLD = TASKS / "archived"
DEFAULT_SOURCES = ("done", "archive")  # 'archived' is already the cold tree


def count_yaml(root: Path, *, exclude_archived: bool = False) -> int:
    if not root.is_dir():
        return 0
    n = 0
    for p in root.rglob("*.yaml"):
        if exclude_archived and "archived" in p.relative_to(root).parts:
            continue
        n += 1
    return n


def plan_moves(sources: tuple[str, ...]) -> list[tuple[Path, Path]]:
    moves: list[tuple[Path, Path]] = []
    for name in sources:
        src = TASKS / name
        if not src.exists() or name == "archived":
            continue
        dest = COLD / name
        moves.append((src, dest))
    return moves


def apply_moves(moves: list[tuple[Path, Path]]) -> list[dict]:
    results = []
    for src, dest in moves:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            for child in src.iterdir():
                target = dest / child.name
                if target.exists():
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    target = dest / f"{child.name}.merged-{stamp}"
                shutil.move(str(child), str(target))
            try:
                src.rmdir()
            except OSError:
                pass
            results.append({"src": str(src), "dest": str(dest), "mode": "merge"})
        else:
            shutil.move(str(src), str(dest))
            results.append({"src": str(src), "dest": str(dest), "mode": "move"})
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="Execute moves (default: dry-run)")
    p.add_argument(
        "--sources",
        default=",".join(DEFAULT_SOURCES),
        help="Comma-separated top-level dirs under .omo/tasks to archive into archived/",
    )
    p.add_argument("--json", action="store_true", help="Emit machine-readable summary")
    p.add_argument(
        "--target-max",
        type=int,
        default=200,
        help="Phase45 active-view target (excludes archived/)",
    )
    p.add_argument(
        "--restore-from-gitignored",
        action="store_true",
        help="Move .omo/_archive/tasks/* back under .omo/tasks/archived/ (tracked)",
    )
    args = p.parse_args(argv)

    if not TASKS.is_dir():
        print(f"error: missing {TASKS}", file=sys.stderr)
        return 1

    summary: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tasks_root": str(TASKS),
        "cold_root": str(COLD),
        "cold_root_tracked": True,
        "gitignored_forbidden": ".omo/_archive/",
        "apply": bool(args.apply),
        "target_max": args.target_max,
    }

    if args.restore_from_gitignored:
        bad = WORKSPACE / ".omo" / "_archive" / "tasks"
        summary["restore_from"] = str(bad)
        if not bad.is_dir():
            summary["restore"] = "noop_missing"
        elif args.apply:
            COLD.mkdir(parents=True, exist_ok=True)
            restored = []
            for child in bad.iterdir():
                dest = COLD / child.name
                if dest.exists():
                    # merge children
                    if child.is_dir():
                        dest.mkdir(parents=True, exist_ok=True)
                        for g in child.rglob("*"):
                            if g.is_file():
                                rel = g.relative_to(child)
                                t = dest / rel
                                t.parent.mkdir(parents=True, exist_ok=True)
                                if not t.exists():
                                    shutil.move(str(g), str(t))
                    restored.append({"src": str(child), "dest": str(dest), "mode": "merge"})
                else:
                    shutil.move(str(child), str(dest))
                    restored.append({"src": str(child), "dest": str(dest), "mode": "move"})
            summary["restore"] = restored
        else:
            summary["restore"] = "dry_run"
            summary["would_restore"] = [str(c) for c in bad.iterdir()]
    else:
        sources = tuple(s.strip() for s in args.sources.split(",") if s.strip())
        before_all = count_yaml(TASKS, exclude_archived=False)
        before_active = count_yaml(TASKS, exclude_archived=True)
        moves = plan_moves(sources)
        planned_files = sum(count_yaml(s) for s, _ in moves if s.is_dir())
        summary.update(
            {
                "sources": list(sources),
                "before_all": before_all,
                "before_active": before_active,
                "planned_move_dirs": [str(s) for s, _ in moves],
                "planned_file_count": planned_files,
                "projected_active_after": before_active - planned_files,
            }
        )
        if args.apply:
            COLD.mkdir(parents=True, exist_ok=True)
            summary["results"] = apply_moves(moves)
            summary["after_all"] = count_yaml(TASKS, exclude_archived=False)
            summary["after_active"] = count_yaml(TASKS, exclude_archived=True)
            summary["meets_active_target"] = summary["after_active"] < args.target_max
        else:
            summary["meets_active_target"] = (
                before_active - planned_files
            ) < args.target_max

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
