#!/usr/bin/env python3
"""CLI tool to check agent workflow standardization compliance.

Usage:
    python3 bin/gac/agent-workflow-standard-check.py [OPTIONS]

Options:
    --run-id RUN_ID       Check specific run ID
    --agent-id AGENT_ID   Agent identifier for signature validation
    --check-ranges        Check range declarations
    --check-locks         Check lock status
    --check-signatures    Check signature validation
    --check-modifications Check modification verification
    --all                 Run all checks (default)
    --json                Output as JSON
    --cleanup             Clean up expired locks
    --status              Show standardization status
    -h, --help            Show this help message
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add workspace to path
WORKSPACE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE / "lib"))

from agent_workflow_standard import (
    STANDARD_MODE_ENV,
    StandardError,
    check_compliance,
    check_lock_status,
    cleanup_expired_locks,
    get_standard_status,
    read_lock_status,
    read_range_declaration,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check agent workflow standardization compliance")
    parser.add_argument(
        "--run-id",
        help="Check specific run ID",
    )
    parser.add_argument(
        "--agent-id",
        help="Agent identifier for signature validation",
    )
    parser.add_argument(
        "--check-ranges",
        action="store_true",
        help="Check range declarations",
    )
    parser.add_argument(
        "--check-locks",
        action="store_true",
        help="Check lock status",
    )
    parser.add_argument(
        "--check-signatures",
        action="store_true",
        help="Check signature validation",
    )
    parser.add_argument(
        "--check-modifications",
        action="store_true",
        help="Check modification verification",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all checks (default)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Clean up expired locks",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show standardization status",
    )
    return parser.parse_args(argv)


def check_range_declarations(run_id: str | None = None) -> dict:
    """Check range declarations."""
    results = {"check": "range_declarations", "violations": []}

    if run_id:
        decl = read_range_declaration(run_id)
        if decl:
            results["declaration"] = decl
            results["status"] = "found"
        else:
            results["status"] = "not_found"
            results["violations"].append(
                {
                    "type": "missing_declaration",
                    "run_id": run_id,
                    "message": f"No range declaration found for run {run_id}",
                }
            )
    else:
        # Check all declarations
        decl_dir = WORKSPACE / ".omo" / "state" / "agent-workflow-standard" / "range-declarations"
        if decl_dir.exists():
            declarations = list(decl_dir.glob("*.yaml"))
            results["total_declarations"] = len(declarations)
            results["declarations"] = [d.stem for d in declarations]
        else:
            results["total_declarations"] = 0
            results["declarations"] = []

    return results


def check_lock_statuses(run_id: str | None = None) -> dict:
    """Check lock statuses."""
    results = {"check": "lock_status", "violations": []}

    if run_id:
        lock = read_lock_status(run_id)
        if lock:
            results["lock"] = lock
            results["status"] = "found"
        else:
            results["status"] = "not_found"
            results["violations"].append(
                {
                    "type": "missing_lock",
                    "run_id": run_id,
                    "message": f"No lock found for run {run_id}",
                }
            )
    else:
        # Check all locks
        lock_dir = WORKSPACE / ".omo" / "state" / "agent-workflow-standard" / "lock-status"
        if lock_dir.exists():
            locks = list(lock_dir.glob("*.lock.yaml"))
            results["total_locks"] = len(locks)
            results["locks"] = [l.stem.replace(".lock", "") for l in locks]
        else:
            results["total_locks"] = 0
            results["locks"] = []

    return results


def run_compliance_check(run_id: str, agent_id: str) -> dict:
    """Run full compliance check."""
    try:
        return check_compliance(run_id, agent_id)
    except StandardError as e:
        return {
            "run_id": run_id,
            "agent_id": agent_id,
            "compliant": False,
            "error": str(e),
        }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Handle cleanup
    if args.cleanup:
        cleaned = cleanup_expired_locks()
        if args.json:
            print(json.dumps({"cleaned": cleaned}, indent=2))
        else:
            print(f"Cleaned up {cleaned} expired locks")
        return 0

    # Handle status
    if args.status:
        status = get_standard_status()
        if args.json:
            print(json.dumps(status, indent=2))
        else:
            print("Agent Workflow Standard Status:")
            print(f"  Standard mode enabled: {status['standard_mode_enabled']}")
            print(f"  Active locks: {status['active_locks']}")
            print(f"  Active declarations: {status['active_declarations']}")
            print(f"  State directory: {status['state_dir']}")
        return 0

    # Determine which checks to run
    run_all = args.all or not any(
        [
            args.check_ranges,
            args.check_locks,
            args.check_signatures,
            args.check_modifications,
        ]
    )

    results = {}

    # Run compliance check if run-id and agent-id provided
    if args.run_id and args.agent_id:
        results["compliance"] = run_compliance_check(args.run_id, args.agent_id)

    # Run individual checks
    if run_all or args.check_ranges:
        results["ranges"] = check_range_declarations(args.run_id)

    if run_all or args.check_locks:
        results["locks"] = check_lock_statuses(args.run_id)

    # Determine violations before output (for HINT)
    has_violations = False
    for check_results in results.values():
        if isinstance(check_results, dict):
            if check_results.get("violations"):
                has_violations = True
            if check_results.get("compliant") is False:
                has_violations = True

    # Output results
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print("Agent Workflow Standard Check Results:")
        print("=" * 50)

        if "compliance" in results:
            comp = results["compliance"]
            print(f"\nCompliance Check for {comp.get('run_id', 'unknown')}:")
            print(f"  Compliant: {comp.get('compliant', False)}")
            if comp.get("violations"):
                print("  Violations:")
                for v in comp["violations"]:
                    print(f"    - [{v.get('severity', 'unknown')}] {v.get('message', '')}")

        if "ranges" in results:
            ranges = results["ranges"]
            print(f"\nRange Declarations:")
            print(f"  Status: {ranges.get('status', 'unknown')}")
            if ranges.get("violations"):
                print("  Violations:")
                for v in ranges["violations"]:
                    print(f"    - {v.get('message', '')}")

        if "locks" in results:
            locks = results["locks"]
            print(f"\nLock Status:")
            print(f"  Status: {locks.get('status', 'unknown')}")
            if locks.get("violations"):
                print("  Violations:")
                for v in locks["violations"]:
                    print(f"    - {v.get('message', '')}")

        if has_violations:
            print(
                "\n  HINT: agent-std FAIL → bin/gac/agent-workflow-standard-check.py --all --json 查看详情; 范围外写 → 先声明 --check-ranges"
            )
            print("  强约束: 未声明范围/未持锁/签名缺失直接 FAIL (CR-AGENT-WORKFLOW-STD)")

    return 1 if has_violations else 0


if __name__ == "__main__":
    sys.exit(main())
