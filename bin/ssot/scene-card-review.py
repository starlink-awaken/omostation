#!/usr/bin/env python3
"""Scene Card Review — 每周复盘统计引擎.

The review engine generates weekly statistics for the pilot:
- Time saved estimation
- Accuracy rate (approved vs rejected)
- Source distribution
- Priority distribution
- Weekly trends

SSOT:  ecos/src/ecos/ssot/registry/scene-cards.yaml
Engine: bin/ssot/scene-card-review.py
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_engine(workspace_root: Path, filename: str, name: str):
    path = workspace_root / "bin" / "ssot" / filename
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"{filename} is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_inbox(workspace_root: Path):
    return _load_engine(workspace_root, "scene-card-decision-inbox.py", "review_inbox")


def _load_approval(workspace_root: Path):
    return _load_engine(workspace_root, "scene-card-approval-flow.py", "review_approval")


def _load_connector(workspace_root: Path):
    return _load_engine(workspace_root, "scene-card-connector.py", "review_connector")


# ── Time estimation ──

# Estimated time saved per intent by priority
_TIME_PER_INTENT = {
    "P0": 15,  # 15 minutes for urgent items
    "P1": 10,  # 10 minutes for important items
    "P2": 5,  # 5 minutes for normal items
    "P3": 3,  # 3 minutes for low priority
}

# Accuracy: approved / (approved + rejected)
# False positive rate: rejected / total


def generate_weekly_review(workspace_root: Path, weeks: int = 1) -> dict[str, Any]:
    """Generate a weekly review report.

    Args:
        weeks: Number of weeks to look back (default 1)

    Returns:
        Dict with review statistics.
    """
    inbox = _load_inbox(workspace_root)
    approval = _load_approval(workspace_root)

    scenes = inbox.list_scenes(workspace_root)
    cutoff = datetime.now(UTC) - timedelta(weeks=weeks)

    # Collect intents within the review period
    total_intents = 0
    pending = 0
    approved = 0
    rejected = 0
    done = 0
    by_source: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    daily_counts: dict[str, int] = {}
    time_saved = 0

    for scene in scenes:
        for journey in scene.journeys:
            for intent in journey.intents:
                created = _parse_time(intent.created_at)
                if created and created < cutoff:
                    continue  # Skip intents outside the review window

                total_intents += 1
                by_source[intent.source] = by_source.get(intent.source, 0) + 1
                by_priority[intent.priority] = by_priority.get(intent.priority, 0) + 1

                # Daily trend
                day = intent.created_at[:10] if intent.created_at else "unknown"
                daily_counts[day] = daily_counts.get(day, 0) + 1

                if intent.status == "pending":
                    pending += 1
                elif intent.status in ("approved", "task_created"):
                    approved += 1
                    time_saved += _TIME_PER_INTENT.get(intent.priority, 5)
                elif intent.status == "rejected":
                    rejected += 1
                elif intent.status == "done":
                    done += 1

    # Calculate accuracy
    total_decided = approved + rejected
    accuracy = approved / total_decided if total_decided > 0 else 0.0
    false_positive_rate = rejected / total_intents if total_intents > 0 else 0.0

    # Get connector stats
    try:
        connector = _load_connector(workspace_root)
        connector_stats = connector.get_connector_stats(workspace_root)
    except Exception:
        connector_stats = {"total_runs": 0, "total_imported": 0}

    # Get approval history
    try:
        history = approval.get_approval_history(workspace_root, limit=50)
    except Exception:
        history = []

    return {
        "report_period": f"last_{weeks}_weeks",
        "generated_at": _now_iso(),
        "summary": {
            "total_intents": total_intents,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "done": done,
            "accuracy": round(accuracy, 3),
            "false_positive_rate": round(false_positive_rate, 3),
            "time_saved_minutes": time_saved,
            "time_saved_hours": round(time_saved / 60, 1),
        },
        "distribution": {
            "by_source": by_source,
            "by_priority": by_priority,
        },
        "daily_trend": dict(sorted(daily_counts.items())),
        "connector_activity": connector_stats,
        "recent_approvals": [
            {
                "intent_id": h["intent_id"],
                "decision": h["decision"],
                "reviewer": h["reviewer"],
                "created_at": h["created_at"],
            }
            for h in history[:10]
        ],
    }


def _parse_time(ts: str) -> datetime | None:
    """Parse ISO timestamp string to datetime."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def validate_scene_card(workspace_root: Path, scene_id: str) -> dict[str, Any]:
    """Validate a scene card's field completeness."""
    scene_file = workspace_root / ".omo" / "_truth" / "scenarios" / f"{scene_id}.yaml"
    if not scene_file.exists():
        return {"valid": False, "error": f"Scene card not found: {scene_file}"}

    data = yaml.safe_load(scene_file.read_text())

    required = [
        "scene_id", "journey_id", "goal", "trigger",
        "input_contract", "result_contract", "outcome_metric",
    ]
    shadow_required = required  # shadow only needs core fields
    assisted_required = required + ["owner", "failure_cost", "data_classification", "rollback_plan"]

    lifecycle = data.get("lifecycle", "draft")
    required_fields = assisted_required if lifecycle in ("assisted", "supervised", "routine") else shadow_required

    missing = [f for f in required_fields if not data.get(f)]
    return {
        "valid": len(missing) == 0,
        "scene_id": scene_id,
        "lifecycle": lifecycle,
        "missing_fields": missing,
        "field_count": len(required_fields) - len(missing),
        "total_fields": len(required_fields),
    }


