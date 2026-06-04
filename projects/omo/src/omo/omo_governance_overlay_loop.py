from __future__ import annotations

from pathlib import Path

import yaml

try:
    from .omo_governance_overlay import build_governance_overlay_status
    from .omo_governance_overlay_targets import evaluate_governance_overlay_planned_target
except ModuleNotFoundError:
    from .omo_governance_overlay import build_governance_overlay_status
    from .omo_governance_overlay_targets import evaluate_governance_overlay_planned_target


def _load_yaml_required(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path.as_posix())
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _roadmap_item(roadmap: dict, roadmap_item_id: str) -> dict:
    for item in roadmap.get("items", []):
        if item.get("id") == roadmap_item_id:
            return item
    raise KeyError(f"unknown roadmap item: {roadmap_item_id}")


def _roadmap_item_sort_key(item: dict[str, object]) -> tuple[int, str]:
    return (0 if item["priority"] == "P0" else 1, str(item["id"]))


def _target_state_summary(target_states: list[dict[str, object]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for target in target_states:
        state = str(target["state"])
        summary[state] = summary.get(state, 0) + 1
    return summary


def _target_action(root: Path, target_ref: str) -> dict[str, object]:
    return evaluate_governance_overlay_planned_target(root, target_ref)


def plan_governance_overlay_cycle(root: Path, *, omo_dir: str | Path = ".omo", actor: str, now: str) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    roadmap = _load_yaml_required(root / omo_ref / "_truth" / "governance-overlay" / "roadmap.yaml")
    status = build_governance_overlay_status(root, omo_dir=omo_dir, now=now)["yaml"]
    run = {
        "run_id": f"governance-overlay-{now.replace(':', '-')}",
        "overlay_id": status["overlay_id"],
        "actor": actor,
        "started_at": now,
        "completed_at": now,
        "mode": "advance_pending",
        "next_action_before_run": status["next_action"],
        "roadmap_item_id": None,
        "summary": "idle",
        "target_results": [],
        "target_state_summary": {},
        "control_updates": {},
    }
    active_item = status.get("active_roadmap_item")
    if active_item:
        pending_items = [
            item
            for item in sorted(roadmap.get("items", []), key=_roadmap_item_sort_key)
            if item.get("status") == "pending" and item.get("id") != active_item["id"]
        ]
        run["mode"] = "continue_active"
        run["roadmap_item_id"] = str(active_item["id"])
        run["target_results"] = list(status.get("active_target_states", []))
        run["target_state_summary"] = _target_state_summary(run["target_results"])
        run["control_updates"] = {
            "current_milestone": pending_items[0]["id"] if pending_items else None,
            "next_milestone": pending_items[1]["id"] if len(pending_items) > 1 else None,
        }
        states = [target["state"] for target in run["target_results"]]
        terminal_blockers = {"planned_blocked", "unsupported_target_ref", "missing_target_ref"}
        if states and all(state == "done" for state in states):
            run["summary"] = "close_ready"
        elif states and all(state in terminal_blockers for state in states):
            run["summary"] = "block_ready"
        else:
            run["summary"] = "in_progress"
        return {"run": run, "roadmap": roadmap, "mutated": False}

    if not status["autopilot_candidates"]:
        return {"run": run, "roadmap": roadmap, "mutated": False}

    roadmap_item_id = str(status["autopilot_candidates"][0]["id"])
    item = _roadmap_item(roadmap, roadmap_item_id)
    run["roadmap_item_id"] = roadmap_item_id
    run["target_results"] = [_target_action(root, str(ref)) for ref in item.get("target_refs", [])]
    if run["target_results"] and all(result["result"] == "unsupported_target_ref" for result in run["target_results"]):
        run["summary"] = "blocked"
    else:
        run["summary"] = "advanced"
    return {"run": run, "roadmap": roadmap, "mutated": False}
