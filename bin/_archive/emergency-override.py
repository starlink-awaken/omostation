#!/usr/bin/env python3
"""Emergency Override — 用户不可用时的约束代决策 (P4-T4).

When checkpoint timeout occurs and user is unreachable:
1. Evaluate situation urgency
2. Execute SAFE constrained actions (holding responses, deadline extensions)
3. Log all emergency decisions for post-hoc review
4. NEVER: submit final docs, send novel communications, make irreversible commitments

Usage: python3 bin/ssot/emergency-override.py [--check] [--json]
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
EMERGENCY_LOG = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "emergency-overrides.jsonl"

SAFE_ACTIONS = {
    "holding_response": "Send 'received, processing, will respond by {deadline}'",
    "extend_internal_deadline": "Extend internal deadline by up to 24h",
    "reschedule_non_critical": "Reschedule non-critical tasks",
    "escalate_notification": "Send urgent notification to backup contact",
}

FORBIDDEN_ACTIONS = {
    "submit_final_document": "Cannot submit final docs to superiors",
    "send_novel_communication": "Cannot send new types of communications",
    "make_irreversible_commitment": "Cannot make binding commitments",
    "financial_transaction": "Cannot execute financial transactions",
}


def check_emergencies() -> list[dict[str, Any]]:
    """Check for timed-out checkpoints that need emergency handling."""
    emergencies: list[dict[str, Any]] = []
    states_dir = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "journey-states"

    if not states_dir.is_dir():
        return []

    now = datetime.now(UTC)
    for journey_dir in states_dir.iterdir():
        if not journey_dir.is_dir():
            continue
        for run_file in journey_dir.glob("*.jsonl"):
            try:
                lines = run_file.read_text(encoding="utf-8").strip().split("\n")
                if not lines or not lines[-1].strip():
                    continue
                last = json.loads(lines[-1])
                if last.get("status") != "awaiting_human":
                    continue
                checkpoint = last.get("checkpoint", {})
                timeout_hours = checkpoint.get("timeout_hours", 48)
                ts_str = last.get("ts", "")
                if not ts_str:
                    continue
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                elapsed = (now - ts).total_seconds() / 3600
                if elapsed > timeout_hours:
                    emergencies.append({
                        "journey_id": last.get("journey_id", journey_dir.name),
                        "run_id": run_file.stem,
                        "state": last.get("state", "?"),
                        "elapsed_hours": round(elapsed, 1),
                        "timeout_hours": timeout_hours,
                        "checkpoint": checkpoint,
                        "recommended_action": "holding_response",
                        "constraints": list(SAFE_ACTIONS.keys()),
                    })
            except Exception:
                continue

    return emergencies


def execute_emergency(emergency: dict[str, Any], *, actor: str = "system") -> dict[str, Any]:
    """Execute a constrained emergency action (SAFE only)."""
    action = emergency.get("recommended_action", "holding_response")
    if action not in SAFE_ACTIONS:
        return {"status": "rejected", "reason": f"Action '{action}' not in safe list"}

    ts = datetime.now(UTC).isoformat()
    entry = {
        "ts": ts,
        "schema": "emergency-override/v1",
        "journey_id": emergency["journey_id"],
        "run_id": emergency["run_id"],
        "action_taken": action,
        "action_description": SAFE_ACTIONS[action],
        "actor": actor,
        "elapsed_hours": emergency["elapsed_hours"],
        "constraints_applied": list(FORBIDDEN_ACTIONS.keys()),
        "review_required": True,
    }

    EMERGENCY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(EMERGENCY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    entry["status"] = "executed"
    return entry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check for emergencies")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--execute", action="store_true", help="execute safe actions for found emergencies")
    args = parser.parse_args(argv)

    emergencies = check_emergencies() if (args.check or args.execute or not args.json) else []

    if args.execute and emergencies:
        for e in emergencies:
            execute_emergency(e)

    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "emergencies_found": len(emergencies),
        "safe_actions_available": list(SAFE_ACTIONS.keys()),
        "forbidden_actions": list(FORBIDDEN_ACTIONS.keys()),
        "emergencies": emergencies,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"Emergency Override: {len(emergencies)} timed-out checkpoints found")
        for e in emergencies:
            print(f"  ⚠️  {e['journey_id']}/{e['run_id']} elapsed={e['elapsed_hours']}h → {e['recommended_action']}")
        if not emergencies:
            print("  ✅ No emergencies detected.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
