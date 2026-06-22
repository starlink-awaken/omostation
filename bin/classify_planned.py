#!/usr/bin/env python3
"""Read-only planned queue classifier aligned with canonical OMO schema."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
OMO_SRC = WORKSPACE_ROOT / "projects" / "omo" / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))

from omo.omo_task_schema import validate_task_data  # noqa: E402


PLANNED_DIR = WORKSPACE_ROOT / ".omo" / "tasks" / "planned"
APPROVAL_QUEUE_PATH = (
    WORKSPACE_ROOT / ".omo" / "workers" / "promotion" / "approval-queue" / "current.yaml"
)


def load_task(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def load_approval_queue_index() -> dict[str, dict[str, Any]]:
    payload = load_yaml(APPROVAL_QUEUE_PATH)
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for item in tasks:
        if not isinstance(item, dict):
            continue
        task_id = item.get("task_id")
        if isinstance(task_id, str) and task_id:
            index[task_id] = item
    return index


def classify() -> dict[str, Any]:
    files = sorted(PLANNED_DIR.glob("*.yaml"))
    approval_queue_index = load_approval_queue_index()

    result: dict[str, Any] = {
        "summary": {
            "total": len(files),
            "valid": 0,
            "invalid": 0,
            "candidate": 0,
            "pending": 0,
            "approval_required": 0,
            "approval_pending": 0,
            "approval_ready_to_promote": 0,
            "approval_granted_blocked": 0,
            "high_risk": 0,
        },
        "invalid_packets": [],
        "approval_queue": [],
        "approval_required_backlog": [],
        "approval_pending_queue": [],
        "approval_ready_to_promote_queue": [],
        "approval_granted_blocked_queue": [],
        "high_risk_backlog": [],
        "normal_backlog": [],
        "next_actions": [],
    }

    for path in files:
        payload = load_task(path)
        task_id = payload.get("id", path.stem)
        status = str(payload.get("status", "missing"))
        risk_level = str(payload.get("risk_level", payload.get("risk", "missing")))
        approval_required = bool(payload.get("human_approval_required"))
        errors = validate_task_data(payload, group="planned")
        entry: dict[str, Any] = {
            "task_id": task_id,
            "title": payload.get("title", path.stem),
            "status": status,
            "risk_level": risk_level,
            "approval_required": approval_required,
            "path": str(path.relative_to(WORKSPACE_ROOT)),
        }

        if errors:
            entry["errors"] = errors
            result["invalid_packets"].append(entry)
            result["summary"]["invalid"] += 1
            continue

        result["summary"]["valid"] += 1
        if status in ("candidate", "pending"):
            result["summary"][status] += 1

        if approval_required:
            queue_entry = approval_queue_index.get(str(task_id), {})
            entry["approval_status"] = queue_entry.get("approval_status")
            entry["proposal_status"] = queue_entry.get("proposal_status")
            entry["eligible"] = queue_entry.get("eligible")
            entry["blockers"] = list(queue_entry.get("blockers", [])) if isinstance(queue_entry.get("blockers"), list) else []
            entry["next_action"] = queue_entry.get("next_action", "materialize_queue_status")

            result["summary"]["approval_required"] += 1
            result["approval_required_backlog"].append(entry)

            if entry["next_action"] == "promote_apply":
                result["summary"]["approval_ready_to_promote"] += 1
                result["approval_ready_to_promote_queue"].append(entry)
            elif entry["approval_status"] == "granted":
                result["summary"]["approval_granted_blocked"] += 1
                result["approval_granted_blocked_queue"].append(entry)
            else:
                result["summary"]["approval_pending"] += 1
                result["approval_pending_queue"].append(entry)
            continue

        if risk_level in ("L2", "L3"):
            result["summary"]["high_risk"] += 1
            result["high_risk_backlog"].append(entry)
        else:
            result["normal_backlog"].append(entry)

    result["approval_queue"] = result["approval_pending_queue"]

    if result["summary"]["invalid"] > 0:
        result["next_actions"].append(
            "python3 scripts/omo/omo_worker.py task normalize-planned --actor <ACTOR> --now <ISO8601> --omo-dir .omo"
        )
    if result["summary"]["approval_required"] > 0:
        result["next_actions"].append(
            "python3 scripts/omo/omo_worker.py task approval-queue-status --omo-dir .omo"
        )
    if result["summary"]["approval_ready_to_promote"] > 0:
        result["next_actions"].append(
            "python3 scripts/omo/omo_worker.py task promote-apply <TASK_ID> --promoted-by <ACTOR> --now <ISO8601> --omo-dir .omo"
        )
    if not result["next_actions"]:
        result["next_actions"].append(
            "python3 scripts/omo/omo_worker.py task promotion-readiness --omo-dir .omo"
        )

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="classify planned tasks against canonical OMO schema (read-only)"
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 而不是 YAML")
    args = parser.parse_args(argv)

    result = classify()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))

    print(
        f"# valid: {result['summary']['valid']} / invalid: {result['summary']['invalid']} / "
        f"approval_required: {result['summary']['approval_required']} / "
        f"approval_pending: {result['summary']['approval_pending']} / "
        f"approval_granted_blocked: {result['summary']['approval_granted_blocked']} / "
        f"approval_ready_to_promote: {result['summary']['approval_ready_to_promote']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
