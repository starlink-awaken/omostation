#!/usr/bin/env python3
"""file-lock-check.py — CLI tool to check lock status, detect deadlocks, and monitor high-frequency files.

Part of the high-frequency file write lock mechanism (ADR-XXXX).
Checks for orphaned locks, deadlocks, lock contention, and file integrity.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add lib to path for imports
WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "lib"))

from file_lock import (
    DEFAULT_TIMEOUT_S,
    DEADLOCK_THRESHOLD_S,
    FileLock,
    cleanup_expired,
    detect_deadlocks,
    list_dead_locks,
    list_expired_locks,
    list_locks,
    read_lock,
)
from high_frequency_files import (
    HIGH_FREQUENCY_FILES,
    HighFrequencyFileMonitor,
    get_high_frequency_paths,
)


def check_orphaned_locks() -> list[dict[str, object]]:
    """Check for orphaned locks (locks without corresponding active runs).

    Returns list of orphaned lock reports.
    """
    orphans: list[dict[str, object]] = []
    runs_dir = WORKSPACE / ".omo/_delivery/agent-workflows/runs"

    # Load active run IDs
    active_runs: set[str] = set()
    if runs_dir.is_dir():
        import yaml

        for run_file in runs_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(run_file.read_text(encoding="utf-8")) or {}
                run_id = data.get("run_id")
                if isinstance(run_id, str) and run_id:
                    active_runs.add(run_id)
            except Exception:
                continue

    # Check each lock
    for lock in list_locks():
        if lock.run_id and lock.run_id not in active_runs:
            orphans.append(
                {
                    "file": lock.scope,
                    "run_id": lock.run_id,
                    "actor": lock.actor,
                    "locked_at": lock.created_at,
                    "expired": lock.is_expired(),
                    "dead": lock.is_dead(),
                }
            )

    return orphans


def check_lock_contention() -> list[dict[str, object]]:
    """Check for lock contention on high-frequency files.

    Returns list of contention reports.
    """
    contention: list[dict[str, object]] = []
    hf_paths = get_high_frequency_paths()

    for path in hf_paths:
        lock = read_lock(path)
        if lock is not None:
            contention.append(
                {
                    "file": path,
                    "locked": True,
                    "run_id": lock.run_id,
                    "actor": lock.actor,
                    "locked_at": lock.created_at,
                    "expires_at": lock.expires_at,
                    "expired": lock.is_expired(),
                    "dead": lock.is_dead(),
                }
            )

    return contention


def check_file_integrity() -> list[dict[str, object]]:
    """Check file integrity for locked files.

    Detects if locked files have been modified since lock acquisition.
    """
    from file_lock import check_conflict

    issues: list[dict[str, object]] = []
    for lock in list_locks():
        conflict = check_conflict(lock.scope)
        if conflict is not None:
            issues.append(conflict)
    return issues


def check_deadlock_detection() -> list[dict[str, object]]:
    """Detect potential deadlocks.

    Returns list of deadlock reports.
    """
    return detect_deadlocks()


def run_full_check(strict: bool = False) -> dict[str, object]:
    """Run full lock health check.

    Args:
        strict: If True, treat all issues as errors.

    Returns:
        Check report dict.
    """
    orphaned = check_orphaned_locks()
    contention = check_lock_contention()
    integrity = check_file_integrity()
    deadlocks = check_deadlock_detection()
    expired = list_expired_locks()
    dead = list_dead_locks()

    # Determine overall status
    has_issues = bool(orphaned or deadlocks or integrity)
    ok = not has_issues if strict else not deadlocks

    return {
        "ok": ok,
        "strict": strict,
        "summary": {
            "total_locks": len(list_locks()),
            "orphaned_locks": len(orphaned),
            "expired_locks": len(expired),
            "dead_locks": len(dead),
            "deadlocks": len(deadlocks),
            "contention_files": len(contention),
            "integrity_issues": len(integrity),
        },
        "orphaned_locks": orphaned,
        "deadlocks": deadlocks,
        "contention": contention,
        "integrity_issues": integrity,
        "high_frequency_files": [
            {"path": f[0], "description": f[1], "expected_writers": f[2]} for f in HIGH_FREQUENCY_FILES
        ],
    }


def print_human(report: dict[str, object], verbose: bool = False) -> None:
    """Print human-readable report."""
    ok = report.get("ok", False)
    summary = report.get("summary", {})

    print("═══ File Lock Health Check ═══")
    print(f"Status: {'PASS' if ok else 'FAIL'}")
    print(f"  Total locks: {summary.get('total_locks', 0)}")
    print(f"  Orphaned: {summary.get('orphaned_locks', 0)}")
    print(f"  Expired: {summary.get('expired_locks', 0)}")
    print(f"  Dead: {summary.get('dead_locks', 0)}")
    print(f"  Deadlocks: {summary.get('deadlocks', 0)}")
    print(f"  Contention files: {summary.get('contention_files', 0)}")
    print(f"  Integrity issues: {summary.get('integrity_issues', 0)}")

    if verbose:
        orphaned = report.get("orphaned_locks", [])
        if orphaned:
            print("\n─── Orphaned Locks ───")
            for o in orphaned:
                print(f"  {o.get('file')} (run: {o.get('run_id')}, actor: {o.get('actor')})")

        deadlocks = report.get("deadlocks", [])
        if deadlocks:
            print("\n─── Deadlocks ───")
            for d in deadlocks:
                print(f"  {d.get('file')} (run: {d.get('run_id')}, actor: {d.get('actor')})")

        contention = report.get("contention", [])
        if contention:
            print("\n─── Lock Contention ───")
            for c in contention:
                status = "EXPIRED" if c.get("expired") else "DEAD" if c.get("dead") else "ACTIVE"
                print(f"  {c.get('file')} [{status}] (run: {c.get('run_id')})")

        integrity = report.get("integrity_issues", [])
        if integrity:
            print("\n─── Integrity Issues ───")
            for i in integrity:
                print(
                    f"  {i.get('file')}: hash mismatch (locked: {i.get('locked_hash', '')[:16]}..., current: {i.get('current_hash', '')[:16]}...)"
                )

    if not report.get("ok", False):
        print(
            "\n  HINT: file-lock FAIL → bin/gac/file-lock-check.py --cleanup 清理过期锁; contention → monitor 子命令; deadlocks → 检查对应 run_id 心跳"
        )
        print("  强约束: 高频文件并发写必须经 file_lock 序列化, 否则门禁阻断 (CR-FILE-LOCK)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check file lock status, detect deadlocks, and monitor high-frequency files"
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Treat all issues as errors")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--cleanup", action="store_true", help="Clean up expired locks")

    sub = parser.add_subparsers(dest="command")

    # Shared arguments for subcommands
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    shared.add_argument("--strict", action="store_true", help="Treat all issues as errors")
    shared.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # Subcommands
    sub.add_parser("status", help="Show lock status", parents=[shared])
    sub.add_parser("deadlocks", help="Detect deadlocks", parents=[shared])
    sub.add_parser("contention", help="Check lock contention", parents=[shared])
    sub.add_parser("integrity", help="Check file integrity", parents=[shared])
    sub.add_parser("orphaned", help="Check orphaned locks", parents=[shared])
    sub.add_parser("monitor", help="Monitor high-frequency files", parents=[shared])

    args = parser.parse_args()

    # Handle cleanup
    if args.cleanup:
        cleaned = cleanup_expired()
        if args.json:
            print(json.dumps({"cleaned": cleaned, "count": len(cleaned)}, indent=2))
        else:
            print(f"Cleaned {len(cleaned)} expired locks")
            for f in cleaned:
                print(f"  {f}")
        return 0

    # Handle subcommands
    if args.command == "status":
        report = run_full_check(strict=args.strict)
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print_human(report, verbose=args.verbose)
        return 0 if report.get("ok") else 1

    elif args.command == "deadlocks":
        deadlocks = check_deadlock_detection()
        if args.json:
            print(json.dumps(deadlocks, indent=2, default=str))
        else:
            if deadlocks:
                print(f"Found {len(deadlocks)} potential deadlocks:")
                for d in deadlocks:
                    print(f"  {d.get('file')} (run: {d.get('run_id')}, actor: {d.get('actor')})")
            else:
                print("No deadlocks detected")
        return 1 if deadlocks else 0

    elif args.command == "contention":
        contention = check_lock_contention()
        if args.json:
            print(json.dumps(contention, indent=2, default=str))
        else:
            if contention:
                print(f"Found {len(contention)} files with lock contention:")
                for c in contention:
                    status = "EXPIRED" if c.get("expired") else "DEAD" if c.get("dead") else "ACTIVE"
                    print(f"  {c.get('file')} [{status}]")
            else:
                print("No lock contention detected")
        return 0

    elif args.command == "integrity":
        integrity = check_file_integrity()
        if args.json:
            print(json.dumps(integrity, indent=2, default=str))
        else:
            if integrity:
                print(f"Found {len(integrity)} integrity issues:")
                for i in integrity:
                    print(f"  {i.get('file')}: hash mismatch")
            else:
                print("No integrity issues detected")
        return 1 if integrity else 0

    elif args.command == "orphaned":
        orphaned = check_orphaned_locks()
        if args.json:
            print(json.dumps(orphaned, indent=2, default=str))
        else:
            if orphaned:
                print(f"Found {len(orphaned)} orphaned locks:")
                for o in orphaned:
                    print(f"  {o.get('file')} (run: {o.get('run_id')})")
            else:
                print("No orphaned locks detected")
        return 0

    elif args.command == "monitor":
        monitor = HighFrequencyFileMonitor()
        monitor.snapshot()
        changes = monitor.detect_changes()
        conflicts = monitor.detect_conflicts()
        report = monitor.report()
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print(f"Monitored {report['monitored_files']} files")
            print(f"Changes detected: {report['recent_changes']}")
            print(f"Conflicts detected: {report['conflicts_detected']}")
            if conflicts:
                for c in conflicts:
                    print(f"  CONFLICT: {c.file} (writers: {', '.join(c.writers)})")
        return 1 if conflicts else 0

    else:
        # Default: full check
        report = run_full_check(strict=args.strict)
        if args.json:
            print(json.dumps(report, indent=2, default=str))
        else:
            print_human(report, verbose=args.verbose)
        return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
