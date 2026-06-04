#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

try:
    from scripts.cost_track_org import cost_summary_by_org
    from .omo_io import write_text_atomic, write_yaml_atomic
    from .omo_redaction import redact_sensitive_text
    from .omo_task_schema import validate_task_file
except ModuleNotFoundError:
    from cost_track_org import cost_summary_by_org
    from .omo_io import write_text_atomic, write_yaml_atomic
    from .omo_redaction import redact_sensitive_text
    from .omo_task_schema import validate_task_file


def _workspace_root(root: Path) -> Path:
    return root.resolve()


def _omo_root(root: Path) -> Path:
    workspace_root = _workspace_root(root)
    candidate = workspace_root / ".omo"
    return candidate if candidate.exists() else workspace_root


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_slug(now: str | None = None) -> str:
    instant = _parse_iso8601(now) or datetime.now(timezone.utc)
    return instant.strftime("%Y%m%d-%H%M%S")


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _relative_ref(path: Path, root: Path) -> str:
    return path.relative_to(_workspace_root(root)).as_posix()


def _phase_and_wave(root: Path) -> tuple[int | None, int | None]:
    omo_root = _omo_root(root)
    state = _load_yaml(omo_root / "state" / "system.yaml") if (omo_root / "state" / "system.yaml").exists() else {}
    goals = _load_yaml(omo_root / "goals" / "current.yaml") if (omo_root / "goals" / "current.yaml").exists() else {}
    phase = goals.get("phase", state.get("current_phase"))
    wave = goals.get("current_wave", state.get("current_wave"))
    return phase, wave


def _append_unique(existing: list[str] | None, value: str) -> list[str]:
    result = list(existing or [])
    if value not in result:
        result.append(value)
    return result


def _find_latest_summary(omo_root: Path) -> Path | None:
    summary_dir = omo_root / "summaries"
    if not summary_dir.exists():
        return None
    summaries = sorted(summary_dir.glob("*.md"), key=lambda path: (path.stat().st_mtime, path.name))
    return summaries[-1] if summaries else None


def _find_task_file(root: Path, task_id: str) -> Path:
    omo_root = _omo_root(root)
    for group in ("active", "blocked", "done"):
        group_dir = omo_root / "tasks" / group
        if not group_dir.exists():
            continue
        for task_file in sorted(group_dir.glob("*.yaml")):
            task = _load_yaml(task_file)
            if task.get("id") == task_id:
                return task_file
    raise FileNotFoundError(f"Task not found: {task_id}")


def build_session_bootstrap(root: Path) -> dict[str, object]:
    workspace_root = _workspace_root(root)
    omo_root = _omo_root(root)
    state = _load_yaml(omo_root / "state" / "system.yaml") if (omo_root / "state" / "system.yaml").exists() else {}
    goals = _load_yaml(omo_root / "goals" / "current.yaml") if (omo_root / "goals" / "current.yaml").exists() else {}
    active_dir = omo_root / "tasks" / "active"
    active_task_ids: list[str] = []
    if active_dir.exists():
        for task_file in sorted(active_dir.glob("*.yaml")):
            task = _load_yaml(task_file)
            if task.get("id"):
                active_task_ids.append(task["id"])
    latest_summary = _find_latest_summary(omo_root)
    return {
        "phase": goals.get("phase", state.get("current_phase")),
        "wave": goals.get("current_wave", state.get("current_wave")),
        "phase_status": state.get("phase_status", goals.get("status")),
        "next_milestone": state.get("next_milestone"),
        "active_task_ids": active_task_ids,
        "divergence_flags": state.get("divergence_flags", []),
        "goal_ids": [goal.get("id") for goal in goals.get("goals", []) if goal.get("id")],
        "latest_summary_ref": _relative_ref(latest_summary, workspace_root) if latest_summary else None,
    }


