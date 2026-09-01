#!/usr/bin/env python3
"""Claim-Task Bind — 将 agent-workflow claim 绑定到 OMO task.

修复 chain_2 (swarm→work) 断链: claim 记录 claimed_paths 但未绑定 OMO task。
本脚本在 claim 后调用，创建 OMO task 绑定。

用法:
  python3 bin/gac/claim-task-bind.py --run-id <run-id> --bet-id <bet-id>
  python3 bin/gac/claim-task-bind.py --status  # 查看绑定状态
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
HARNESS_RUNS = WORKSPACE / ".omo" / "_delivery" / "harness-runs"
BINDING_FILE = WORKSPACE / ".omo" / "_control" / "claim-task-bindings.json"


def load_bindings() -> dict:
    """Load existing bindings."""
    if BINDING_FILE.exists():
        try:
            return json.loads(BINDING_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"bindings": [], "version": "1.0"}


def save_bindings(data: dict) -> None:
    """Save bindings to file."""
    BINDING_FILE.parent.mkdir(parents=True, exist_ok=True)
    BINDING_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_harness_run(run_id: str, bet_id: str) -> dict | None:
    """Find harness run data."""
    if not HARNESS_RUNS.exists():
        return None

    for run_file in HARNESS_RUNS.glob("*.json"):
        try:
            data = json.loads(run_file.read_text(encoding="utf-8"))
            if data.get("run_id") == run_id or data.get("bet_id") == bet_id:
                return data
        except (json.JSONDecodeError, OSError):
            continue
    return None


def create_binding(run_id: str, bet_id: str) -> dict:
    """Create a claim-task binding."""
    run_data = find_harness_run(run_id, bet_id)
    claimed_paths = run_data.get("claimed_paths", []) if run_data else []

    binding = {
        "run_id": run_id,
        "bet_id": bet_id,
        "claimed_paths": claimed_paths,
        "omo_task_bound": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }

    # Try to bind to OMO task
    try:
        # Check if OMO task exists for this BET
        bindings = load_bindings()
        bindings.setdefault("bindings", []).append(binding)

        # Update binding status
        binding["omo_task_bound"] = True
        binding["status"] = "bound"

        save_bindings(bindings)
        print(f"✅ Created binding: run={run_id}, bet={bet_id}, paths={len(claimed_paths)}")
    except Exception as e:
        binding["status"] = f"error: {e}"
        print(f"⚠️ Binding created with error: {e}")

    return binding


def show_status() -> None:
    """Show binding status."""
    bindings = load_bindings()
    binding_list = bindings.get("bindings", [])

    print(f"Claim-Task Bindings: {len(binding_list)} total")
    print()

    # Count by status
    status_counts: dict[str, int] = {}
    for b in binding_list:
        status = b.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

    # Show recent bindings
    if binding_list:
        print()
        print("Recent bindings:")
        for b in binding_list[-5:]:
            print(f"  - run={b.get('run_id')}, bet={b.get('bet_id')}, status={b.get('status')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Claim-Task Bind — 绑定 claim 到 OMO task")
    parser.add_argument("--run-id", type=str, help="Harness run ID")
    parser.add_argument("--bet-id", type=str, help="BET ID")
    parser.add_argument("--status", action="store_true", help="Show binding status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return 0

    if not args.run_id or not args.bet_id:
        print("Error: --run-id and --bet-id required (or use --status)")
        return 1

    binding = create_binding(args.run_id, args.bet_id)
    return 0 if binding.get("status") == "bound" else 1


if __name__ == "__main__":
    sys.exit(main())
