#!/usr/bin/env python3
"""CLI tool to check submodule status, detect drift, and trigger auto-update.

Wraps lib.submodule_auto.SubmoduleAutoManager for command-line usage.

Usage:
    python3 bin/gac/submodule-auto-check.py                # check drift
    python3 bin/gac/submodule-auto-check.py --fix           # dry-run fix
    python3 bin/gac/submodule-auto-check.py --fix --apply   # apply fixes
    python3 bin/gac/submodule-auto-check.py --integrity     # full integrity check
    python3 bin/gac/submodule-auto-check.py --json          # JSON output
    python3 bin/gac/submodule-auto-check.py --strict        # treat behind as drift
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add repo root to path for lib import
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from lib.submodule_auto import (
    SubmoduleAutoManager,
    DriftStatus,
    UpdateResult,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submodule pointer drift detection and auto-update",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      Check for drift
  %(prog)s --fix                Show fix suggestions (dry-run)
  %(prog)s --fix --apply        Apply fixes
  %(prog)s --integrity          Full integrity check
  %(prog)s --json               JSON output
  %(prog)s --strict             Treat 'behind' as drift
  %(prog)s --from-head          Read gitlink from HEAD instead of index
        """,
    )
    parser.add_argument("--check", action="store_true", default=True, help="Check for drift (default, read-only)")
    parser.add_argument("--fix", action="store_true", help="Show fix suggestions (dry-run)")
    parser.add_argument("--apply", action="store_true", help="Apply fixes (requires --fix)")
    parser.add_argument("--strict", action="store_true", help="Treat 'behind' status as drift")
    parser.add_argument("--integrity", action="store_true", help="Run full integrity check")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--from-head", action="store_true", help="Read gitlink from HEAD instead of index")
    parser.add_argument("--root", type=Path, default=None, help="Repository root (default: auto-detect)")
    args = parser.parse_args()

    repo_root = args.root or REPO_ROOT
    source = "head" if args.from_head else "index"

    mgr = SubmoduleAutoManager(
        repo_root=repo_root,
        strict=args.strict,
    )

    # Integrity check mode
    if args.integrity:
        report = mgr.check_integrity()
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            _print_drift_report(report)
        return 1 if report.has_drift else 0

    # Fix mode
    if args.fix:
        update_report = mgr.auto_update(apply=args.apply, strict=args.strict)
        if args.json:
            print(json.dumps(update_report.to_dict(), indent=2))
        else:
            _print_update_report(update_report, dry_run=not args.apply)

        # Exit non-zero if there were failures
        if update_report.failed > 0 or update_report.rolled_back > 0:
            return 1
        return 0

    # Default: check mode
    report = mgr.detect_drift(source=source)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_drift_report(report)

    if report.has_drift:
        return 1
    if report.has_stale and args.strict:
        return 1
    return 0


def _print_drift_report(report) -> None:
    """Print human-readable drift report."""
    print("== submodule pointer drift check ==")
    print()

    for s in report.submodules:
        status = s.drift_status
        path = s.path
        gitlink = (s.gitlink_sha or "")[:12]
        remote = (s.remote_sha or "")[:12]

        if status == DriftStatus.ALIGNED:
            print(f"  OK   {path}: {gitlink}")
        elif status == DriftStatus.BEHIND:
            print(f"  WARN {path}: {gitlink} <- remote {remote} (stale)")
        elif status == DriftStatus.AHEAD:
            print(f"  OK   {path}: {gitlink} (ahead, non-blocking)")
        elif status == DriftStatus.DIVERGED:
            print(f"  FAIL {path}: {gitlink} NOT on remote {remote}")
        elif status == DriftStatus.SKIP:
            print(f"  SKIP {path}: {s.detail or 'skipped'}")
        elif status == DriftStatus.UNVERIFIABLE:
            print(f"  OK   {path}: {gitlink} (shallow, unverifiable)")
        elif status == DriftStatus.ERROR:
            print(f"  ERR  {path}: {s.detail or 'error'}")

    print()
    print(
        f"  Total: {report.total} | "
        f"{report.aligned} aligned | "
        f"{report.behind} behind | "
        f"{report.ahead} ahead | "
        f"{report.diverged} DIVERGED | "
        f"{report.skipped} skipped"
    )

    if report.has_drift:
        print(f"\n  {report.diverged} DIVERGED — root pointer targets side branch!")
        print("  Run --fix for suggestions, --fix --apply to execute")
        print(
            "  HINT: drift 检出 → bin/gac/submodule-auto-check.py --check --json; 修复 → --fix (dry-run) / --apply; 校验 → --integrity"
        )
        print("  强约束: diverged 直接 FAIL, behind 非阻断但提示 (CR-SUBMODULE-AUTO)")
    elif report.has_stale:
        print(f"\n  No divergence ({report.behind} behind, non-blocking)")
        print("  HINT: behind 为可自愈滞后, 需更新时 → bin/gac/submodule-auto-check.py --fix --apply")
    else:
        print("\n  ALL ALIGNED")


def _print_update_report(report, dry_run: bool = True) -> None:
    """Print human-readable update report."""
    mode = "DRY-RUN" if dry_run else "APPLIED"
    print(f"== submodule auto-update ({mode}) ==")
    print()

    for r in report.results:
        result = r.update_result
        icon = {
            UpdateResult.UPDATED: "FIXED",
            UpdateResult.ALREADY_ALIGNED: "OK",
            UpdateResult.SKIPPED: "SKIP",
            UpdateResult.FAILED: "FAIL",
            UpdateResult.ROLLED_BACK: "ROLLBACK",
        }.get(result, "?")
        print(f"  {icon:8s} {r.path}: {r.detail or ''}")

    print()
    print(
        f"  Attempted: {report.attempted} | "
        f"Updated: {report.updated} | "
        f"Skipped: {report.skipped} | "
        f"Failed: {report.failed} | "
        f"Rolled back: {report.rolled_back}"
    )

    if dry_run and report.updated > 0:
        print("\n  This was a dry-run. Use --fix --apply to execute.")
    elif not dry_run and report.updated > 0:
        print(f"\n  {report.updated} submodule pointer(s) updated.")
        print("  Stage and commit the changes to persist.")


if __name__ == "__main__":
    raise SystemExit(main())
