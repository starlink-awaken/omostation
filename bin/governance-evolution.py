#!/usr/bin/env python3
"""Validate and inspect the systemic governance evolution roadmap."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY_PATH = WORKSPACE / ".omo/_truth/registry/governance-evolution-roadmap.yaml"
AGORA_BOS_REGISTRY_PATH = WORKSPACE / "projects/agora/etc/bos-services.yaml"
COCKPIT_CLI_PATH = WORKSPACE / "projects/cockpit/src/cockpit/cli.py"
COCKPIT_GOVERNANCE_COMMAND_PATH = WORKSPACE / "projects/cockpit/src/cockpit/commands/governance.py"
GOVERNANCE_EVOLUTION_BOS_PREFIX = "bos://governance/evolution/"
VALID_INITIATIVE_STATUS = {"planned", "in_progress", "active", "done", "blocked"}
PACKAGE_ORDER = [
    "governance-control-plane",
    "governance-truth-and-standards",
    "mof-model-registry",
    "governance-history-evidence",
    "governance-task-lifecycle",
    "governance-audit-report",
    "strategy-ingress-artifact",
    "governance-docs",
    "project-entry-docs",
    "workspace-config",
    "protocol-registry",
    "archived-artifact",
    "submodule-pointer",
    "runtime-or-control-output",
    "data-output",
    "unknown",
]
RELEASE_REVIEW_PACKAGES = {
    "governance-task-lifecycle": {
        "message": "review OMO task lifecycle mutations before release",
        "owner": "governance-team",
        "workflow": "governance-state-mutation",
        "recommended_action": "Confirm task lifecycle changes were brokered and should ship.",
    },
    "governance-audit-report": {
        "message": "review root governance audit reports before release",
        "owner": "governance-team",
        "workflow": "project-doc-change",
        "recommended_action": "Move audit evidence to the governed knowledge plane or explicitly include it.",
    },
    "strategy-ingress-artifact": {
        "message": "review C2G ingress lifecycle before release",
        "owner": "strategy-team",
        "workflow": "c2g-spec-ingress",
        "recommended_action": "Confirm strategy ingress artifacts are materialized or intentionally retained.",
    },
    "archived-artifact": {
        "message": "review archive deletion or migration intent before release",
        "owner": "governance-team",
        "workflow": "project-doc-change",
        "recommended_action": "Confirm archive mutations are intentional historical cleanup.",
    },
    "submodule-pointer": {
        "message": "review child repository diffs and commit boundaries before release",
        "owner": "release-team",
        "workflow": "submodule-pointer-close",
        "recommended_action": "Close child repository changes before updating or releasing root pointers.",
    },
    "workspace-config": {
        "message": "review workspace configuration and CI workflow changes before release",
        "owner": "governance-team",
        "workflow": "project-code-change",
        "recommended_action": "Confirm workspace config and CI workflow changes are intentional and covered by gates.",
    },
    "runtime-or-control-output": {
        "message": "exclude or explicitly attach control/evidence outputs before release",
        "owner": "governance-team",
        "workflow": "observer-audit",
        "recommended_action": "Exclude runtime/control output unless it is deliberate release evidence.",
    },
    "data-output": {
        "message": "exclude user/runtime data unless the release explicitly requires it",
        "owner": "data-owner",
        "workflow": "observer-audit",
        "recommended_action": "Exclude user or runtime data from release packages by default.",
    },
}
RELEASE_REVIEW_WORKFLOW_PROFILES = {
    "c2g-spec-ingress": "c2g-agent",
    "governance-state-mutation": "governance-agent",
    "observer-audit": "observer-agent",
    "project-code-change": "governance-agent",
    "project-doc-change": "docs-agent",
    "submodule-pointer-close": "release-agent",
}
ALLOWED_RELEASE_DECISIONS = ("include", "exclude", "defer")


class RoadmapError(RuntimeError):
    """Raised when the governance evolution roadmap is invalid."""


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE))
    except ValueError:
        return str(path)


def load_roadmap(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        raise RoadmapError(f"roadmap registry not found: {display_path(path)}")
    documents = [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]
    for document in documents:
        if isinstance(document, dict) and "initiatives" in document:
            return document
    raise RoadmapError(f"roadmap registry has no initiatives document: {display_path(path)}")


def load_yaml_document_with(path: Path, key: str) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing file: {display_path(path)}"
    try:
        documents = [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]
    except yaml.YAMLError as exc:
        return None, f"invalid YAML: {display_path(path)} ({exc})"
    for document in documents:
        if isinstance(document, dict) and key in document:
            return document, None
    return None, f"{display_path(path)} has no YAML document with key '{key}'"


def agora_governance_evolution_routes() -> tuple[set[str], list[str]]:
    document, error = load_yaml_document_with(AGORA_BOS_REGISTRY_PATH, "services")
    if error:
        return set(), [error]
    services = document.get("services") if isinstance(document, dict) else []
    if not isinstance(services, list):
        return set(), [f"{display_path(AGORA_BOS_REGISTRY_PATH)} services must be a list"]
    routes = {
        str(service.get("uri"))
        for service in services
        if isinstance(service, dict)
        and isinstance(service.get("uri"), str)
        and service["uri"].startswith(GOVERNANCE_EVOLUTION_BOS_PREFIX)
    }
    return routes, []


def validate_bos_route_alignment(registry: dict[str, Any]) -> list[str]:
    entrypoints = registry.get("entrypoints")
    if not isinstance(entrypoints, dict):
        return []
    bos_routes = entrypoints.get("bos")
    if not isinstance(bos_routes, list) or not all(isinstance(route, str) for route in bos_routes):
        return ["entrypoints.bos must be a list of strings"]
    expected = {route for route in bos_routes if route.startswith(GOVERNANCE_EVOLUTION_BOS_PREFIX)}
    actual, errors = agora_governance_evolution_routes()
    if errors:
        return errors
    findings: list[str] = []
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        findings.append(f"entrypoints.bos routes missing from Agora BOS registry: {', '.join(missing)}")
    if extra:
        findings.append(f"Agora BOS governance evolution routes missing from roadmap: {', '.join(extra)}")
    return findings


def validate_cockpit_entrypoint_alignment(registry: dict[str, Any]) -> list[str]:
    entrypoints = registry.get("entrypoints")
    if not isinstance(entrypoints, dict):
        return []
    human_entry = str(entrypoints.get("human") or "")
    if human_entry != "cockpit governance evolution":
        return [f"entrypoints.human must be `cockpit governance evolution`, got `{human_entry}`"]
    findings: list[str] = []
    if not COCKPIT_CLI_PATH.exists():
        findings.append(f"missing Cockpit CLI file: {display_path(COCKPIT_CLI_PATH)}")
    else:
        cli_text = COCKPIT_CLI_PATH.read_text(encoding="utf-8")
        if 'sub.add_parser("governance"' not in cli_text:
            findings.append("Cockpit CLI must expose `cockpit governance`")
        if '"evolution"' not in cli_text:
            findings.append("Cockpit CLI governance parser must accept `evolution`")
    if not COCKPIT_GOVERNANCE_COMMAND_PATH.exists():
        findings.append(f"missing Cockpit governance command: {display_path(COCKPIT_GOVERNANCE_COMMAND_PATH)}")
    else:
        command_text = COCKPIT_GOVERNANCE_COMMAND_PATH.read_text(encoding="utf-8")
        required_snippets = [
            "def _run_governance_evolution",
            'forwarded = args or ["status"]',
            '"bin" / "governance-evolution.py"',
            'if subcmd == "evolution"',
            "return _run_governance_evolution",
        ]
        missing = [snippet for snippet in required_snippets if snippet not in command_text]
        if missing:
            findings.append(f"Cockpit governance evolution delegation missing snippets: {', '.join(missing)}")
    return findings


def is_external_ref(value: str) -> bool:
    return (
        value.startswith("bos://")
        or value.startswith("http://")
        or value.startswith("https://")
        or " " in value
        or value.startswith("uv ")
        or value.startswith("python")
        or value.startswith("make ")
        or value.startswith("cockpit")
        or value.startswith("bin/")
    )


def path_exists_if_local(value: str) -> bool:
    if "*" in value or is_external_ref(value):
        return True
    return (WORKSPACE / value).exists()


def validate_command_list(command: Any, prefix: str) -> list[str]:
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        return [f"{prefix}: command must be a non-empty list of strings"]
    return []


def validate_roadmap(registry: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(registry.get("version"), int):
        errors.append("version must be an integer")
    for key in ("ssot", "entrypoints", "preferred_entrypoints"):
        if not isinstance(registry.get(key), dict):
            errors.append(f"{key} must be a mapping")
    errors.extend(validate_bos_route_alignment(registry))
    errors.extend(validate_cockpit_entrypoint_alignment(registry))

    initiatives = registry.get("initiatives")
    if not isinstance(initiatives, list) or not initiatives:
        errors.append("initiatives must be a non-empty list")
        initiatives = []
    seen_ids: set[str] = set()
    for index, initiative in enumerate(initiatives):
        prefix = f"initiatives[{index}]"
        if not isinstance(initiative, dict):
            errors.append(f"{prefix}: entry must be a mapping")
            continue
        initiative_id = str(initiative.get("id") or "")
        if not initiative_id:
            errors.append(f"{prefix}: missing id")
        elif initiative_id in seen_ids:
            errors.append(f"{prefix}: duplicate id {initiative_id}")
        seen_ids.add(initiative_id)
        for field in ("title", "recommendation", "owner", "layer", "ssot"):
            if not initiative.get(field):
                errors.append(f"{initiative_id or prefix}: missing {field}")
        status = str(initiative.get("status") or "")
        if status not in VALID_INITIATIVE_STATUS:
            errors.append(f"{initiative_id or prefix}: status must be one of {sorted(VALID_INITIATIVE_STATUS)}")
        level = initiative.get("meadows_level")
        if not isinstance(level, int) or level < 1 or level > 12:
            errors.append(f"{initiative_id or prefix}: meadows_level must be an integer from 1 to 12")
        for field in ("entrypoints", "deliverables", "verification", "acceptance"):
            if not isinstance(initiative.get(field), list) or not initiative.get(field):
                errors.append(f"{initiative_id or prefix}: {field} must be a non-empty list")
        if not isinstance(initiative.get("done_when"), str) or not initiative.get("done_when"):
            errors.append(f"{initiative_id or prefix}: done_when must be a non-empty string")
        blocked_by = initiative.get("blocked_by")
        if not isinstance(blocked_by, list) or not all(isinstance(item, str) for item in blocked_by):
            errors.append(f"{initiative_id or prefix}: blocked_by must be a list of strings")
        for deliverable in initiative.get("deliverables") or []:
            if isinstance(deliverable, str) and not path_exists_if_local(deliverable):
                warnings.append(f"{initiative_id}: deliverable path not present yet: {deliverable}")
        for check_index, check in enumerate(initiative.get("verification") or []):
            if not isinstance(check, dict):
                errors.append(f"{initiative_id}.verification[{check_index}]: entry must be a mapping")
                continue
            errors.extend(validate_command_list(check.get("command"), f"{initiative_id}.verification[{check_index}]"))

    for section in ("capability_traces", "golden_paths"):
        rows = registry.get(section)
        if not isinstance(rows, list) or not rows:
            errors.append(f"{section} must be a non-empty list")
            continue
        ids: set[str] = set()
        for index, row in enumerate(rows):
            prefix = f"{section}[{index}]"
            if not isinstance(row, dict):
                errors.append(f"{prefix}: entry must be a mapping")
                continue
            row_id = str(row.get("id") or "")
            if not row_id:
                errors.append(f"{prefix}: missing id")
            elif row_id in ids:
                errors.append(f"{prefix}: duplicate id {row_id}")
            ids.add(row_id)
            required = ("capability", "entry", "ssot", "verifier") if section == "capability_traces" else (
                "title",
                "owner",
                "steps",
                "verifier",
            )
            for field in required:
                if not row.get(field):
                    errors.append(f"{row_id or prefix}: missing {field}")
            if section == "golden_paths" and not isinstance(row.get("steps"), list):
                errors.append(f"{row_id or prefix}: steps must be a list")

    rhythm = registry.get("operating_rhythm")
    if not isinstance(rhythm, dict):
        errors.append("operating_rhythm must be a mapping")
    else:
        for cadence, commands in rhythm.items():
            if not isinstance(commands, list) or not all(isinstance(command, str) for command in commands):
                errors.append(f"operating_rhythm.{cadence}: must be a list of command strings")
    return errors, warnings


def build_status(registry: dict[str, Any]) -> dict[str, Any]:
    errors, warnings = validate_roadmap(registry)
    initiatives = registry.get("initiatives") or []
    by_status: dict[str, int] = {}
    for initiative in initiatives:
        if isinstance(initiative, dict):
            status = str(initiative.get("status") or "unknown")
            by_status[status] = by_status.get(status, 0) + 1
    return {
        "ok": not errors,
        "registry": display_path(REGISTRY_PATH),
        "version": registry.get("version"),
        "initiative_count": len(initiatives),
        "by_status": by_status,
        "initiatives": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "status": item.get("status"),
                "owner": item.get("owner"),
                "layer": item.get("layer"),
            }
            for item in initiatives
            if isinstance(item, dict)
        ],
        "entrypoints": registry.get("entrypoints", {}),
        "preferred_entrypoints": registry.get("preferred_entrypoints", {}),
        "next_active": [
            {
                "id": item.get("id"),
                "status": item.get("status"),
                "next_step": item.get("next_step"),
            }
            for item in initiatives
            if isinstance(item, dict) and item.get("status") in {"planned", "in_progress", "active"}
        ],
        "errors": errors,
        "warnings": warnings,
    }


def git_status_lines() -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RoadmapError(completed.stderr.strip() or "git status failed")
    return [line for line in completed.stdout.splitlines() if line.strip()]


def parse_status_line(line: str) -> tuple[str, str]:
    status = line[:2].strip() or "?"
    path = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    if path.startswith('"') and path.endswith('"'):
        escaped = path[1:-1]
        try:
            path = escaped.encode("utf-8").decode("unicode_escape").encode("latin1").decode("utf-8")
        except UnicodeError:
            path = escaped
    return status, path


def classify_release_package(path: str) -> tuple[str, str]:
    if path.startswith((
        ".omo/_control/", ".omo/_delivery/agent-workflows/", ".omo/state/",
        "runtime/omo/_control/", "runtime/omo/_delivery/agent-workflows/", "runtime/omo/state/",
    )):
        return "runtime-or-control-output", "review evidence/control output before including in a release package"
    if path.startswith((".omo/_knowledge/", ".omo/change-log/", "runtime/omo/_knowledge/", "runtime/omo/change-log/")):
        return "governance-history-evidence", "review as governance evidence/history, not executable control logic"
    if path.startswith((".omo/tasks/", "runtime/omo/tasks/")):
        return "governance-task-lifecycle", "review OMO task lifecycle state and registry effects"
    if path.endswith("-audit-report.md"):
        return "governance-audit-report", "review root audit report placement and release intent"
    if path.startswith(".c2g_data/"):
        return "strategy-ingress-artifact", "review strategy ingress/task lifecycle before release"
    if path.startswith("_archived/"):
        return "archived-artifact", "review archive deletion or migration intent before release"
    if path.startswith("data/"):
        return "data-output", "keep user/runtime data out of governance release packages unless explicitly required"
    if path.startswith((".omo/_truth/registry/", ".omo/standards/", "runtime/omo/_truth/registry/", "runtime/omo/standards/")):
        return "governance-truth-and-standards", "review with AGCP claim coverage and SSOT checks"
    if path.startswith("ecos/src/ecos/ssot/mof/") or path.startswith("projects/ecos/src/ecos/ssot/mof/"):
        return "mof-model-registry", "review MOF schema/state bridge and model drift checks"
    if path in {".env.example", ".gitignore", "pyproject.toml"} or path.startswith(
        ("config/", ".github/workflows/", ".githooks/")
    ):
        return "workspace-config", "review workspace configuration examples and machine identity boundaries"
    if path.startswith(".agents/skills/") or path.startswith("bin/") or path.startswith("tests/") or path == "Makefile":
        return "governance-control-plane", "ship with focused tests and make gac-local-gate"
    if path in {"AGENTS.md", "CLAUDE.md", "README.md"} or path.startswith("docs/"):
        return "governance-docs", "ship with doc-ssot-lint and doc-link-check"
    if path == "projects/AGENTS.md" or (
        path.startswith("projects/") and path.endswith(("/AGENTS.md", "/CLAUDE.md", "/README.md"))
    ):
        return "project-entry-docs", "review as project entrypoint documentation"
    if path == "scripts" or (path.startswith("projects/") and path.count("/") == 1):
        return "submodule-pointer", "review child repository status before release"
    if path.startswith("protocols/"):
        return "protocol-registry", "review protocol registry drift and consumers"
    return "unknown", "inspect manually before release"


def release_review_findings(packages: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    unknown_paths = packages.get("unknown", {}).get("paths", [])
    if unknown_paths:
        findings.append(
            {
                "severity": "blocker",
                "package": "unknown",
                "count": len(unknown_paths),
                "paths": unknown_paths,
                "message": "classify unknown entries before release",
                "owner": "governance-team",
                "workflow": "project-code-change",
                "recommended_action": "Classify every unknown path before release packaging.",
            }
        )
    for package_id, review in RELEASE_REVIEW_PACKAGES.items():
        paths = packages.get(package_id, {}).get("paths", [])
        if paths:
            findings.append(
                {
                    "severity": "review",
                    "package": package_id,
                    "count": len(paths),
                    "paths": paths,
                    "message": review["message"],
                    "owner": review["owner"],
                    "workflow": review["workflow"],
                    "recommended_action": review["recommended_action"],
                }
            )
    return findings




def agent_workflow_claim_command(path: str) -> list[str]:
    return [
        "uv",
        "run",
        "--with",
        "pyyaml",
        "python",
        "bin/agent-workflow.py",
        "claim",
        "<run-id>",
        "--path",
        path,
    ]

def release_review_plan(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batches: dict[str, dict[str, Any]] = {}
    for finding in findings:
        workflow = str(finding.get("workflow") or "project-code-change")
        profile = RELEASE_REVIEW_WORKFLOW_PROFILES.get(workflow, "governance-agent")
        bucket = batches.setdefault(
            workflow,
            {
                "workflow": workflow,
                "profile": profile,
                "owners": [],
                "package_count": 0,
                "path_count": 0,
                "packages": [],
                "recommended_actions": [],
                "start_command": [
                    "uv",
                    "run",
                    "--with",
                    "pyyaml",
                    "python",
                    "bin/agent-workflow.py",
                    "start",
                    workflow,
                    "--profile",
                    profile,
                    "--objective",
                    f"Review release package findings for {workflow}",
                ],
                "claim_commands": [],
                "closeout_command_template": [
                    "uv",
                    "run",
                    "--with",
                    "pyyaml",
                    "python",
                    "bin/agent-workflow.py",
                    "closeout",
                    "<run-id>",
                    "--evidence",
                    f"Reviewed release package findings for {workflow}",
                ],
                "decision_options": list(ALLOWED_RELEASE_DECISIONS),
            },
        )
        owner = str(finding.get("owner") or "")
        if owner and owner not in bucket["owners"]:
            bucket["owners"].append(owner)
        action = str(finding.get("recommended_action") or "")
        if action and action not in bucket["recommended_actions"]:
            bucket["recommended_actions"].append(action)
        paths = [str(path) for path in finding.get("paths") or []]
        for path in paths:
            claim_command = agent_workflow_claim_command(path)
            if claim_command not in bucket["claim_commands"]:
                bucket["claim_commands"].append(claim_command)
        bucket["package_count"] += 1
        bucket["path_count"] += len(paths)
        bucket["packages"].append(
            {
                "package": finding.get("package"),
                "severity": finding.get("severity"),
                "count": finding.get("count"),
                "paths": paths,
                "recommended_action": action,
            }
        )
    return [batches[workflow] for workflow in sorted(batches)]


def release_decision_template(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for finding in findings:
        workflow = str(finding.get("workflow") or "project-code-change")
        profile = RELEASE_REVIEW_WORKFLOW_PROFILES.get(workflow, "governance-agent")
        package = str(finding.get("package") or "unknown")
        owner = str(finding.get("owner") or "governance-team")
        severity = str(finding.get("severity") or "review")
        action = str(finding.get("recommended_action") or "")
        for path in [str(path) for path in finding.get("paths") or []]:
            decisions.append(
                {
                    "decision_id": f"{workflow}:{package}:{path}",
                    "workflow": workflow,
                    "profile": profile,
                    "owner": owner,
                    "package": package,
                    "path": path,
                    "severity": severity,
                    "decision": None,
                    "decision_required": True,
                    "allowed_decisions": list(ALLOWED_RELEASE_DECISIONS),
                    "recommended_action": action,
                    "claim_command": agent_workflow_claim_command(path),
                    "notes": "",
                }
            )
    return decisions


def load_release_decisions(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    decision_path = Path(path)
    if not decision_path.is_absolute():
        decision_path = WORKSPACE / decision_path
    if not decision_path.exists():
        raise RoadmapError(f"release decisions file not found: {display_path(decision_path)}")
    try:
        payload = yaml.safe_load(decision_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RoadmapError(f"invalid release decisions YAML: {display_path(decision_path)} ({exc})") from exc
    if payload is None:
        return []
    records = payload.get("decisions") if isinstance(payload, dict) else payload
    if not isinstance(records, list):
        raise RoadmapError("release decisions must be a list or a mapping with decisions: [...]")
    out: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise RoadmapError(f"release decision #{index + 1} must be a mapping")
        out.append(record)
    return out


def apply_release_decisions(
    decision_template: list[dict[str, Any]], decision_records: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    decisions = [dict(item) for item in decision_template]
    by_id = {str(item["decision_id"]): item for item in decisions}
    by_path = {str(item["path"]): item for item in decisions}
    invalid: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for index, record in enumerate(decision_records):
        decision_id = str(record.get("decision_id") or "")
        path = str(record.get("path") or "")
        key = decision_id or path
        target = by_id.get(decision_id) if decision_id else None
        if target is None and path:
            target = by_path.get(path)
        if not key:
            invalid.append({"index": index, "reason": "missing decision_id or path", "record": record})
            continue
        if key in seen_keys:
            invalid.append({"index": index, "reason": "duplicate decision", "key": key})
            continue
        seen_keys.add(key)
        if target is None:
            invalid.append({"index": index, "reason": "decision target not in current template", "key": key})
            continue
        decision = record.get("decision")
        if decision not in ALLOWED_RELEASE_DECISIONS:
            invalid.append(
                {
                    "index": index,
                    "reason": "invalid decision",
                    "key": key,
                    "decision": decision,
                    "allowed_decisions": list(ALLOWED_RELEASE_DECISIONS),
                }
            )
            continue
        target["decision"] = decision
        target["notes"] = str(record.get("notes") or "")
        for optional_key in ("reviewed_by", "evidence"):
            if optional_key in record:
                target[optional_key] = record[optional_key]

    counts = {decision: 0 for decision in ALLOWED_RELEASE_DECISIONS}
    pending = 0
    for item in decisions:
        decision = item.get("decision")
        if decision in counts:
            counts[str(decision)] += 1
        else:
            pending += 1
    summary = {
        "total": len(decisions),
        "pending": pending,
        "invalid": len(invalid),
        "include": counts["include"],
        "exclude": counts["exclude"],
        "defer": counts["defer"],
        "applied": len(decision_records) - len(invalid),
        "ready": pending == 0 and not invalid,
        "invalid_decisions": invalid,
    }
    return decisions, summary


def release_decision_template_records(
    decision_template: list[dict[str, Any]], default_decision: str = ""
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in decision_template:
        records.append(
            {
                "decision_id": item["decision_id"],
                "path": item["path"],
                "workflow": item["workflow"],
                "package": item["package"],
                "owner": item["owner"],
                "decision": default_decision or None,
                "notes": item["recommended_action"],
            }
        )
    return records


def write_release_decision_template(
    decision_template: list[dict[str, Any]], output_path: str, default_decision: str = ""
) -> str:
    if default_decision and default_decision not in ALLOWED_RELEASE_DECISIONS:
        raise RoadmapError(
            "release decision default must be one of: " + ", ".join(ALLOWED_RELEASE_DECISIONS)
        )
    decision_path = Path(output_path)
    if not decision_path.is_absolute():
        decision_path = WORKSPACE / decision_path
    if not decision_path.parent.exists():
        raise RoadmapError(f"release decisions output parent not found: {display_path(decision_path.parent)}")
    if decision_path.exists() and decision_path.is_dir():
        raise RoadmapError(f"release decisions output is a directory: {display_path(decision_path)}")
    payload = {
        "decisions": release_decision_template_records(decision_template, default_decision),
    }
    decision_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return display_path(decision_path)


def build_package_report(
    decisions_path: str | None = None,
    *,
    require_ready: bool = False,
    write_decisions_template: str = "",
    decision_default: str = "",
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    packages: dict[str, dict[str, Any]] = {}
    for line in git_status_lines():
        status, path = parse_status_line(line)
        package, recommendation = classify_release_package(path)
        entry = {
            "status": status,
            "path": path,
            "package": package,
            "recommendation": recommendation,
        }
        entries.append(entry)
        bucket = packages.setdefault(package, {"count": 0, "paths": [], "recommendation": recommendation})
        bucket["count"] += 1
        bucket["paths"].append(path)
    ordered_packages = [
        {"id": package, **packages[package]}
        for package in PACKAGE_ORDER
        if package in packages
    ]
    unknown_count = packages.get("unknown", {}).get("count", 0)
    review_findings = release_review_findings(packages)
    review_plan = release_review_plan(review_findings)
    decision_template = release_decision_template(review_findings)
    generated_decision_records = (
        release_decision_template_records(decision_template, decision_default)
        if write_decisions_template and decision_default
        else []
    )
    decision_records = load_release_decisions(decisions_path) if decisions_path else generated_decision_records
    decision_template, decision_summary = apply_release_decisions(decision_template, decision_records)
    written_template = ""
    if write_decisions_template:
        written_template = write_release_decision_template(
            release_decision_template(review_findings),
            write_decisions_template,
            decision_default,
        )
    release_ready = not review_findings or decision_summary["ready"]
    release_gate = {
        "required": require_ready,
        "ok": release_ready,
        "blocking": require_ready and not release_ready,
    }
    report_ok = unknown_count == 0 and decision_summary["invalid"] == 0 and not release_gate["blocking"]
    review_workflows = sorted(
        {
            str(item["workflow"])
            for item in review_findings
            if isinstance(item.get("workflow"), str) and item.get("workflow")
        }
    )
    return {
        "ok": report_ok,
        "release_ready": release_ready,
        "release_gate": release_gate,
        "entry_count": len(entries),
        "unknown_count": unknown_count,
        "review_count": sum(item["count"] for item in review_findings),
        "decision_count": len(decision_template),
        "decision_source": decisions_path or "",
        "decision_template_written": written_template,
        "decision_template_default": decision_default,
        "decision_summary": decision_summary,
        "review_workflows": review_workflows,
        "review_plan": review_plan,
        "decision_template": decision_template,
        "review_findings": review_findings,
        "release_order": [item["id"] for item in ordered_packages],
        "packages": ordered_packages,
        "entries": entries,
        "recommended_next": "Review unknown package entries before release." if unknown_count else (
            "Fix invalid release decision records."
            if decision_summary["invalid"]
            else (
                "Complete release decisions before packaging."
                if release_gate["blocking"]
                else (
                    f"Resolve release review findings through workflows: {', '.join(review_workflows)}."
                    if decision_summary["pending"]
                    else "Release decisions complete; proceed with packaging closeout."
                )
            )
        ),
    }


def print_report(report: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    if isinstance(report, dict) and "ok" in report:
        print(f"governance-evolution: {'PASS' if report['ok'] else 'FAIL'}")
        print(f"registry={report.get('registry')} initiatives={report.get('initiative_count')}")
        for warning in report.get("warnings", []):
            print(f"[WARN] {warning}")
        for error in report.get("errors", []):
            print(f"[FAIL] {error}", file=sys.stderr)
        return
    print(json.dumps(report, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect governance evolution roadmap")
    parser.add_argument("--registry", default=str(REGISTRY_PATH))
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "validate", "traces", "golden-paths"):
        command_parser = sub.add_parser(name)
        command_parser.add_argument("--json", action="store_true")
    packages_parser = sub.add_parser("packages")
    packages_parser.add_argument("--json", action="store_true")
    packages_parser.add_argument(
        "--decisions",
        default="",
        help="YAML/JSON file with release decisions keyed by decision_id or path.",
    )
    packages_parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return non-zero unless release decisions make the package set ready.",
    )
    packages_parser.add_argument(
        "--write-decisions-template",
        default="",
        help="Write the current release decision template to a YAML file.",
    )
    packages_parser.add_argument(
        "--decision-default",
        choices=ALLOWED_RELEASE_DECISIONS,
        default="",
        help="Decision value to prefill when writing a release decision template.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        registry = load_roadmap(Path(args.registry))
        if args.command in {"status", "validate"}:
            report = build_status(registry)
            print_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "traces":
            report = registry.get("capability_traces") or []
            print_report(report, args.json)
            return 0
        if args.command == "golden-paths":
            report = registry.get("golden_paths") or []
            print_report(report, args.json)
            return 0
        if args.command == "packages":
            report = build_package_report(
                args.decisions,
                require_ready=args.require_ready,
                write_decisions_template=args.write_decisions_template,
                decision_default=args.decision_default,
            )
            print_report(report, args.json)
            return 0 if report["ok"] else 1
    except RoadmapError as exc:
        print(f"governance-evolution: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