def bridge_request_to_task(
    root: Path,
    task_id: str,
    title: str,
    request_text: str,
    source_docs: list[str] | None = None,
    now: str | None = None,
) -> dict[str, str]:
    workspace_root = _workspace_root(root)
    omo_root = _omo_root(root)
    phase, wave = _phase_and_wave(workspace_root)
    created_at = now or _utc_now()
    task_path = omo_root / "tasks" / "blocked" / f"{task_id.lower()}.yaml"
    task = {
        "id": task_id,
        "title": title,
        "phase": phase,
        "milestone": f"W{wave}" if wave else None,
        "status": "blocked",
        "assigned_to": None,
        "dispatch_id": None,
        "run_ref": None,
        "approval_ref": None,
        "review_ref": None,
        "knowledge_refs": [],
        "handoff_refs": [],
        "source_docs": source_docs or [],
        "deliverables": ["schema-valid governed task packet created from complex request"],
        "risk_level": "L1",
        "allowed_operation_level": "L1",
        "human_approval_required": False,
        "entry_gate": ["triage request and ratify packet into active queue"],
        "evidence_required": ["complex request bridged into governed task packet"],
        "created_at": created_at,
        "request_excerpt": redact_sensitive_text(request_text),
    }
    write_yaml_atomic(task_path, task)
    errors = validate_task_file(task_path)
    if errors:
        raise ValueError(f"Generated task packet is invalid: {errors}")
    return {
        "classification": "complex_task",
        "task_id": task_id,
        "task_ref": _relative_ref(task_path, workspace_root),
    }


def record_confirmation_evidence(root: Path, task_id: str, message: str, now: str | None = None) -> dict[str, str]:
    workspace_root = _workspace_root(root)
    omo_root = _omo_root(root)
    task_path = _find_task_file(workspace_root, task_id)
    task = _load_yaml(task_path)
    confirmed_at = now or _utc_now()
    evidence_path = (
        omo_root
        / "_delivery"
        / "task-center"
        / "consensus"
        / f"{task_id.lower()}-{_timestamp_slug(confirmed_at)}.yaml"
    )
    evidence = {
        "task_id": task_id,
        "classification": "positive_confirmation",
        "message": redact_sensitive_text(message),
        "confirmed_at": confirmed_at,
        "task_status": task.get("status"),
    }
    write_yaml_atomic(evidence_path, evidence)
    evidence_ref = _relative_ref(evidence_path, workspace_root)
    task["handoff_refs"] = _append_unique(task.get("handoff_refs"), evidence_ref)
    write_yaml_atomic(task_path, task)
    return {"task_id": task_id, "evidence_ref": evidence_ref}


def write_resource_accounting_report(root: Path, now: str | None = None, days: int = 7) -> dict[str, str]:
    workspace_root = _workspace_root(root)
    omo_root = _omo_root(root)
    state_path = omo_root / "state" / "system.yaml"
    state = _load_yaml(state_path) if state_path.exists() else {}
    runs_dir = omo_root / "workers" / "runs"
    dispatch_files = sorted(runs_dir.glob("*-dispatch.yaml")) if runs_dir.exists() else []
    dispatches = [_load_yaml(path) for path in dispatch_files]
    worker_counts = Counter(dispatch.get("worker_id", "unknown") for dispatch in dispatches)
    cost_by_org = cost_summary_by_org(days=days)
    registry = {
        "generated_at": now or _utc_now(),
        "current_phase": state.get("current_phase"),
        "current_wave": state.get("current_wave"),
        "task_counts": {
            "active": state.get("active_tasks", 0),
            "blocked": state.get("blocked_tasks", 0),
            "completed": state.get("completed_tasks", 0),
        },
        "dispatches": {
            "total": len(dispatches),
            "workers": dict(worker_counts),
        },
        "cost_by_org": cost_by_org,
    }
    registry_path = omo_root / "_truth" / "task-center" / "usage-accounting.yaml"
    write_yaml_atomic(registry_path, registry)

    lines = [
        "# Phase 7 resource accounting",
        "",
        f"- generated_at: {registry['generated_at']}",
        f"- current_phase: {registry['current_phase']}",
        f"- current_wave: {registry['current_wave']}",
        f"- active_tasks: {registry['task_counts']['active']}",
        f"- blocked_tasks: {registry['task_counts']['blocked']}",
        f"- completed_tasks: {registry['task_counts']['completed']}",
        f"- dispatch_total: {registry['dispatches']['total']}",
        "",
        "## Cost by org",
    ]
    if not cost_by_org:
        lines.append("- no cost data available")
    else:
        for item in cost_by_org:
            lines.append(
                f"- {item['org']}: calls={item['calls']} tokens={item['tokens']} cost=${item['cost']:.2f}"
            )
    summary_path = omo_root / "summaries" / "phase7-wave2-resource-accounting.md"
    write_text_atomic(summary_path, "\n".join(lines) + "\n")
    return {
        "registry_ref": _relative_ref(registry_path, workspace_root),
        "summary_ref": _relative_ref(summary_path, workspace_root),
    }


