#!/usr/bin/env python3
"""Executable agent workflow runner for project-level governance."""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml


WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY_PATH = WORKSPACE / ".omo/_truth/registry/agent-workflows.yaml"
ADAPTER_AUTHORITIES = {"discipline_layer", "input_adapter", "memory_adapter"}
INTEGRATION_AUTHORITIES = {
    "entrypoint",
    "governance_gate",
    "model_registry",
    "state_broker",
    "strategy_ingress",
}


class WorkflowError(RuntimeError):
    """Raised when the workflow registry or run state is invalid."""


class SafeFormatDict(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        raise WorkflowError(f"workflow registry not found: {path}")
    documents = [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]
    for document in documents:
        if isinstance(document, dict) and "workflows" in document:
            return document
    raise WorkflowError(f"workflow registry has no workflows document: {path}")


def workflow_by_id(registry: dict[str, Any], workflow_id: str) -> dict[str, Any]:
    for workflow in registry.get("workflows", []):
        if workflow.get("id") == workflow_id:
            return workflow
    raise WorkflowError(f"unknown workflow: {workflow_id}")


def workflow_roles(workflow: dict[str, Any]) -> list[str]:
    agents = workflow.get("agents") or {}
    roles = agents.get("roles") if isinstance(agents, dict) else []
    if not isinstance(roles, list):
        return []
    return [role for role in roles if isinstance(role, str)]


def validate_agent_profile(
    registry: dict[str, Any],
    workflow: dict[str, Any],
    profile_id: str,
    require: bool,
) -> None:
    roles = workflow_roles(workflow)
    workflow_id = str(workflow.get("id") or "")
    if not profile_id:
        if require and roles:
            raise WorkflowError(f"{workflow_id} requires --profile ({', '.join(roles)})")
        return
    profiles = registry.get("agent_profiles") or {}
    profile = profiles.get(profile_id) if isinstance(profiles, dict) else None
    if not isinstance(profile, dict):
        raise WorkflowError(f"unknown agent profile: {profile_id}")
    allowed = profile.get("allowed_workflows", [])
    if allowed != ["*"] and workflow_id not in allowed:
        raise WorkflowError(f"agent profile {profile_id} cannot run workflow {workflow_id}")
    if roles and profile_id not in roles:
        raise WorkflowError(f"agent profile {profile_id} is not listed in {workflow_id}.agents.roles")


def context_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {
        "project": str(getattr(args, "project", "") or ""),
        "format": str(getattr(args, "format", "") or "openspec"),
        "source_file": str(getattr(args, "source_file", "") or ""),
        "run_id": str(getattr(args, "run_id", "") or ""),
        "actor": str(getattr(args, "actor", "") or "agent"),
        "profile": str(getattr(args, "profile", "") or ""),
    }


def substitute(value: Any, context: dict[str, str]) -> Any:
    if isinstance(value, str):
        return value.format_map(SafeFormatDict(context))
    if isinstance(value, list):
        return [substitute(item, context) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item, context) for key, item in value.items()}
    return value


