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


def context_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {
        "project": str(getattr(args, "project", "") or ""),
        "format": str(getattr(args, "format", "") or "openspec"),
        "source_file": str(getattr(args, "source_file", "") or ""),
        "run_id": str(getattr(args, "run_id", "") or ""),
        "actor": str(getattr(args, "actor", "") or "agent"),
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

    for name, adapter in (registry.get("external_patterns") or {}).items():
        command = adapter.get("command") if isinstance(adapter, dict) else None
        if command and shutil.which(str(command)) is None:
            warnings.append(f"optional adapter not installed: {name} ({command})")
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
    rows = [
        {
            "id": workflow["id"],
            "title": workflow.get("title", ""),
            "lanes": workflow.get("allowed_lanes", []),
        }
        for workflow in registry.get("workflows", [])
    ]
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for row in rows:
        print(f"{row['id']:<28} {row['title']} [{', '.join(row['lanes'])}]")


def workflow_plan(workflow: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    resolved = substitute(workflow, context)
    return {
        "id": resolved["id"],
        "title": resolved.get("title", ""),
        "purpose": resolved.get("purpose", ""),
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


def doctor(registry: dict[str, Any], as_json: bool) -> int:
    adapters = []
    for name, adapter in (registry.get("external_patterns") or {}).items():
        command = adapter.get("command") if isinstance(adapter, dict) else None
        found = shutil.which(str(command)) if command else None
        adapters.append(
            {
                "name": name,
                "status": adapter.get("status") if isinstance(adapter, dict) else None,
                "command": command,
                "available": bool(found) if command else True,
                "path": found,
            }
        )
    checks = [run_doctor_check(item) for item in registry.get("doctor_checks", [])]
    ok = all((not item["required"]) or item["ok"] for item in checks)
    report = {
        "ok": ok,
        "registry": str(REGISTRY_PATH.relative_to(WORKSPACE)),
        "adapters": adapters,
        "checks": checks,
    }
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if ok else 1
    print(f"registry: {report['registry']}")
    for adapter in adapters:
        status = "available" if adapter["available"] else "missing"
        suffix = f" ({adapter['path']})" if adapter["path"] else ""
        print(f"{adapter['name']:<14} {status}{suffix}")
    for item in checks:
        status = "PASS" if item["ok"] else ("WARN" if not item["required"] else "FAIL")
        print(f"[{status}] {item['id']} :: {item['command']}")
        if not item["ok"] and item.get("stderr"):
            print(item["stderr"], file=sys.stderr)
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run executable project governance workflows")
    parser.add_argument("--registry", default=str(REGISTRY_PATH), help="Workflow registry path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_lint = sub.add_parser("lint", help="Validate the workflow registry")
    p_lint.add_argument("--json", action="store_true")

    p_doctor = sub.add_parser("doctor", help="Report optional adapter availability")
    p_doctor.add_argument("--json", action="store_true")

    p_list = sub.add_parser("list", help="List workflows")
    p_list.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="Show a workflow plan")
    p_show.add_argument("workflow_id")
    p_show.add_argument("--project", default="")
    p_show.add_argument("--format", default="openspec")
    p_show.add_argument("--source-file", default="")
    p_show.add_argument("--run-id", default="")
    p_show.add_argument("--json", action="store_true")

    p_run = sub.add_parser("run", help="Run or print a workflow stage")
    p_run.add_argument("workflow_id")
    p_run.add_argument("--stage", default="preflight")
    p_run.add_argument("--execute", action="store_true", help="Actually run non-manual commands")
    p_run.add_argument("--project", default="")
    p_run.add_argument("--format", default="openspec")
    p_run.add_argument("--source-file", default="")
    p_run.add_argument("--run-id", default="")
    p_run.add_argument("--json", action="store_true")

    p_start = sub.add_parser("start", help="Create a resumable workflow run record")
    p_start.add_argument("workflow_id")
    p_start.add_argument("--project", default="")
    p_start.add_argument("--format", default="openspec")
    p_start.add_argument("--source-file", default="")
    p_start.add_argument("--actor", default=os.environ.get("USER", "agent"))
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
        if args.command == "list":
            list_workflows(registry, args.json)
            return 0
        if args.command == "show":
            workflow = workflow_by_id(registry, args.workflow_id)
            print_plan(workflow_plan(workflow, context_from_args(args)), args.json)
            return 0
        if args.command == "run":
            workflow = workflow_by_id(registry, args.workflow_id)
            return run_stage(workflow, args.stage, context_from_args(args), args.execute, args.json)
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