def write_freshness_report(root: Path, now: str | None = None) -> dict[str, str]:
    workspace_root = _workspace_root(root)
    omo_root = _omo_root(workspace_root)
    state_path = omo_root / "state" / "system.yaml"
    state = _load_yaml(state_path) if state_path.exists() else {}
    generated_at = _parse_iso8601(now) or datetime.now(timezone.utc)
    stale_items: list[str] = []
    updated_at = _parse_iso8601(state.get("updated_at"))
    if updated_at is None or (generated_at - updated_at).total_seconds() >= 3600:
        stale_items.append("state_update_stale")
    stale_items.extend(flag for flag in state.get("divergence_flags", []) if flag not in stale_items)
    freshness_score = max(0, 100 - (30 if "state_update_stale" in stale_items else 0) - 20 * (len(stale_items) - ("state_update_stale" in stale_items)))
    report = {
        "generated_at": generated_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "current_phase": state.get("current_phase"),
        "current_wave": state.get("current_wave"),
        "stale_items": stale_items,
        "freshness_score": freshness_score,
        "recommended_actions": ["refresh state summary", "resolve or tolerate divergence"] if stale_items else ["no action required"],
    }
    report_path = omo_root / "_delivery" / "task-center" / "freshness" / "current.yaml"
    write_yaml_atomic(report_path, report)
    summary_lines = [
        "# Phase 7 freshness report",
        "",
        f"- generated_at: {report['generated_at']}",
        f"- current_phase: {report['current_phase']}",
        f"- current_wave: {report['current_wave']}",
        f"- freshness_score: {report['freshness_score']}",
        "",
        "## Stale items",
    ]
    if not stale_items:
        summary_lines.append("- none")
    else:
        summary_lines.extend(f"- {item}" for item in stale_items)
    summary_path = omo_root / "summaries" / "phase7-wave3-freshness-report.md"
    write_text_atomic(summary_path, "\n".join(summary_lines) + "\n")
    return {
        "report_ref": _relative_ref(report_path, workspace_root),
        "summary_ref": _relative_ref(summary_path, workspace_root),
    }


def evaluate_control_gate(
    root: Path,
    budget_limit_usd: float,
    warning_score: int = 80,
    critical_score: int = 50,
    now: str | None = None,
) -> dict[str, object]:
    workspace_root = _workspace_root(root)
    omo_root = _omo_root(workspace_root)
    generated_at = now or _utc_now()
    accounting_path = omo_root / "_truth" / "task-center" / "usage-accounting.yaml"
    freshness_path = omo_root / "_delivery" / "task-center" / "freshness" / "current.yaml"
    accounting = _load_yaml(accounting_path) if accounting_path.exists() else {}
    freshness = _load_yaml(freshness_path) if freshness_path.exists() else {}

    total_cost = sum(float(item.get("cost", 0) or 0) for item in accounting.get("cost_by_org", []))
    freshness_score = int(freshness.get("freshness_score", 100) or 100)
    stale_items = list(freshness.get("stale_items", []) or [])
    reasons: list[str] = []

    if total_cost > budget_limit_usd:
        decision = "block"
        reasons.append("budget_limit_exceeded")
    elif freshness_score <= critical_score:
        decision = "review"
        reasons.append("freshness_critical")
    elif freshness_score <= warning_score or stale_items:
        decision = "degrade"
        reasons.append("freshness_warning")
    else:
        decision = "allow"
        reasons.append("within_budget_and_fresh")

    artifact = {
        "generated_at": generated_at,
        "decision": decision,
        "reasons": reasons,
        "budget_limit_usd": budget_limit_usd,
        "total_cost_usd": round(total_cost, 4),
        "freshness_score": freshness_score,
        "stale_items": stale_items,
        "accounting_ref": _relative_ref(accounting_path, workspace_root) if accounting_path.exists() else None,
        "freshness_ref": _relative_ref(freshness_path, workspace_root) if freshness_path.exists() else None,
    }
    artifact_path = omo_root / "_delivery" / "task-center" / "control" / "current.yaml"
    write_yaml_atomic(artifact_path, artifact)
    artifact["decision_ref"] = _relative_ref(artifact_path, workspace_root)
    return artifact


