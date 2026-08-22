#!/usr/bin/env python3
"""fix-orphan-locks.py — 清理无对应 run 的孤儿锁."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def _load_run_ids(runs_dir: Path) -> set[str]:
    run_ids: set[str] = set()
    if not runs_dir.is_dir():
        return run_ids
    for run_file in sorted(runs_dir.glob("*.yaml")):
        try:
            import yaml

            payload = yaml.safe_load(run_file.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        run_id = payload.get("run_id")
        if isinstance(run_id, str) and run_id:
            run_ids.add(run_id)
    return run_ids


def scan_orphan_locks(workspace: Path) -> list[dict[str, object]]:
    locks_dir = workspace / ".omo/_delivery/agent-workflows/locks"
    runs_dir = workspace / ".omo/_delivery/agent-workflows/runs"
    run_ids = _load_run_ids(runs_dir)
    orphans: list[dict[str, object]] = []
    if not locks_dir.is_dir():
        return orphans
    for lock_file in sorted(locks_dir.glob("*.yaml")):
        if lock_file.name.startswith("."):
            continue
        try:
            import yaml

            lock = yaml.safe_load(lock_file.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        lock_run_id = str(lock.get("run_id") or "")
        if lock_run_id and lock_run_id in run_ids:
            continue
        orphans.append(
            {
                "path": str(lock_file),
                "run_id": lock_run_id or None,
                "actor": lock.get("actor"),
            }
        )
    return orphans


def move_to_archive(lock_path: Path, archive_dir: Path) -> Path:
    archive_dir.mkdir(parents=True, exist_ok=True)
    target = archive_dir / lock_path.name
    shutil.move(str(lock_path), str(target))
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fix orphan lock files")
    parser.add_argument("--registry", type=Path, default=WORKSPACE / ".omo")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    orphans = scan_orphan_locks(WORKSPACE)
    report: dict[str, object] = {
        "orphan_count": len(orphans),
        "orphans": orphans,
        "applied": [],
    }
    if args.apply and orphans:
        archive_dir = WORKSPACE / ".omo/_delivery/agent-workflows/locks/.archive"
        for item in orphans:
            target = move_to_archive(Path(str(item["path"])), archive_dir)
            report["applied"].append(str(target))

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