def command_display(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def validate_command(workflow_id: str, phase: str, index: int, item: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    prefix = f"{workflow_id}.{phase}[{index}]"
    if not isinstance(item, dict):
        return [f"{prefix}: command entry must be a mapping"]
    if not item.get("id"):
        errors.append(f"{prefix}: missing id")
    if item.get("mode") not in {"required", "advisory", "manual"}:
        errors.append(f"{prefix}: mode must be required/advisory/manual")
    command = item.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
        errors.append(f"{prefix}: command must be a non-empty list of strings")
    return errors


def lint_registry(registry: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    agent_profiles = registry.get("agent_profiles") or {}
    if agent_profiles and not isinstance(agent_profiles, dict):
        errors.append("registry.agent_profiles must be a mapping")
        agent_profiles = {}
    workflows = registry.get("workflows")
    if not isinstance(workflows, list) or not workflows:
        errors.append("registry.workflows must be a non-empty list")
        return errors, warnings

    seen: set[str] = set()
    for workflow in workflows:
        if not isinstance(workflow, dict):
            errors.append("workflow entry must be a mapping")
            continue
        workflow_id = workflow.get("id")
        if not workflow_id:
            errors.append("workflow missing id")
            continue
        if workflow_id in seen:
            errors.append(f"duplicate workflow id: {workflow_id}")
        seen.add(workflow_id)
        for field in ("title", "purpose", "allowed_lanes", "lock_scopes", "surfaces", "phases"):
            if field not in workflow:
                errors.append(f"{workflow_id}: missing {field}")
        for field in ("allowed_lanes", "lock_scopes"):
            values = workflow.get(field, [])
            if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
                errors.append(f"{workflow_id}: {field} must be a list of strings")
        agents = workflow.get("agents")
        if agents is not None:
            if not isinstance(agents, dict):
                errors.append(f"{workflow_id}: agents must be a mapping")
            else:
                roles = agents.get("roles", [])
                if not isinstance(roles, list) or not all(isinstance(item, str) for item in roles):
                    errors.append(f"{workflow_id}: agents.roles must be a list of strings")
                for role in roles if isinstance(roles, list) else []:
                    profile = agent_profiles.get(role) if isinstance(agent_profiles, dict) else None
                    if not isinstance(profile, dict):
                        errors.append(f"{workflow_id}: unknown agent role: {role}")
                        continue
                    allowed = profile.get("allowed_workflows", [])
                    if allowed != ["*"] and workflow_id not in allowed:
                        errors.append(f"{workflow_id}: role {role} does not allow this workflow")
        phases = workflow.get("phases", {})
        if not isinstance(phases, dict):
            errors.append(f"{workflow_id}: phases must be a mapping")
            continue
        for phase in ("preflight", "execute", "verification", "closeout"):
            entries = phases.get(phase)
            if not isinstance(entries, list) or not entries:
                errors.append(f"{workflow_id}: missing non-empty phase {phase}")
                continue
            for index, item in enumerate(entries):
                errors.extend(validate_command(workflow_id, phase, index, item))

    if isinstance(agent_profiles, dict):
        for profile_id, profile in agent_profiles.items():
            if not isinstance(profile, dict):
                errors.append(f"agent_profiles.{profile_id}: profile must be a mapping")
                continue
            for field in ("purpose", "allowed_workflows", "can_write_lanes"):
                if field not in profile:
                    errors.append(f"agent_profiles.{profile_id}: missing {field}")
            allowed = profile.get("allowed_workflows", [])
            if not isinstance(allowed, list) or not all(isinstance(item, str) for item in allowed):
                errors.append(f"agent_profiles.{profile_id}: allowed_workflows must be a list of strings")
            else:
                for workflow_ref in allowed:
                    if workflow_ref != "*" and workflow_ref not in seen:
                        errors.append(
                            f"agent_profiles.{profile_id}: unknown workflow in allowed_workflows: {workflow_ref}"
                        )
            lanes = profile.get("can_write_lanes", [])
            if not isinstance(lanes, list) or not all(isinstance(item, str) for item in lanes):
                errors.append(f"agent_profiles.{profile_id}: can_write_lanes must be a list of strings")

    for name, integration in (registry.get("internal_integrations") or {}).items():
        if not isinstance(integration, dict):
            errors.append(f"internal_integrations.{name}: integration must be a mapping")
            continue
        for field in ("status", "authority", "owner", "ssot_rule", "health_command", "health_required"):
            if field not in integration:
                errors.append(f"internal_integrations.{name}: missing {field}")
        authority = integration.get("authority")
        if authority and authority not in INTEGRATION_AUTHORITIES:
            errors.append(
                "internal_integrations."
                f"{name}: authority must be one of {', '.join(sorted(INTEGRATION_AUTHORITIES))}"
            )
        health_command = integration.get("health_command")
        if health_command is not None and (
            not isinstance(health_command, list)
            or not health_command
            or not all(isinstance(part, str) for part in health_command)
        ):
            errors.append(f"internal_integrations.{name}: health_command must be a non-empty list of strings")
        if "health_required" in integration and not isinstance(integration.get("health_required"), bool):
            errors.append(f"internal_integrations.{name}: health_required must be a boolean")

    for name, adapter in (registry.get("external_patterns") or {}).items():
        if not isinstance(adapter, dict):
            errors.append(f"external_patterns.{name}: adapter must be a mapping")
            continue
        for field in ("status", "pattern", "authority", "ssot_rule", "ingress_workflow"):
            if not adapter.get(field):
                errors.append(f"external_patterns.{name}: missing {field}")
        authority = adapter.get("authority")
        if authority and authority not in ADAPTER_AUTHORITIES:
            errors.append(
                f"external_patterns.{name}: authority must be one of {', '.join(sorted(ADAPTER_AUTHORITIES))}"
            )
        command = adapter.get("command")
        if command and shutil.which(str(command)) is None:
            warnings.append(f"optional adapter not installed: {name} ({command})")
        health_command = adapter.get("health_command")
        if health_command is not None and (
            not isinstance(health_command, list)
            or not health_command
            or not all(isinstance(part, str) for part in health_command)
        ):
            errors.append(f"external_patterns.{name}: health_command must be a non-empty list of strings")
        if "health_required" in adapter and not isinstance(adapter.get("health_required"), bool):
            errors.append(f"external_patterns.{name}: health_required must be a boolean")
    for index, check_item in enumerate(registry.get("doctor_checks") or []):
        prefix = f"doctor_checks[{index}]"
        if not isinstance(check_item, dict):
            errors.append(f"{prefix}: entry must be a mapping")
            continue
        command = check_item.get("command")
        if not check_item.get("id"):
            errors.append(f"{prefix}: missing id")
        if not isinstance(command, list) or not command or not all(isinstance(part, str) for part in command):
            errors.append(f"{prefix}: command must be a non-empty list of strings")
    return errors, warnings


def print_lint(errors: list[str], warnings: list[str], as_json: bool) -> None:
    report = {"ok": not errors, "errors": errors, "warnings": warnings}
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    for warning in warnings:
        print(f"[WARN] {warning}")
    if errors:
        for error in errors:
            print(f"[FAIL] {error}", file=sys.stderr)
        print("agent-workflow lint: FAIL", file=sys.stderr)
    else:
        print("agent-workflow lint: PASS")


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


def workflow_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": workflow["id"],
            "title": workflow.get("title", ""),
            "lanes": workflow.get("allowed_lanes", []),
        }
        for workflow in registry.get("workflows", [])
    ]


def agent_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": profile_id,
            "purpose": profile.get("purpose", ""),
            "allowed_workflows": profile.get("allowed_workflows", []),
            "can_write_lanes": profile.get("can_write_lanes", []),
        }
        for profile_id, profile in sorted((registry.get("agent_profiles") or {}).items())
        if isinstance(profile, dict)
    ]