def route_request_with_control_gate(
    root: Path,
    task_id: str,
    title: str,
    request_text: str,
    source_docs: list[str] | None = None,
    budget_limit_usd: float = 2.5,
    warning_score: int = 80,
    critical_score: int = 50,
    now: str | None = None,
) -> dict[str, str]:
    decision = evaluate_control_gate(
        root,
        budget_limit_usd=budget_limit_usd,
        warning_score=warning_score,
        critical_score=critical_score,
        now=now,
    )
    result = {
        "decision": str(decision["decision"]),
        "decision_ref": str(decision["decision_ref"]),
    }
    if decision["decision"] in {"allow", "degrade"}:
        task_result = bridge_request_to_task(
            root,
            task_id=task_id,
            title=title,
            request_text=request_text,
            source_docs=source_docs,
            now=now,
        )
        result["task_ref"] = task_result["task_ref"]
        result["task_id"] = task_result["task_id"]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(prog="omo-experience")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("bootstrap")

    bridge_parser = subparsers.add_parser("bridge")
    bridge_parser.add_argument("--task-id", required=True)
    bridge_parser.add_argument("--title", required=True)
    bridge_parser.add_argument("--request", required=True)
    bridge_parser.add_argument("--source-doc", action="append", default=[])
    bridge_parser.add_argument("--now")

    confirm_parser = subparsers.add_parser("confirm")
    confirm_parser.add_argument("task_id")
    confirm_parser.add_argument("--message", required=True)
    confirm_parser.add_argument("--now")

    accounting_parser = subparsers.add_parser("accounting")
    accounting_parser.add_argument("--now")
    accounting_parser.add_argument("--days", type=int, default=7)

    freshness_parser = subparsers.add_parser("freshness")
    freshness_parser.add_argument("--now")

    control_parser = subparsers.add_parser("control")
    control_parser.add_argument("--budget-limit", type=float, required=True)
    control_parser.add_argument("--warning-score", type=int, default=80)
    control_parser.add_argument("--critical-score", type=int, default=50)
    control_parser.add_argument("--now")

    route_parser = subparsers.add_parser("route")
    route_parser.add_argument("--task-id", required=True)
    route_parser.add_argument("--title", required=True)
    route_parser.add_argument("--request", required=True)
    route_parser.add_argument("--source-doc", action="append", default=[])
    route_parser.add_argument("--budget-limit", type=float, required=True)
    route_parser.add_argument("--warning-score", type=int, default=80)
    route_parser.add_argument("--critical-score", type=int, default=50)
    route_parser.add_argument("--now")

    args = parser.parse_args()
    root = Path.cwd()

    if args.command == "bootstrap":
        print(yaml.safe_dump(build_session_bootstrap(root), sort_keys=False))
        return 0
    if args.command == "bridge":
        print(
            yaml.safe_dump(
                bridge_request_to_task(
                    root,
                    task_id=args.task_id,
                    title=args.title,
                    request_text=args.request,
                    source_docs=args.source_doc,
                    now=args.now,
                ),
                sort_keys=False,
            )
        )
        return 0
    if args.command == "confirm":
        print(
            yaml.safe_dump(
                record_confirmation_evidence(root, task_id=args.task_id, message=args.message, now=args.now),
                sort_keys=False,
            )
        )
        return 0
    if args.command == "accounting":
        print(yaml.safe_dump(write_resource_accounting_report(root, now=args.now, days=args.days), sort_keys=False))
        return 0
    if args.command == "freshness":
        print(yaml.safe_dump(write_freshness_report(root, now=args.now), sort_keys=False))
        return 0
    if args.command == "control":
        print(
            yaml.safe_dump(
                evaluate_control_gate(
                    root,
                    budget_limit_usd=args.budget_limit,
                    warning_score=args.warning_score,
                    critical_score=args.critical_score,
                    now=args.now,
                ),
                sort_keys=False,
            )
        )
        return 0
    if args.command == "route":
        print(
            yaml.safe_dump(
                route_request_with_control_gate(
                    root,
                    task_id=args.task_id,
                    title=args.title,
                    request_text=args.request,
                    source_docs=args.source_doc,
                    budget_limit_usd=args.budget_limit,
                    warning_score=args.warning_score,
                    critical_score=args.critical_score,
                    now=args.now,
                ),
                sort_keys=False,
            )
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
