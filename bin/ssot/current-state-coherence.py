#!/usr/bin/env python3
"""Build and validate the read-only current-state-coherence/v1 projection.

The projection combines existing OMO state, current goals, task directories and
Scene Card candidates. It never mutates a truth surface and treats a waiting
workspace as a valid state rather than inventing an active business task.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA = "current-state-coherence/v1"
ACTIVE_GOAL_STATUSES = frozenset({"active", "in_progress"})
_SCENE_CANDIDATES_PATH = Path(__file__).with_name("scene-card-candidates.py")


class CoherenceInputError(ValueError):
    """Raised when a required SSOT input is missing or malformed."""


def _load_yaml_documents(path: Path) -> list[dict[str, Any]]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment error
        raise CoherenceInputError("pyyaml is required") from exc
    if not path.is_file():
        raise CoherenceInputError(f"missing input: {path}")
    try:
        documents = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError) as exc:
        raise CoherenceInputError(f"cannot read YAML: {path}") from exc
    return [document for document in documents if isinstance(document, dict)]


def _merged_yaml(path: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for document in _load_yaml_documents(path):
        merged.update(document)
    return merged


def _direct_yaml_count(path: Path) -> int:
    return len(list(path.glob("*.yaml"))) if path.is_dir() else 0


def _task_counts(omo_dir: Path) -> dict[str, int]:
    task_dir = omo_dir / "tasks"
    done = _direct_yaml_count(task_dir / "done")
    # Historical completed tasks are archived by the OMO state broker and are
    # still part of the completed count exposed by system.yaml.
    done += _direct_yaml_count(task_dir / "archived" / "done")
    return {
        "active": _direct_yaml_count(task_dir / "active"),
        "planned": _direct_yaml_count(task_dir / "planned"),
        "blocked": _direct_yaml_count(task_dir / "blocked"),
        "done": done,
    }


def _goal_inventory(goals: dict[str, Any]) -> dict[str, Any]:
    items = goals.get("goals")
    if not isinstance(items, list):
        raise CoherenceInputError("goals.current.yaml goals must be a list")
    active: list[str] = []
    gated: list[str] = []
    monitoring: list[str] = []
    stale_completed_active: list[str] = []
    historical = 0
    active_task_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        goal_id = str(item.get("id") or "").strip()
        status = str(item.get("status") or "").strip()
        if status in ACTIVE_GOAL_STATUSES:
            progress = item.get("progress")
            if isinstance(progress, (int, float)) and progress >= 100:
                if item.get("quarterly_targets"):
                    if goal_id:
                        monitoring.append(goal_id)
                else:
                    if goal_id:
                        stale_completed_active.append(goal_id)
                    historical += 1
                continue
            if goal_id:
                active.append(goal_id)
            task_ids = item.get("tasks") or []
            if isinstance(task_ids, list):
                active_task_ids.update(str(task_id) for task_id in task_ids if task_id)
        elif status == "gated":
            if goal_id:
                gated.append(goal_id)
        elif status in {"done", "completed", "archived", "closed"}:
            historical += 1
    return {
        "active_goal_ids": sorted(active),
        "gated_goal_ids": sorted(gated),
        "monitoring_goal_ids": sorted(monitoring),
        "stale_completed_active_goal_ids": sorted(stale_completed_active),
        "historical_goal_count": historical,
        "active_goal_task_ids": sorted(active_task_ids),
        "declared_goal_count": len(items),
    }


def _scene_inventory(root: Path) -> dict[str, Any]:
    """Reuse the candidate collector so the gate has one candidate definition."""
    spec = importlib.util.spec_from_file_location("scene_card_candidates", _SCENE_CANDIDATES_PATH)
    if spec is None or spec.loader is None:
        raise CoherenceInputError("scene-card candidate collector cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    candidates = module.collect_candidates(root)["candidates"]

    cards: list[dict[str, Any]] = []
    cards_dir = root / "docs" / "scene-cards"
    for path in sorted(cards_dir.glob("*.yaml")) if cards_dir.is_dir() else []:
        documents = _load_yaml_documents(path)
        body = documents[-1] if documents else {}
        if isinstance(body, dict):
            cards.append({"path": path.relative_to(root).as_posix(), **body})

    active_cards = [
        card for card in cards if card.get("activation") in {"active", "admitted"} or card.get("lifecycle") == "active"
    ]
    proposal_cards = [
        card for card in cards if card.get("activation") == "forbidden" or card.get("lifecycle") == "proposal_only"
    ]
    activation_allowed = bool(active_cards)
    return {
        "status": "active" if activation_allowed else "candidate_only",
        "activation_allowed": activation_allowed,
        "candidate_count": len(candidates),
        "proposal_only_card_count": len(proposal_cards),
        "active_card_count": len(active_cards),
        "candidate_ids": sorted(str(item.get("candidate_id")) for item in candidates),
        "proposal_only_card_refs": [str(card["path"]) for card in proposal_cards],
        "blockers": [] if activation_allowed else ["no_active_scene_card"],
    }


def _stored_count_mismatches(state: dict[str, Any], counts: dict[str, int]) -> list[str]:
    expected = {
        "active_tasks": counts["active"],
        "planned_tasks": counts["planned"],
        "blocked_tasks": counts["blocked"],
        "completed_tasks": counts["done"],
        "total_tasks": counts["active"] + counts["planned"] + counts["blocked"] + counts["done"],
    }
    mismatches: list[str] = []
    for field, value in expected.items():
        stored = state.get(field)
        if stored is not None and stored != value:
            mismatches.append(f"{field}_mismatch:expected={value}:state={stored}")
    return mismatches


def build_report(root: Path) -> dict[str, Any]:
    root = root.resolve()
    omo_dir = root / ".omo"
    state_path = omo_dir / "state" / "system.yaml"
    goals_path = omo_dir / "goals" / "current.yaml"
    state = _merged_yaml(state_path)
    goals = _merged_yaml(goals_path)
    goal_inventory = _goal_inventory(goals)
    counts = _task_counts(omo_dir)

    state_phase = state.get("current_phase")
    goal_phase = goals.get("phase")
    state_wave = state.get("current_wave")
    goal_wave = goals.get("current_wave")
    execution_mode = str(goals.get("execution_mode") or "").strip()
    computed_flags: list[str] = []
    if state_phase != goal_phase:
        computed_flags.append(f"phase_mismatch:goals={goal_phase}:state={state_phase}")
    if state_wave != goal_wave:
        computed_flags.append(f"wave_mismatch:goals={goal_wave}:state={state_wave}")
    if counts["active"] == 0 and goal_inventory["active_goal_ids"]:
        computed_flags.append("active_goals_without_active_tasks")
    if counts["active"] > 0 and execution_mode == "waiting-for-scenario/next-bet":
        computed_flags.append("execution_mode_mismatch:active_tasks_present")
    if (
        counts["active"] == 0
        and not goal_inventory["active_goal_ids"]
        and execution_mode != "waiting-for-scenario/next-bet"
    ):
        computed_flags.append("execution_mode_mismatch:expected=waiting-for-scenario/next-bet")
    computed_flags.extend(_stored_count_mismatches(state, counts))

    stored_flags = state.get("divergence_flags") or []
    errors = list(computed_flags)
    warnings: list[str] = []
    if not computed_flags and stored_flags:
        warnings.append("stale_divergence_flags")
    elif computed_flags and stored_flags != computed_flags:
        warnings.append("divergence_flags_snapshot_mismatch")

    stale_active = goal_inventory["stale_completed_active_goal_ids"]
    warnings.extend(f"goal_status_stale_completed:{goal_id}" for goal_id in stale_active)

    scene = _scene_inventory(root)
    waiting = counts["active"] == 0 and not goal_inventory["active_goal_ids"]
    phase_state = "waiting_for_scenario" if waiting else "active"
    if errors:
        status = "error"
    elif waiting:
        status = "waiting_for_scenario"
    else:
        status = "active"

    return {
        "schema": SCHEMA,
        "ok": not errors,
        "status": status,
        "source_refs": {
            "system": ".omo/state/system.yaml",
            "goals": ".omo/goals/current.yaml",
            "tasks": ".omo/tasks/",
            "scene_candidates": "docs/scene-card-candidate-seeds.yaml + .omo/_truth/contracts/",
            "scene_cards": "docs/scene-cards/",
        },
        "phase": {
            "state": state_phase,
            "goals": goal_phase,
            "wave_state": state_wave,
            "wave_goals": goal_wave,
            "phase_status": state.get("phase_status"),
            "derived_state": phase_state,
            "aligned": state_phase == goal_phase and state_wave == goal_wave,
        },
        "execution": {
            "mode": execution_mode,
            "counts": counts,
            "stored_counts": {
                field: state.get(field)
                for field in (
                    "active_tasks",
                    "planned_tasks",
                    "blocked_tasks",
                    "completed_tasks",
                    "total_tasks",
                )
            },
            "active_goal_ids": goal_inventory["active_goal_ids"],
            "gated_goal_ids": goal_inventory["gated_goal_ids"],
            "monitoring_goal_ids": goal_inventory["monitoring_goal_ids"],
            "stale_completed_active_goal_ids": stale_active,
            "active_goal_task_ids": goal_inventory["active_goal_task_ids"],
            "historical_goal_count": goal_inventory["historical_goal_count"],
            "declared_goal_count": goal_inventory["declared_goal_count"],
        },
        "scene_activation": scene,
        "divergence": {
            "computed_flags": computed_flags,
            "stored_flags": stored_flags,
        },
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true", help="emit the complete projection")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.root)
    except CoherenceInputError as exc:
        print(f"current-state-coherence: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            "current-state-coherence: "
            f"{report['status']} phase={report['phase']['state']} "
            f"wave={report['phase']['wave_state']} "
            f"active={report['execution']['counts']['active']} "
            f"planned={report['execution']['counts']['planned']} "
            f"blocked={report['execution']['counts']['blocked']} "
            f"scene_activation={report['scene_activation']['status']}"
        )
        for message in report["errors"]:
            print(f"ERROR: {message}", file=sys.stderr)
        for message in report["warnings"]:
            print(f"WARNING: {message}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