def integration_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, integration in (registry.get("internal_integrations") or {}).items():
        if not isinstance(integration, dict):
            continue
        rows.append(
            {
                "name": name,
                "status": integration.get("status"),
                "authority": integration.get("authority"),
                "owner": integration.get("owner"),
                "ssot_rule": integration.get("ssot_rule"),
                "gate_binding": integration.get("gate_binding"),
                "health_command": integration.get("health_command"),
                "health_required": bool(integration.get("health_required", False)),
                "commands": {
                    key: value
                    for key, value in integration.items()
                    if key
                    not in {
                        "status",
                        "authority",
                        "owner",
                        "ssot_rule",
                        "gate_binding",
                        "health_command",
                        "health_required",
                    }
                },
            }
        )
    return rows


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


def adapter_rows(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, adapter in (registry.get("external_patterns") or {}).items():
        if not isinstance(adapter, dict):
            continue
        command = adapter.get("command")
        found = shutil.which(str(command)) if command else None
        rows.append(
            {
                "name": name,
                "status": adapter.get("status"),
                "authority": adapter.get("authority"),
                "ssot_rule": adapter.get("ssot_rule"),
                "ingress_workflow": adapter.get("ingress_workflow"),
                "skill": adapter.get("skill"),
                "command": command,
                "available": bool(found) if command else True,
                "path": found,
                "bridge": adapter.get("bridge"),
                "pattern": adapter.get("pattern"),
                "degrade_to": adapter.get("degrade_to"),
                "health_command": adapter.get("health_command"),
                "health_required": bool(adapter.get("health_required", False)),
            }
        )
    return rows


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


def workflow_plan(workflow: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    resolved = substitute(workflow, context)
    return {
        "id": resolved["id"],
        "title": resolved.get("title", ""),
        "purpose": resolved.get("purpose", ""),
        "agents": resolved.get("agents", {}),
        "allowed_lanes": resolved.get("allowed_lanes", []),
        "lock_scopes": resolved.get("lock_scopes", []),
        "phases": resolved.get("phases", {}),
    }


def print_plan(plan: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return
    print(f"{plan['id']} — {plan['title']}")
    print(plan["purpose"])
    roles = plan.get("agents", {}).get("roles") or []
    if roles:
        print(f"agents: {', '.join(roles)}")
    print(f"lanes: {', '.join(plan['allowed_lanes'])}")
    print(f"locks: {', '.join(plan['lock_scopes'])}")
    for phase, entries in plan["phases"].items():
        print(f"\n[{phase}]")
        for item in entries:
            mode = item.get("mode", "?")
            cwd = item.get("cwd")
            prefix = f"({mode})"
            if cwd:
                prefix += f" cwd={cwd}"
            print(f"  {item.get('id')}: {prefix} {command_display(item['command'])}")


def run_stage(
    workflow: dict[str, Any],
    stage: str,
    context: dict[str, str],
    execute: bool,
    as_json: bool,
) -> int:
    plan = workflow_plan(workflow, context)
    entries = plan["phases"].get(stage)
    if not entries:
        raise WorkflowError(f"{plan['id']} has no stage: {stage}")

    results: list[dict[str, Any]] = []
    for item in entries:
        mode = item.get("mode")
        command = item["command"]
        cwd = WORKSPACE / item.get("cwd", ".")
        skipped = mode == "manual" or not execute
        result: dict[str, Any] = {
            "id": item.get("id"),
            "mode": mode,
            "command": command_display(command),
            "cwd": str(cwd.relative_to(WORKSPACE)) if cwd.is_relative_to(WORKSPACE) else str(cwd),
            "skipped": skipped,
            "ok": True,
        }
        if not skipped:
            completed = subprocess.run(command, cwd=cwd, check=False)
            result["returncode"] = completed.returncode
            result["ok"] = completed.returncode == 0 or mode == "advisory"
        results.append(result)

    report = {"workflow": plan["id"], "stage": stage, "execute": execute, "results": results}
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for result in results:
            status = "SKIP" if result["skipped"] else ("PASS" if result["ok"] else "FAIL")
            print(f"[{status}] {result['id']} :: {result['command']}")
    return 0 if all(item["ok"] for item in results) else 1


def run_state_dir(registry: dict[str, Any]) -> Path:
    return WORKSPACE / registry.get("runner", {}).get(
        "run_state_dir", ".omo/_delivery/agent-workflows/runs"
    )


def lock_state_dir(registry: dict[str, Any]) -> Path:
    return WORKSPACE / registry.get("runner", {}).get(
        "lock_state_dir", ".omo/_delivery/agent-workflows/locks"
    )


def ledger_path(registry: dict[str, Any]) -> Path:
    return WORKSPACE / registry.get("runner", {}).get(
        "ledger_path", ".omo/_delivery/agent-workflows/events.jsonl"
    )


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE))
    except ValueError:
        return str(path)


def sanitize_lock_name(scope: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", scope).strip("_") or "workspace"


def append_ledger_event(registry: dict[str, Any], event: dict[str, Any]) -> None:
    path = ledger_path(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ts": utc_now(), **event}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def acquire_locks(
    registry: dict[str, Any],
    scopes: list[str],
    run_id: str,
    actor: str,
    force: bool,
) -> list[str]:
    lock_dir = lock_state_dir(registry)
    lock_dir.mkdir(parents=True, exist_ok=True)
    acquired: list[str] = []
    acquired_paths: list[Path] = []
    ttl_hours = float(registry.get("runner", {}).get("lock_ttl_hours", 24))
    expires_at = (datetime.now(UTC) + timedelta(hours=ttl_hours)).replace(microsecond=0)
    try:
        for scope in scopes:
            lock_path = lock_dir / f"{sanitize_lock_name(scope)}.lock.yaml"
            payload = {
                "run_id": run_id,
                "actor": actor,
                "scope": scope,
                "created_at": utc_now(),
                "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
            }
            if lock_path.exists() and not force:
                existing = lock_path.read_text(encoding="utf-8").strip()
                raise WorkflowError(f"lock already held for {scope}: {lock_path}\n{existing}")
            with lock_path.open("w" if force else "x", encoding="utf-8") as handle:
                yaml.safe_dump(payload, handle, allow_unicode=True, sort_keys=False)
            acquired_paths.append(lock_path)
            acquired.append(display_path(lock_path))
    except Exception:
        for path in acquired_paths:
            path.unlink(missing_ok=True)
        raise
    return acquired


def release_locks(registry: dict[str, Any], run_id: str) -> list[str]:
    lock_dir = lock_state_dir(registry)
    released: list[str] = []
    if not lock_dir.exists():
        return released
    for lock_path in lock_dir.glob("*.lock.yaml"):
        try:
            payload = yaml.safe_load(lock_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if payload.get("run_id") == run_id:
            lock_path.unlink()
            released.append(display_path(lock_path))
    return released


def run_file_for(registry: dict[str, Any], run_id: str) -> Path:
    run_dir = run_state_dir(registry)
    direct = run_dir / f"{run_id}.yaml"
    if direct.exists():
        return direct
    matches = list(run_dir.glob(f"*{run_id}*.yaml")) if run_dir.exists() else []
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise WorkflowError(f"ambiguous run id {run_id}: {', '.join(str(p) for p in matches)}")
    raise WorkflowError(f"run not found: {run_id}")


def start_run(
    registry: dict[str, Any],
    workflow: dict[str, Any],
    context: dict[str, str],
    objective: str,
    dry_run: bool,
    force_lock: bool,
) -> dict[str, Any]:
    validate_agent_profile(registry, workflow, context.get("profile", ""), require=True)
    plan = workflow_plan(workflow, context)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{stamp}-{plan['id']}-{uuid.uuid4().hex[:8]}"
    context = {**context, "run_id": run_id}
    plan = workflow_plan(workflow, context)
    record = {
        "run_id": run_id,
        "workflow_id": plan["id"],
        "status": "active",
        "actor": context["actor"],
        "agent_profile": context.get("profile", ""),
        "objective": objective,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "context": context,
        "locks": [],
        "plan": plan,
        "evidence": [],
    }
    if dry_run:
        return record
    record["locks"] = acquire_locks(registry, plan["lock_scopes"], run_id, context["actor"], force_lock)
    run_dir = run_state_dir(registry)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_path = run_dir / f"{run_id}.yaml"
    run_path.write_text(yaml.safe_dump(record, allow_unicode=True, sort_keys=False), encoding="utf-8")
    record["path"] = display_path(run_path)
    append_ledger_event(
        registry,
        {
            "event": "agent_workflow_start",
            "run_id": run_id,
            "workflow_id": plan["id"],
            "actor": context["actor"],
            "agent_profile": context.get("profile", ""),
            "objective": objective,
            "path": record["path"],
            "locks": record["locks"],
        },
    )
    return record


def read_run(registry: dict[str, Any], run_id: str) -> tuple[Path, dict[str, Any]]:
    path = run_file_for(registry, run_id)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict) or not payload.get("run_id"):
        raise WorkflowError(f"invalid run file: {path}")
    return path, payload


def parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_run_records(registry: dict[str, Any]) -> dict[str, tuple[Path, dict[str, Any]]]:
    run_dir = run_state_dir(registry)
    records: dict[str, tuple[Path, dict[str, Any]]] = {}
    if not run_dir.exists():
        return records
    for path in sorted(run_dir.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            payload = {}
        run_id = payload.get("run_id") if isinstance(payload, dict) else None
        if run_id:
            records[str(run_id)] = (path, payload)
    return records


def load_lock_records(registry: dict[str, Any]) -> list[tuple[Path, dict[str, Any]]]:
    lock_dir = lock_state_dir(registry)
    records: list[tuple[Path, dict[str, Any]]] = []
    if not lock_dir.exists():
        return records
    for path in sorted(lock_dir.glob("*.lock.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            payload = {"run_id": None, "parse_error": True}
        records.append((path, payload if isinstance(payload, dict) else {"run_id": None, "parse_error": True}))
    return records


def ledger_mentions_run(registry: dict[str, Any], run_id: str) -> bool:
    path = ledger_path(registry)
    if not path.exists():
        return False
    needle = f'"run_id": "{run_id}"'
    return needle in path.read_text(encoding="utf-8", errors="replace")


def observe(registry: dict[str, Any], run_id: str | None, as_json: bool) -> int:
    runs = load_run_records(registry)
    locks = load_lock_records(registry)
    now = datetime.now(UTC)
    findings: list[dict[str, Any]] = []

    selected_runs = {run_id: runs[run_id]} if run_id and run_id in runs else runs
    if run_id and run_id not in runs:
        findings.append(
            {
                "severity": "halt",
                "kind": "run_missing",
                "message": f"run not found: {run_id}",
                "run_id": run_id,
            }
        )

    for lock_path, lock in locks:
        lock_run_id = str(lock.get("run_id") or "")
        if run_id and lock_run_id != run_id:
            continue
        lock_rel = display_path(lock_path)
        if lock.get("parse_error"):
            findings.append(
                {
                    "severity": "halt",
                    "kind": "lock_parse_error",
                    "message": f"lock file is not valid YAML: {lock_rel}",
                    "path": lock_rel,
                }
            )
            continue
        if not lock_run_id or lock_run_id not in runs:
            findings.append(
                {
                    "severity": "halt",
                    "kind": "orphan_lock",
                    "message": f"lock has no matching run record: {lock_rel}",
                    "path": lock_rel,
                    "run_id": lock_run_id or None,
                }
            )
            continue
        expires_at = parse_utc_timestamp(str(lock.get("expires_at") or ""))
        if expires_at and expires_at < now:
            findings.append(
                {
                    "severity": "escalate",
                    "kind": "expired_lock",
                    "message": f"lock expired: {lock_rel}",
                    "path": lock_rel,
                    "run_id": lock_run_id,
                    "expires_at": lock.get("expires_at"),
                }
            )
        run_status = runs[lock_run_id][1].get("status")
        if run_status in {"ok", "failed", "blocked"}:
            findings.append(
                {
                    "severity": "halt",
                    "kind": "closed_run_lock",
                    "message": f"closed run still holds a lock: {lock_rel}",
                    "path": lock_rel,
                    "run_id": lock_run_id,
                    "status": run_status,
                }
            )

    lock_paths_by_run: dict[str, set[str]] = {}
    for lock_path, lock in locks:
        lock_run_id = str(lock.get("run_id") or "")
        if lock_run_id:
            lock_paths_by_run.setdefault(lock_run_id, set()).add(display_path(lock_path))

    for current_run_id, (path, payload) in selected_runs.items():
        expected_locks = set(payload.get("locks") or [])
        if payload.get("status") == "active":
            missing_locks = sorted(expected_locks - lock_paths_by_run.get(current_run_id, set()))
            if missing_locks:
                findings.append(
                    {
                        "severity": "halt",
                        "kind": "active_run_missing_locks",
                        "message": f"active run is missing lock files: {current_run_id}",
                        "run_id": current_run_id,
                        "missing_locks": missing_locks,
                    }
                )
        if not ledger_mentions_run(registry, current_run_id):
            findings.append(
                {
                    "severity": "warn",
                    "kind": "ledger_missing_run",
                    "message": f"ledger has no event for run: {current_run_id}",
                    "run_id": current_run_id,
                    "path": display_path(path),
                }
            )

    severities = {finding["severity"] for finding in findings}
    decision = "escalate" if "escalate" in severities else "halt" if "halt" in severities else "continue"
    report = {
        "ok": decision == "continue",
        "decision": decision,
        "run_count": len(selected_runs),
        "lock_count": len([lock for _, lock in locks if not run_id or str(lock.get("run_id") or "") == run_id]),
        "ledger": display_path(ledger_path(registry)),
        "findings": findings,
    }
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"agent-workflow observe: {decision}")
        print(f"runs={report['run_count']} locks={report['lock_count']} ledger={report['ledger']}")
        for finding in findings:
            print(f"[{finding['severity'].upper()}] {finding['kind']}: {finding['message']}")
    return 0 if decision == "continue" else 1


def close_run(
    registry: dict[str, Any],
    run_id: str,
    status: str,
    evidence: list[str],
    release: bool,
) -> dict[str, Any]:
    path, payload = read_run(registry, run_id)
    payload["status"] = status
    payload["updated_at"] = utc_now()
    payload["closed_at"] = utc_now()
    payload.setdefault("evidence", [])
    payload["evidence"].extend(evidence)
    if release:
        payload["released_locks"] = release_locks(registry, payload["run_id"])
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    payload["path"] = display_path(path)
    append_ledger_event(
        registry,
        {
            "event": "agent_workflow_close",
            "run_id": payload["run_id"],
            "workflow_id": payload.get("workflow_id"),
            "status": status,
            "evidence": evidence,
            "released_locks": payload.get("released_locks", []),
        },
    )
    return payload


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
        lines.append(f"- `{item.get('mode')}` {item.get('id')}: `{command_display(item.get('command', []))}`")
    lines.extend(["", "## Evidence"])
    evidence = payload.get("evidence") or []
    if evidence:
        lines.extend(f"- {entry}" for entry in evidence)
    else:
        lines.append("- none yet")
    return "\n".join(lines)


def run_doctor_check(check_item: dict[str, Any]) -> dict[str, Any]:
    command = check_item["command"]
    env = os.environ.copy()
    # Nested `uv run` invocations inherit the runner's temporary VIRTUAL_ENV and
    # otherwise emit noisy mismatch warnings for project-local checks.
    env.pop("VIRTUAL_ENV", None)
    try:
        completed = subprocess.run(
            command,
            cwd=WORKSPACE,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        ok = completed.returncode == 0
        return {
            "id": check_item["id"],
            "description": check_item.get("description", ""),
            "required": bool(check_item.get("required", True)),
            "command": command_display(command),
            "ok": ok,
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip()[-1000:],
            "stderr": completed.stderr.strip()[-1000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "id": check_item["id"],
            "description": check_item.get("description", ""),
            "required": bool(check_item.get("required", True)),
            "command": command_display(command),
            "ok": False,
            "error": str(exc),
        }


def build_doctor_report(registry: dict[str, Any]) -> dict[str, Any]:
    integrations = integration_rows(registry)
    for integration in integrations:
        name = str(integration["name"])
        health = None
        health_command = integration.get("health_command")
        health_required = bool(integration.get("health_required", False))
        if isinstance(health_command, list) and health_command:
            health = run_doctor_check(
                {
                    "id": f"integration-{name}-health",
                    "description": f"Internal integration health check for {name}.",
                    "required": health_required,
                    "command": health_command,
                }
            )
        integration["health"] = health

    adapters = adapter_rows(registry)
    for adapter in adapters:
        name = str(adapter["name"])
        health = None
        health_command = adapter.get("health_command")
        health_required = bool(adapter.get("health_required", False))
        if isinstance(health_command, list) and health_command:
            health = run_doctor_check(
                {
                    "id": f"adapter-{name}-health",
                    "description": f"External adapter health check for {name}.",
                    "required": health_required,
                    "command": health_command,
                }
            )
        adapter["health"] = health
    checks = [run_doctor_check(item) for item in registry.get("doctor_checks", [])]
    required_integration_health = [
        integration["health"]
        for integration in integrations
        if integration.get("health_required") and isinstance(integration.get("health"), dict)
    ]
    required_adapter_health = [
        adapter["health"]
        for adapter in adapters
        if adapter.get("health_required") and isinstance(adapter.get("health"), dict)
    ]
    ok = all(
        (not item["required"]) or item["ok"]
        for item in [*checks, *required_integration_health, *required_adapter_health]
    )
    return {
        "ok": ok,
        "registry": str(REGISTRY_PATH.relative_to(WORKSPACE)),
        "integrations": integrations,
        "adapters": adapters,
        "checks": checks,
    }


def print_doctor_report(report: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    print(f"registry: {report['registry']}")
    for integration in report["integrations"]:
        health = integration.get("health")
        health_status = ""
        if isinstance(health, dict):
            label = "PASS" if health["ok"] else ("FAIL" if integration.get("health_required") else "WARN")
            health_status = f" health={label}"
        print(
            f"{integration['name']:<14} {integration['status']:<12} "
            f"{integration['authority']:<16}{health_status}"
        )
    for adapter in report["adapters"]:
        status = "available" if adapter["available"] else "missing"
        suffix = f" ({adapter['path']})" if adapter["path"] else ""
        health = adapter.get("health")
        if isinstance(health, dict):
            health_status = "PASS" if health["ok"] else ("FAIL" if adapter.get("health_required") else "WARN")
            suffix += f" health={health_status}"
        print(f"{adapter['name']:<14} {status}{suffix}")
    for item in report["checks"]:
        status = "PASS" if item["ok"] else ("WARN" if not item["required"] else "FAIL")
        print(f"[{status}] {item['id']} :: {item['command']}")
        if not item["ok"] and item.get("stderr"):
            print(item["stderr"], file=sys.stderr)


def doctor(registry: dict[str, Any], as_json: bool) -> int:
    report = build_doctor_report(registry)
    print_doctor_report(report, as_json)
    return 0 if report["ok"] else 1


def health_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for row in rows:
        health = row.get("health")
        summary.append(
            {
                "name": row.get("name"),
                "status": row.get("status"),
                "authority": row.get("authority"),
                "required": bool(row.get("health_required", False)),
                "health_ok": health.get("ok") if isinstance(health, dict) else None,
                "command": health.get("command") if isinstance(health, dict) else command_display(row.get("health_command", [])),
                "advisory": not bool(row.get("health_required", False)),
            }
        )
    return summary


def check_summary(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": check.get("id"),
            "required": bool(check.get("required", True)),
            "ok": bool(check.get("ok", False)),
            "command": check.get("command"),
        }
        for check in checks
    ]


def bootstrap_report(registry: dict[str, Any], include_health: bool) -> dict[str, Any]:
    errors, warnings = lint_registry(registry)
    doctor_report = build_doctor_report(registry) if include_health else None
    integrations = (
        doctor_report["integrations"] if isinstance(doctor_report, dict) else integration_rows(registry)
    )
    adapters = doctor_report["adapters"] if isinstance(doctor_report, dict) else adapter_rows(registry)
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
            "start": "uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> --profile <agent-profile> --objective \"<summary>\"",
            "doctor": "uv run --with pyyaml python bin/agent-workflow.py doctor",
            "gate": "make gac-local-gate",
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
        print(f"  {row['id']:<20} workflows={len(row['allowed_workflows'])} lanes={','.join(row['can_write_lanes'])}")
    print("\ninternal integrations:")
    for row in report["integrations"]:
        print(f"  {row['name']:<14} {row['authority']:<16} owner={row['owner']}")
    print("\nexternal adapters:")
    for row in report["adapters"]:
        availability = "available" if row["available"] else "missing"
        command = row["command"] or row["skill"] or "-"
        print(f"  {row['name']:<14} {row['authority']:<16} {availability} command={command}")
    print("\nnext:")
    for command in report["next_commands"].values():
        print(f"  {command}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run executable project governance workflows")
    parser.add_argument("--registry", default=str(REGISTRY_PATH), help="Workflow registry path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_lint = sub.add_parser("lint", help="Validate the workflow registry")
    p_lint.add_argument("--json", action="store_true")

    p_doctor = sub.add_parser("doctor", help="Report optional adapter availability")
    p_doctor.add_argument("--json", action="store_true")

    p_observe = sub.add_parser("observe", help="Read-only observer audit for workflow runs and locks")
    p_observe.add_argument("run_id", nargs="?")
    p_observe.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list", help="List workflows")
    p_list.add_argument("--json", action="store_true")

    p_agents = sub.add_parser("agents", help="List registered agent profiles")
    p_agents.add_argument("--json", action="store_true")

    p_adapters = sub.add_parser("adapters", help="List external adapter contracts")
    p_adapters.add_argument("--json", action="store_true")

    p_integrations = sub.add_parser("integrations", help="List internal integration contracts")
    p_integrations.add_argument("--json", action="store_true")

    p_bootstrap = sub.add_parser("bootstrap", help="Show one-shot startup context for agents")
    p_bootstrap.add_argument("--json", action="store_true")
    p_bootstrap.add_argument("--skip-health", action="store_true")

    p_context = sub.add_parser("context", help="Alias for bootstrap")
    p_context.add_argument("--json", action="store_true")
    p_context.add_argument("--skip-health", action="store_true")

    p_show = sub.add_parser("show", help="Show a workflow plan")
    p_show.add_argument("workflow_id")
    p_show.add_argument("--project", default="")
    p_show.add_argument("--format", default="openspec")
    p_show.add_argument("--source-file", default="")
    p_show.add_argument("--run-id", default="")
    p_show.add_argument("--profile", default="")
    p_show.add_argument("--json", action="store_true")

    p_run = sub.add_parser("run", help="Run or print a workflow stage")
    p_run.add_argument("workflow_id")
    p_run.add_argument("--stage", default="preflight")
    p_run.add_argument("--execute", action="store_true", help="Actually run non-manual commands")
    p_run.add_argument("--project", default="")
    p_run.add_argument("--format", default="openspec")
    p_run.add_argument("--source-file", default="")
    p_run.add_argument("--run-id", default="")
    p_run.add_argument("--profile", default="")
    p_run.add_argument("--json", action="store_true")

    p_start = sub.add_parser("start", help="Create a resumable workflow run record")
    p_start.add_argument("workflow_id")
    p_start.add_argument("--project", default="")
    p_start.add_argument("--format", default="openspec")
    p_start.add_argument("--source-file", default="")
    p_start.add_argument("--actor", default=os.environ.get("USER", "agent"))
    p_start.add_argument("--profile", default="")
    p_start.add_argument("--objective", default="")
    p_start.add_argument("--dry-run", action="store_true")
    p_start.add_argument("--force-lock", action="store_true")
    p_start.add_argument("--json", action="store_true")

    p_resume = sub.add_parser("resume", help="Show a resumable run plan")
    p_resume.add_argument("run_id")
    p_resume.add_argument("--json", action="store_true")

    p_show_run = sub.add_parser("show-run", help="Show a run record")
    p_show_run.add_argument("run_id")
    p_show_run.add_argument("--json", action="store_true")

    p_handoff = sub.add_parser("handoff", help="Print a compression-safe handoff note")
    p_handoff.add_argument("run_id")
    p_handoff.add_argument("--json", action="store_true")

    p_close = sub.add_parser("close", help="Close a workflow run")
    p_close.add_argument("run_id")
    p_close.add_argument("--status", choices=["ok", "failed", "blocked"], required=True)
    p_close.add_argument("--evidence", action="append", default=[])
    p_close.add_argument("--keep-locks", action="store_true")
    p_close.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        registry = load_registry(Path(args.registry))
        if args.command == "lint":
            errors, warnings = lint_registry(registry)
            print_lint(errors, warnings, args.json)
            return 0 if not errors else 1
        if args.command == "doctor":
            return doctor(registry, args.json)
        if args.command == "observe":
            return observe(registry, args.run_id, args.json)
        if args.command == "list":
            list_workflows(registry, args.json)
            return 0
        if args.command == "agents":
            list_agents(registry, args.json)
            return 0
        if args.command == "adapters":
            list_adapters(registry, args.json)
            return 0
        if args.command == "integrations":
            list_integrations(registry, args.json)
            return 0
        if args.command in {"bootstrap", "context"}:
            report = bootstrap_report(registry, not args.skip_health)
            print_bootstrap_report(report, args.json)
            return 0 if report["ok"] else 1
        if args.command == "show":
            workflow = workflow_by_id(registry, args.workflow_id)
            context = context_from_args(args)
            validate_agent_profile(registry, workflow, context["profile"], require=False)
            print_plan(workflow_plan(workflow, context), args.json)
            return 0
        if args.command == "run":
            workflow = workflow_by_id(registry, args.workflow_id)
            context = context_from_args(args)
            validate_agent_profile(registry, workflow, context["profile"], require=args.execute)
            return run_stage(workflow, args.stage, context, args.execute, args.json)
        if args.command == "start":
            workflow = workflow_by_id(registry, args.workflow_id)
            record = start_run(
                registry,
                workflow,
                context_from_args(args),
                args.objective,
                args.dry_run,
                args.force_lock,
            )
            if args.json:
                print(json.dumps(record, ensure_ascii=False, indent=2))
            else:
                print(f"started {record['run_id']}")
                if record.get("path"):
                    print(record["path"])
            return 0
        if args.command in {"resume", "show-run"}:
            _, payload = read_run(registry, args.run_id)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_plan(payload["plan"], False)
            return 0
        if args.command == "handoff":
            _, payload = read_run(registry, args.run_id)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(handoff_markdown(payload))
            return 0
        if args.command == "close":
            payload = close_run(registry, args.run_id, args.status, args.evidence, not args.keep_locks)
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"closed {payload['run_id']} as {payload['status']}")
            return 0
    except WorkflowError as exc:
        print(f"agent-workflow: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
