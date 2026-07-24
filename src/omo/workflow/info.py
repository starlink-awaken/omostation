from __future__ import annotations

import json
import sys
from typing import Any

from .core import (
    REGISTRY_PATH,
    WORKSPACE,
    adapter_rows,
    agent_rows,
    command_display,
    integration_rows,
    normalize_repo_path,
    path_matches,
    workflow_rows,
)
from .diagnostics import build_doctor_report, check_summary, health_summary
from .lint import lint_registry


def list_workflows(registry: dict[str, Any], as_json: bool) -> None:
    rows = workflow_rows(registry)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        print(f"{row['id']:<28} {row['title']} [{', '.join(row['lanes'])}]")


def list_agents(registry: dict[str, Any], as_json: bool) -> None:
    rows = agent_rows(registry)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        workflows = ", ".join(row["allowed_workflows"])
        lanes = ", ".join(row["can_write_lanes"])
        print(f"{row['id']:<20} workflows=[{workflows}] lanes=[{lanes}]")


def list_integrations(registry: dict[str, Any], as_json: bool) -> None:
    rows = integration_rows(registry)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        print(
            f"{row['name']:<14} {row['status']:<12} {row['authority']:<16} "
            f"owner={row['owner']} gate={row.get('gate_binding') or '-'}"
        )
        if row.get("ssot_rule"):
            print(f"  ssot: {row['ssot_rule']}")


def list_adapters(registry: dict[str, Any], as_json: bool) -> None:
    rows = adapter_rows(registry)
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        availability = "available" if row["available"] else "missing"
        command = row["command"] or row["skill"] or "-"
        print(
            f"{row['name']:<14} {row['status']:<16} {row['authority']:<16} "
            f"workflow={row['ingress_workflow']} command={command} {availability}"
        )
        if row.get("bridge"):
            print(f"  bridge: {row['bridge']}")
        if row.get("degrade_to"):
            print(f"  degrade_to: {row['degrade_to']}")
        if row.get("ssot_rule"):
            print(f"  ssot: {row['ssot_rule']}")


def handoff_markdown(payload: dict[str, Any]) -> str:
    plan = payload.get("plan", {})
    context = payload.get("context", {})
    lines = [
        f"# Agent Workflow Handoff: {payload.get('run_id')}",
        "",
        f"- workflow: `{payload.get('workflow_id')}`",
        f"- status: `{payload.get('status')}`",
        f"- actor: `{payload.get('actor')}`",
        f"- agent_profile: `{payload.get('agent_profile') or context.get('profile') or '-'}`",
        f"- objective: {payload.get('objective') or '(none)'}",
        f"- created_at: `{payload.get('created_at')}`",
        f"- updated_at: `{payload.get('updated_at')}`",
        f"- project: `{context.get('project') or '-'}`",
        f"- source_file: `{context.get('source_file') or '-'}`",
        "",
        "## Locks",
    ]
    locks = payload.get("locks") or []
    if locks:
        lines.extend(f"- `{lock}`" for lock in locks)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Resume",
            "",
            "```bash",
            f"uv run --with pyyaml python bin/agent-workflow.py resume {payload.get('run_id')}",
            "uv run --with pyyaml python bin/agent-workflow.py doctor",
            "```",
            "",
            "## Verification Plan",
        ]
    )
    for item in plan.get("phases", {}).get("verification", []):
        lines.append(
            f"- `{item.get('mode')}` {item.get('id')}: `{command_display(item.get('command', []))}`"
        )
    lines.extend(["", "## Evidence"])
    evidence = payload.get("evidence") or []
    if evidence:
        lines.extend(f"- {entry}" for entry in evidence)
    else:
        lines.append("- none yet")
    return "\n".join(lines)


def bootstrap_report(
    registry: dict[str, Any],
    include_health: bool,
    include_agcp_drift: bool = True,
) -> dict[str, Any]:
    errors, warnings = lint_registry(registry, include_agcp_drift)
    doctor_report = (
        build_doctor_report(registry, include_agcp_drift) if include_health else None
    )
    integrations = (
        doctor_report["integrations"]
        if isinstance(doctor_report, dict)
        else integration_rows(registry)
    )
    adapters = (
        doctor_report["adapters"]
        if isinstance(doctor_report, dict)
        else adapter_rows(registry)
    )
    ok = not errors and (doctor_report is None or bool(doctor_report["ok"]))
    return {
        "ok": ok,
        "registry": str(REGISTRY_PATH.relative_to(WORKSPACE)),
        "version": registry.get("version"),
        "ssot": registry.get("ssot", {}),
        "runner": registry.get("runner", {}),
        "lint": {"ok": not errors, "errors": errors, "warnings": warnings},
        "workflows": workflow_rows(registry),
        "agent_profiles": agent_rows(registry),
        "integrations": [
            {key: value for key, value in row.items() if key != "health"}
            for row in integrations
        ],
        "adapters": [
            {key: value for key, value in row.items() if key != "health"}
            for row in adapters
        ],
        "health": None
        if doctor_report is None
        else {
            "ok": doctor_report["ok"],
            "integrations": health_summary(doctor_report["integrations"]),
            "adapters": health_summary(doctor_report["adapters"]),
            "checks": check_summary(doctor_report["checks"]),
        },
        "next_commands": {
            "status": "uv run --with pyyaml python bin/agent-workflow.py status --json",
            "start": 'uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> --profile <agent-profile> --objective "<summary>"',
            "claim": "uv run --with pyyaml python bin/agent-workflow.py claim <run-id> --path <path>",
            "verify": "uv run --with pyyaml python bin/agent-workflow.py verify <run-id> --from-diff --execute",
            "closeout": "uv run --with pyyaml python bin/agent-workflow.py closeout <run-id>",
            "compliance": "uv run --with pyyaml python bin/agent-workflow.py compliance",
            "doctor": "uv run --with pyyaml python bin/agent-workflow.py doctor",
            "gate": "make gac-local-gate",
            "scoped_gate": "uv run --with pyyaml python bin/gac/gac-local-gate.py --scope files --file <path> --json",
        },
    }


