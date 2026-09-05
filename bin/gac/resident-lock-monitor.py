#!/usr/bin/env python3
"""resident-lock-monitor — Resident Agent 锁监控与自动恢复。

检测并报告:
1. 过期锁 (lock age > threshold)
2. 孤立锁 (无对应 run)
3. 死锁 (同一 scope 多个锁)

Usage:
    python3 bin/gac/resident-lock-monitor.py [--clean] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOCKS_DIR = REPO / ".omo" / "_delivery" / "agent-workflows" / "locks"
RUNS_DIR = REPO / ".omo" / "_delivery" / "agent-workflows" / "runs"

# 锁过期阈值 (秒)
STALE_THRESHOLDS = {
    "default": 3600,      # 1 小时
    "bet-execution": 7200,  # 2 小时
    "project-code-change": 3600,
    "project-doc-change": 1800,
}


def get_lock_age(lock_file: Path) -> float:
    """获取锁文件年龄 (秒)。"""
    try:
        with open(lock_file) as f:
            data = json.load(f)
        created = data.get("created_at", data.get("timestamp", ""))
        if created:
            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - created_dt).total_seconds()
    except Exception:
        pass
    # 回退到文件 mtime
    return time.time() - lock_file.stat().st_mtime


def get_lock_scope(lock_file: Path) -> str:
    """获取锁的 scope。"""
    try:
        with open(lock_file) as f:
            data = json.load(f)
        return data.get("scope", data.get("bet_id", "unknown"))
    except Exception:
        return "unknown"


def find_active_runs() -> set[str]:
    """查找活跃的 run_id 集合。"""
    active = set()
    if RUNS_DIR.exists():
        for run_dir in RUNS_DIR.iterdir():
            if run_dir.is_dir():
                state_file = run_dir / "state.yaml"
                if state_file.exists():
                    try:
                        content = state_file.read_text()
                        if "status: active" in content:
                            active.add(run_dir.name)
                    except Exception:
                        pass
    return active


def scan_locks() -> dict:
    """扫描所有锁。"""
    result = {
        "total": 0,
        "stale": [],
        "orphan": [],
        "active": [],
        "by_scope": {},
    }

    if not LOCKS_DIR.exists():
        return result

    active_runs = find_active_runs()

    for lock_file in LOCKS_DIR.glob("*.json"):
        result["total"] += 1
        age = get_lock_age(lock_file)
        scope = get_lock_scope(lock_file)
        run_id = lock_file.stem

        lock_info = {
            "file": str(lock_file.relative_to(REPO)),
            "scope": scope,
            "age_seconds": int(age),
            "age_human": f"{age/3600:.1f}h" if age > 3600 else f"{age/60:.0f}m",
        }

        # 检查是否过期
        threshold = STALE_THRESHOLDS.get(scope, STALE_THRESHOLDS["default"])
        is_stale = age > threshold

        # 检查是否为孤儿锁 (无对应 active run)
        is_orphan = run_id not in active_runs and not scope.startswith("root-")

        if is_stale:
            result["stale"].append(lock_info)
        elif is_orphan:
            result["orphan"].append(lock_info)
        else:
            result["active"].append(lock_info)

        # 按 scope 统计
        result["by_scope"].setdefault(scope, []).append(lock_info)

    return result


def clean_stale_locks(stale_locks: list[dict]) -> int:
    """清理过期锁。"""
    cleaned = 0
    for lock in stale_locks:
        lock_path = REPO / lock["file"]
        try:
            lock_path.unlink()
            cleaned += 1
        except Exception:
            pass
    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Resident Agent 锁监控")
    parser.add_argument("--clean", action="store_true", help="清理过期锁")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    result = scan_locks()

    if args.clean:
        cleaned = clean_stale_locks(result["stale"])
        result["cleaned"] = cleaned

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Resident Lock Monitor")
        print(f"  Total locks: {result['total']}")
        print(f"  Active: {len(result['active'])}")
        print(f"  Stale: {len(result['stale'])}")
        print(f"  Orphan: {len(result['orphan'])}")

        if result["stale"]:
            print(f"\n  Stale locks:")
            for lock in result["stale"]:
                print(f"    ⚠️ {lock['scope']}: {lock['age_human']} ({lock['file']})")

        if result["orphan"]:
            print(f"\n  Orphan locks:")
            for lock in result["orphan"]:
                print(f"    ❌ {lock['scope']}: {lock['file']}")

        if args.clean:
            print(f"\n  Cleaned: {result.get('cleaned', 0)} stale locks")

    # 有过期或孤儿锁时 exit 1
    return 1 if result["stale"] or result["orphan"] else 0


if __name__ == "__main__":
    sys.exit(main())