def promote_scene_card(workspace_root: Path, scene_id: str, target_lifecycle: str) -> dict[str, Any]:
    """Promote a scene card to a higher lifecycle."""
    valid_order = ["draft", "shadow", "assisted", "supervised", "routine"]
    if target_lifecycle not in valid_order:
        return {"success": False, "error": f"Invalid lifecycle: {target_lifecycle}"}

    scene_file = workspace_root / ".omo" / "_truth" / "scenarios" / f"{scene_id}.yaml"
    if not scene_file.exists():
        return {"success": False, "error": f"Scene card not found: {scene_file}"}

    data = yaml.safe_load(scene_file.read_text())
    current = data.get("lifecycle", "draft")

    if valid_order.index(target_lifecycle) <= valid_order.index(current):
        return {"success": False, "error": f"Cannot promote from {current} to {target_lifecycle}"}

    # Validate before promotion
    validation = validate_scene_card(workspace_root, scene_id)
    if not validation["valid"]:
        return {"success": False, "error": f"Validation failed: {validation['missing_fields']}"}

    data["lifecycle"] = target_lifecycle
    scene_file.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
    return {"success": True, "scene_id": scene_id, "lifecycle": target_lifecycle}


def status_scene_card(workspace_root: Path, scene_id: str) -> dict[str, Any]:
    """Get scene card status."""
    scene_file = workspace_root / ".omo" / "_truth" / "scenarios" / f"{scene_id}.yaml"
    if not scene_file.exists():
        return {"error": f"Scene card not found: {scene_file}"}

    data = yaml.safe_load(scene_file.read_text())
    return {
        "scene_id": data.get("scene_id", scene_id),
        "lifecycle": data.get("lifecycle", "draft"),
        "journey_id": data.get("journey_id"),
        "goal": data.get("goal"),
        "owner": data.get("owner", "unspecified"),
    }


def generate_pilot_report(workspace_root: Path) -> dict[str, Any]:
    """Generate the 4-week pilot summary report.

    This is the M4 final deliverable: a comprehensive summary
    of the entire 4-week pilot.
    """
    inbox = _load_inbox(workspace_root)
    scenes = inbox.list_scenes(workspace_root)

    # Aggregate all data
    all_intents = []
    for scene in scenes:
        for journey in scene.journeys:
            for intent in journey.intents:
                all_intents.append(
                    {
                        "scene_name": scene.name,
                        "journey_name": journey.name,
                        "intent_id": intent.id,
                        "source": intent.source,
                        "status": intent.status,
                        "priority": intent.priority,
                        "created_at": intent.created_at,
                        "processed_at": intent.processed_at,
                        "task_id": intent.task_id,
                    }
                )

    # Weekly breakdown
    weekly_reviews = []
    for w in range(4):
        try:
            review = generate_weekly_review(workspace_root, weeks=w + 1)
            weekly_reviews.append(review)
        except Exception:
            pass

    return {
        "pilot_name": "Phase 1.5 场景验证试点",
        "pilot_duration": "4 周 (2026-08-07 ~ 2026-09-03)",
        "generated_at": _now_iso(),
        "scenes": [
            {
                "id": s.id,
                "name": s.name,
                "status": s.status,
                "priority": s.priority,
                "journey_count": len(s.journeys),
                "intent_count": sum(len(j.intents) for j in s.journeys),
            }
            for s in scenes
        ],
        "total_intents": len(all_intents),
        "intents": sorted(all_intents, key=lambda x: x["created_at"], reverse=True)[:100],
        "weekly_reviews": weekly_reviews,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Scene Card Review — 场景卡生命周期管理")
    sub = parser.add_subparsers(dest="command")

    # validate
    p_validate = sub.add_parser("validate", help="校验场景卡字段完整度")
    p_validate.add_argument("scene_id", help="场景 ID")

    # promote
    p_promote = sub.add_parser("promote", help="升级场景卡生命周期")
    p_promote.add_argument("scene_id", help="场景 ID")
    p_promote.add_argument("--to", required=True, choices=["draft", "shadow", "assisted", "supervised", "routine"])

    # status
    p_status = sub.add_parser("status", help="查看场景卡状态")
    p_status.add_argument("scene_id", help="场景 ID")

    # weekly-review
    p_weekly = sub.add_parser("weekly-review", help="生成周统计报告")
    p_weekly.add_argument("--weeks", type=int, default=1)

    # pilot-report
    sub.add_parser("pilot-report", help="生成 4 周试点总结")

    args = parser.parse_args()
    import sys
    ws = Path.cwd()

    if args.command == "validate":
        result = validate_scene_card(ws, args.scene_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["valid"] else 1)

    elif args.command == "promote":
        result = promote_scene_card(ws, args.scene_id, args.to)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["success"] else 1)

    elif args.command == "status":
        result = status_scene_card(ws, args.scene_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "weekly-review":
        result = generate_weekly_review(ws, weeks=args.weeks)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.command == "pilot-report":
        result = generate_pilot_report(ws)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