def print_bootstrap_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"registry: {report['registry']}")
    print(f"lint: {'PASS' if report['lint']['ok'] else 'FAIL'}")
    for warning in report["lint"]["warnings"]:
        print(f"[WARN] {warning}")
    health = report.get("health")
    if isinstance(health, dict):
        print(f"health: {'PASS' if health['ok'] else 'FAIL'}")
    print("\nworkflows:")
    for row in report["workflows"]:
        print(f"  {row['id']:<28} {row['title']}")
    print("\nagent profiles:")
    for row in report["agent_profiles"]:
        print(
            f"  {row['id']:<20} workflows={len(row['allowed_workflows'])} lanes={','.join(row['can_write_lanes'])}"
        )
    print("\ninternal integrations:")
    for row in report["integrations"]:
        print(f"  {row['name']:<14} {row['authority']:<16} owner={row['owner']}")
    print("\nexternal adapters:")
    for row in report["adapters"]:
        availability = "available" if row["available"] else "missing"
        command = row["command"] or row["skill"] or "-"
        print(
            f"  {row['name']:<14} {row['authority']:<16} {availability} command={command}"
        )
    print("\nnext:")
    for command in report["next_commands"].values():
        print(f"  {command}")


def suggest_workflows(
    registry: dict[str, Any],
    files: list[str],
    profile: str = "",
) -> list[dict[str, Any]]:
    normalized = sorted({normalize_repo_path(item) for item in files})
    if not normalized:
        return []
    suggestions: list[dict[str, Any]] = []
    for workflow in registry.get("workflows") or []:
        if not isinstance(workflow, dict):
            continue
        surfaces = workflow.get("surfaces") or {}
        write_patterns = surfaces.get("write") if isinstance(surfaces, dict) else None
        if not isinstance(write_patterns, list) or not write_patterns:
            continue
        matched = [
            file
            for file in normalized
            if path_matches([str(p) for p in write_patterns], file)
        ]
        if not matched:
            continue
        score = round(len(matched) / len(normalized), 3)
        agents = workflow.get("agents") or {}
        roles = agents.get("roles") if isinstance(agents, dict) else []
        suggestions.append(
            {
                "workflow_id": str(workflow.get("id") or ""),
                "title": str(workflow.get("title") or ""),
                "score": score,
                "matched_files": matched,
                "total_files": len(normalized),
                "agents": [str(r) for r in roles if isinstance(r, str)],
                "allowed_lanes": [
                    str(item)
                    for item in (workflow.get("allowed_lanes") or [])
                    if isinstance(item, str)
                ],
                "profile_hint": _profile_hint(profile, roles),
            }
        )
    suggestions.sort(
        key=lambda item: (item["score"], item["workflow_id"]), reverse=True
    )
    return suggestions


def _profile_hint(profile: str, roles: list[object]) -> str:
    if not profile:
        return ""
    if any(str(role) == profile for role in roles):
        return "exact"
    return "allowed_via_governance_agent"


def suggest_command(
    registry: dict[str, Any], files: list[str], profile: str, as_json: bool
) -> int:
    suggestions = suggest_workflows(registry, files, profile)
    matched_files = {
        matched for suggestion in suggestions for matched in suggestion["matched_files"]
    }
    uncovered = [file for file in files if file not in matched_files]
    if as_json:
        json.dump(
            {
                "file_count": len(files),
                "profile": profile,
                "suggestion_count": len(suggestions),
                "suggestions": suggestions,
                "uncovered_files": uncovered,
            },
            sys.stdout,
            indent=2,
            ensure_ascii=False,
            sort_keys=False,
        )
        sys.stdout.write("\n")
        return 0
    if not suggestions:
        print(
            f"[INFO] no workflow matches {len(files)} file(s); use --workflow-id to override"
        )
        if uncovered:
            print(
                f"[WARN] {len(uncovered)} file(s) uncovered by any workflow.surfaces.write:"
            )
            for file in uncovered:
                print(f"  - {file}")
            print(
                "[HINT] consider extending an existing workflow's surfaces or registering a new one."
            )
        return 0
    print(
        f"[advisory] {len(suggestions)} workflow candidate(s) for {len(files)} file(s):"
    )
    for item in suggestions:
        marker = " <-- profile matches" if item["profile_hint"] == "exact" else ""
        print(
            f"  - {item['workflow_id']} (score={item['score']}, agents={','.join(item['agents']) or '-'}){marker}"
        )
        for matched in item["matched_files"]:
            print(f"      matched: {matched}")
    if uncovered:
        print(
            f"[WARN] {len(uncovered)} file(s) uncovered by any workflow.surfaces.write:"
        )
        for file in uncovered:
            print(f"  - {file}")
    return 0
