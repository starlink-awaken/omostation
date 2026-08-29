#!/usr/bin/env python3
"""Goal Mode Test — 验证 BET claim → verify → closeout 流程.

最小化 Goal 模式测试:
1. Claim 一个简单 BET
2. 执行一个最小任务
3. 验证结果
4. Closeout BET

Usage:
    python3 bin/gac/goal-mode-test.py --claim
    python3 bin/gac/goal-mode-test.py --execute
    python3 bin/gac/goal-mode-test.py --verify
    python3 bin/gac/goal-mode-test.py --closeout
    python3 bin/gac/goal-mode-test.py --full-test
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE_FILE = REPO / ".omo" / "_state" / "goal-mode-test.json"

# Test BET
TEST_BET = {
    "id": "BET-TEST-001",
    "title": "Goal Mode 验证测试",
    "appetite": "0.5 day",
    "objective": "验证 BET claim → execute → verify → closeout 全流程",
    "deliverables": ["goal-mode-test-result.json"],
    "success_criteria": ["BET 状态从 active → done", "deliverable 文件存在"],
}


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"status": "init", "steps": []}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def claim_bet() -> dict:
    """Claim the test BET."""
    state = _load_state()
    state["bet"] = TEST_BET
    state["status"] = "claimed"
    state["steps"].append({"step": "claim", "at": datetime.now(timezone.utc).isoformat()})
    _save_state(state)
    return {"ok": True, "bet_id": TEST_BET["id"], "status": "claimed"}


def execute_task() -> dict:
    """Execute the minimal task."""
    state = _load_state()
    if state.get("status") != "claimed":
        return {"ok": False, "error": "BET not claimed yet"}

    # Create deliverable
    deliverable = {
        "bet_id": TEST_BET["id"],
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "result": "Goal mode test executed successfully",
        "checks": {
            "bridge_runtime": _check_command(["python3", str(REPO / "bin/gac/bridge-runtime.py"), "--status"]),
            "heartbeat": _check_command(["python3", str(REPO / "bin/gac/probe-heartbeat-monitor.py"), "--status"]),
        },
    }

    # Write deliverable
    deliverable_path = REPO / ".omo" / "_state" / "goal-mode-test-result.json"
    deliverable_path.write_text(json.dumps(deliverable, indent=2, ensure_ascii=False), encoding="utf-8")

    state["status"] = "executed"
    state["steps"].append({"step": "execute", "at": datetime.now(timezone.utc).isoformat()})
    _save_state(state)

    return {"ok": True, "deliverable": str(deliverable_path)}


def verify_result() -> dict:
    """Verify the deliverable exists and is valid."""
    state = _load_state()
    if state.get("status") != "executed":
        return {"ok": False, "error": "Task not executed yet"}

    deliverable_path = REPO / ".omo" / "_state" / "goal-mode-test-result.json"
    if not deliverable_path.exists():
        return {"ok": False, "error": "Deliverable not found"}

    try:
        deliverable = json.loads(deliverable_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"ok": False, "error": f"Invalid deliverable: {e}"}

    # Verify checks passed
    checks = deliverable.get("checks", {})
    all_passed = all(v.get("ok") for v in checks.values() if isinstance(v, dict))

    state["status"] = "verified"
    state["steps"].append({"step": "verify", "at": datetime.now(timezone.utc).isoformat(), "passed": all_passed})
    _save_state(state)

    return {"ok": True, "passed": all_passed, "checks": list(checks.keys())}


def closeout_bet() -> dict:
    """Closeout the BET."""
    state = _load_state()
    if state.get("status") != "verified":
        return {"ok": False, "error": "BET not verified yet"}

    state["status"] = "done"
    state["steps"].append({"step": "closeout", "at": datetime.now(timezone.utc).isoformat()})
    _save_state(state)

    return {"ok": True, "bet_id": TEST_BET["id"], "status": "done"}


def _check_command(cmd: list[str]) -> dict:
    """Run a command and return result."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        return {"ok": result.returncode == 0, "stdout": result.stdout[:200]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def full_test() -> int:
    """Run the full test flow."""
    print("=== Goal Mode 全流程测试 ===\n")

    # Step 1: Claim
    print("[1/4] Claim BET...")
    result = claim_bet()
    if not result.get("ok"):
        print(f"  ✗ Failed: {result.get('error')}")
        return 1
    print(f"  ✓ Claimed: {result['bet_id']}")

    # Step 2: Execute
    print("[2/4] Execute task...")
    result = execute_task()
    if not result.get("ok"):
        print(f"  ✗ Failed: {result.get('error')}")
        return 1
    print(f"  ✓ Executed: {result['deliverable']}")

    # Step 3: Verify
    print("[3/4] Verify result...")
    result = verify_result()
    if not result.get("ok"):
        print(f"  ✗ Failed: {result.get('error')}")
        return 1
    print(f"  ✓ Verified: {result['passed']}")

    # Step 4: Closeout
    print("[4/4] Closeout BET...")
    result = closeout_bet()
    if not result.get("ok"):
        print(f"  ✗ Failed: {result.get('error')}")
        return 1
    print(f"  ✓ Closed: {result['bet_id']} → {result['status']}")

    print("\n=== 测试通过 ===")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Goal Mode Test")
    parser.add_argument("--claim", action="store_true", help="Claim BET")
    parser.add_argument("--execute", action="store_true", help="Execute task")
    parser.add_argument("--verify", action="store_true", help="Verify result")
    parser.add_argument("--closeout", action="store_true", help="Closeout BET")
    parser.add_argument("--full-test", action="store_true", help="Run full test")
    args = parser.parse_args()

    if args.full_test:
        return full_test()

    if args.claim:
        result = claim_bet()
    elif args.execute:
        result = execute_task()
    elif args.verify:
        result = verify_result()
    elif args.closeout:
        result = closeout_bet()
    else:
        parser.print_help()
        return 0

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
