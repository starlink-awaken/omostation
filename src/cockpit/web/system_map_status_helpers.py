"""cockpit system-map project status/coverage/verification helpers. Split from api_system_map.py."""

from __future__ import annotations

import json
import os
import re
import socket
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query

from cockpit import compat
from cockpit.web.api_system_map_catalog import (
    CAPABILITY_TO_PAGE,
    CLI_ENTRYPOINTS,
    COCKPIT_PAGES,
    NEXT_CONFIGS,
    OPERATING_PLAYBOOKS,
    PACKAGE_MANIFESTS,
    PAGE_CAPABILITY_LINKS,
    PAGE_OPERATOR_ACTIONS,
    PAGE_PROJECT_LINKS,
    PROJECT_COVERAGE_DIMENSIONS,
    PROJECT_DOC_FILES,
    PROJECT_PORT_ALIASES,
    PROJECT_TO_PAGE,
    ROADMAP_ITEMS,
    SERVICE_ENTRYPOINTS,
    STATIC_FRONTEND_MARKERS,
    USAGE_PATHS,
    VITE_CONFIGS,
)
from cockpit.web.api_system_map_io_commands import (
    MAX_SOURCE_PREVIEW_BYTES,
    _command_with_cwd,
    _exists_any,
    _first_action,
    _first_matching_command,
    _is_port_listening,
    _line_number,
    _package_scripts,
    _parse_source_ref_target,
    _path_state,
    _port_probe_command,
    _port_registry_search_command,
    _project_actions,
    _project_inventory_command,
    _project_ports,
    _project_start_command,
    _project_triage_commands,
    _project_verify_command,
    _read_json,
    _read_text,
    _read_text_lossy,
    _read_yaml,
    _recover_port_registry,
    _source_ref,
    _source_ref_for_id,
    _triage_command,
    _triage_task_posture,
    _workflow_evidence_search_command,
    build_source_ref_preview,
)

VERIFICATION_EVIDENCE_MAX_AGE_HOURS = 30 * 24
RUNTIME_EVIDENCE_MAX_AGE_HOURS = 24

__all__ = [
    "VERIFICATION_EVIDENCE_MAX_AGE_HOURS",
    "RUNTIME_EVIDENCE_MAX_AGE_HOURS",
    "_evidence_freshness",
    "_attach_evidence_freshness",
    "_latest_project_verification",
    "_project_workflow_lifecycle",
    "_commands_from_agents",
    "_project_path",
    "_project_source_location",
    "_resolved_physical_location",
    "_read_package_manifest",
    "_runtime_profile",
    "_project_runtime_status",
    "_project_operational_status",
    "_parse_capability_domains",
    "_parse_markdown_rows",
    "_build_layers",
    "_project_source_refs",
    "_coverage_check",
    "_latest_controlled_verification",
    "_project_coverage_checks",
    "_project_diagnostics",
    "_project_portfolio_state",
]


def _evidence_freshness(timestamp: Any, max_age_hours: int, now: datetime | None = None) -> dict[str, Any]:
    """Return explicit freshness metadata for durable evidence timestamps."""
    raw_timestamp = str(timestamp or "").strip()
    max_age_seconds = max_age_hours * 60 * 60
    if not raw_timestamp:
        return {
            "status": "unknown",
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
            "next_action": "补录带时间戳的持久证据。",
        }
    try:
        recorded_at = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        if recorded_at.tzinfo is None:
            recorded_at = recorded_at.replace(tzinfo=UTC)
        recorded_at = recorded_at.astimezone(UTC)
    except ValueError:
        return {
            "status": "unknown",
            "age_seconds": None,
            "max_age_seconds": max_age_seconds,
            "next_action": "修正证据时间戳后重新留证。",
        }
    age_seconds = max(0, int(((now or datetime.now(UTC)) - recorded_at).total_seconds()))
    fresh = age_seconds <= max_age_seconds
    return {
        "status": "fresh" if fresh else "stale",
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "recorded_at": recorded_at.isoformat(),
        "next_action": "保持证据新鲜。" if fresh else "重新执行并留存最新证据。",
    }


def _attach_evidence_freshness(evidence: dict[str, Any], max_age_hours: int) -> dict[str, Any]:
    result = dict(evidence)
    result["freshness"] = _evidence_freshness(result.get("ts"), max_age_hours)
    return result


def _latest_project_verification(project_id: str, project_path: Path, operational: dict[str, Any]) -> dict[str, Any]:
    events_path = compat.WORKSPACE_ROOT / ".omo" / "_delivery" / "agent-workflows" / "events.jsonl"
    project_prefix = f"projects/{project_id}"
    claims_by_run: dict[str, set[str]] = defaultdict(set)
    verify_events: list[dict[str, Any]] = []
    closeout_events: list[dict[str, Any]] = []

    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []

    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        run_id = event.get("run_id")
        if not run_id:
            continue
        if event.get("event") == "agent_workflow_claim":
            for path in event.get("paths") or []:
                claims_by_run[run_id].add(str(path))
        if event.get("event") == "agent_workflow_verify":
            verify_events.append(event)
        if event.get("event") in {"agent_workflow_closeout", "agent_workflow_close"}:
            closeout_events.append(event)

    for event in reversed(verify_events):
        run_id = event.get("run_id", "")
        surfaces = set(str(path) for path in (event.get("changed_files") or []))
        surfaces.update(claims_by_run.get(run_id, set()))
        if any(path == project_prefix or path.startswith(f"{project_prefix}/") for path in surfaces):
            result = {
                "status": "verified" if event.get("ok") else "failed",
                "run_id": run_id,
                "ts": event.get("ts"),
                "checks": len(event.get("checks") or []),
                "command": None,
                "source": "agent_workflow",
            }
            closeout = next((item for item in reversed(closeout_events) if item.get("run_id") == run_id), None)
            if closeout:
                result["closeout_status"] = "closed"
                result["closeout_ref"] = closeout.get("artifact_ref") or closeout.get("source_ref")
            return result

    # Older or interrupted runs may have a durable YAML run record but no
    # events.jsonl entry. Surface that evidence instead of silently downgrading
    # the project to "documented".
    runs_dir = compat.WORKSPACE_ROOT / ".omo" / "_delivery" / "agent-workflows" / "runs"
    try:
        run_paths = sorted(runs_dir.glob("*.yaml"), key=lambda path: path.stat().st_mtime, reverse=True)
    except OSError:
        run_paths = []
    for run_path in run_paths:
        try:
            run = yaml.safe_load(run_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        surfaces = {str(path) for claim in run.get("claims") or [] for path in claim.get("paths") or []}
        if not any(path == project_prefix or path.startswith(f"{project_prefix}/") for path in surfaces):
            continue
        run_status = str(run.get("status", "")).lower()
        if run_status in {"ok", "completed", "complete", "closed", "succeeded", "success"}:
            status = "verified"
        elif run_status in {"blocked", "failed", "error"}:
            status = "failed"
        else:
            continue
        evidence = [str(item) for item in run.get("evidence") or []]
        checks = sum(1 for item in evidence if "agent-workflow verify:" in item)
        result = {
            "status": status,
            "run_id": run.get("run_id") or run_path.stem,
            "ts": run.get("updated_at") or run.get("closed_at") or run.get("created_at"),
            "checks": checks,
            "command": None,
            "source": "agent_workflow_run",
        }
        if run.get("closed_at") or run_status in {"ok", "closed", "complete", "completed"}:
            result["closeout_status"] = "closed"
            result["closeout_ref"] = str(run_path.relative_to(compat.WORKSPACE_ROOT))
        return result

    # A Cockpit-controlled verification is also durable OMO evidence. Keep it
    # in the same project posture so TaskCenter and SystemMap do not disagree.
    task_paths: list[Path] = []
    task_ids = [f"cockpit-action-{project_id}-copy-verify-command"]
    triage_posture = _triage_task_posture(project_id, "verification-rerun")
    if triage_posture.get("task_id"):
        task_ids.append(str(triage_posture["task_id"]))
    for group in ("active", "done", "archived/done"):
        for task_id in task_ids:
            task_path = compat.WORKSPACE_ROOT / ".omo" / "tasks" / group / f"{task_id}.yaml"
            if task_path.is_file():
                task_paths.append(task_path)
    for task_path in sorted(task_paths, key=lambda path: path.stat().st_mtime, reverse=True):
        try:
            task = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        audit = (task.get("metadata") or {}).get("execution_audit") or {}
        if not isinstance(audit, dict) or "exit_code" not in audit:
            continue
        exit_code = audit.get("exit_code")
        return {
            "status": "verified" if exit_code == 0 else "failed",
            "run_id": task.get("id") or task_path.stem,
            "ts": audit.get("recorded_at"),
            "checks": 1,
            "command": audit.get("command"),
            "source": "omo_task_execution",
            "log_ref": audit.get("log_ref"),
            "actor": audit.get("actor"),
            "closeout_status": "closed" if audit.get("closeout_ref") else "missing",
            "closeout_ref": audit.get("closeout_ref"),
        }

    verify_command = _project_verify_command(
        project_path,
        list(operational.get("commands") or []),
        list(operational.get("manifests") or []),
    )
    if verify_command:
        return {
            "status": "documented",
            "run_id": None,
            "ts": None,
            "checks": 0,
            "command": verify_command,
            "source": "project_commands",
        }

    return {
        "status": "unknown",
        "run_id": None,
        "ts": None,
        "checks": 0,
        "command": None,
        "source": "missing",
        "closeout_status": "missing",
        "closeout_ref": None,
    }


def _project_workflow_lifecycle(project_id: str) -> dict[str, Any]:
    events_path = compat.WORKSPACE_ROOT / ".omo" / "_delivery" / "agent-workflows" / "events.jsonl"
    project_prefix = f"projects/{project_id}"
    events_by_run: dict[str, list[dict[str, Any]]] = defaultdict(list)

    try:
        lines = events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {
            "latest_run_id": None,
            "latest_status": "unknown",
            "latest_ts": None,
            "runs": [],
            "summary": {"runs": 0, "verified": 0, "failed": 0, "active": 0},
        }

    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        run_id = event.get("run_id")
        if run_id:
            events_by_run[str(run_id)].append(event)

    runs: list[dict[str, Any]] = []
    for run_id, events in events_by_run.items():
        surfaces: set[str] = set()
        for event in events:
            surfaces.update(str(path) for path in (event.get("paths") or []))
            surfaces.update(str(path) for path in (event.get("changed_files") or []))
        project_surfaces = sorted(
            path for path in surfaces if path == project_prefix or path.startswith(f"{project_prefix}/")
        )
        if not project_surfaces:
            continue

        timeline: list[dict[str, Any]] = []
        start_event = next((event for event in events if event.get("event") == "agent_workflow_start"), None)
        workflow_id = start_event.get("workflow_id") if start_event else "unknown"
        objective = start_event.get("objective") if start_event else ""
        status = "active"
        verify_status = "unknown"
        verify_checks = 0
        latest_ts = events[-1].get("ts")

        for event in events:
            event_type = event.get("event")
            if event_type == "agent_workflow_start":
                timeline.append(
                    {
                        "type": "start",
                        "status": "started",
                        "ts": event.get("ts"),
                        "summary": event.get("objective") or workflow_id,
                    }
                )
            elif event_type == "agent_workflow_claim":
                claimed_paths = [
                    str(path)
                    for path in (event.get("paths") or [])
                    if str(path) == project_prefix or str(path).startswith(f"{project_prefix}/")
                ]
                if claimed_paths:
                    timeline.append(
                        {
                            "type": "claim",
                            "status": "claimed",
                            "ts": event.get("ts"),
                            "summary": f"claimed {len(claimed_paths)} path(s)",
                            "paths": claimed_paths[:6],
                        }
                    )
            elif event_type == "agent_workflow_verify":
                changed = [
                    str(path)
                    for path in (event.get("changed_files") or [])
                    if str(path) == project_prefix or str(path).startswith(f"{project_prefix}/")
                ]
                if changed:
                    ok = bool(event.get("ok"))
                    verify_status = "verified" if ok else "failed"
                    verify_checks = len(event.get("checks") or [])
                    status = verify_status
                    timeline.append(
                        {
                            "type": "verify",
                            "status": verify_status,
                            "ts": event.get("ts"),
                            "summary": f"checks={verify_checks}",
                            "paths": changed[:6],
                        }
                    )
            elif event_type == "agent_workflow_closeout":
                ok = bool(event.get("ok"))
                status = "closed" if ok else "failed"
                timeline.append(
                    {
                        "type": "closeout",
                        "status": status,
                        "ts": event.get("ts"),
                        "summary": f"status={event.get('status', 'unknown')}",
                    }
                )

        runs.append(
            {
                "run_id": run_id,
                "workflow_id": workflow_id,
                "objective": objective or "",
                "status": status,
                "verify_status": verify_status,
                "verify_checks": verify_checks,
                "latest_ts": latest_ts,
                "paths": project_surfaces[:8],
                "events": timeline[-8:],
            }
        )

    runs.sort(key=lambda item: item.get("latest_ts") or "", reverse=True)
    visible_runs = runs[:4]
    return {
        "latest_run_id": visible_runs[0]["run_id"] if visible_runs else None,
        "latest_status": visible_runs[0]["status"] if visible_runs else "unknown",
        "latest_ts": visible_runs[0]["latest_ts"] if visible_runs else None,
        "runs": visible_runs,
        "summary": {
            "runs": len(runs),
            "verified": sum(1 for run in runs if run["verify_status"] == "verified"),
            "failed": sum(1 for run in runs if run["verify_status"] == "failed" or run["status"] == "failed"),
            "active": sum(1 for run in runs if run["status"] == "active"),
        },
    }


def _commands_from_agents(path: Path, limit: int = 4) -> list[str]:
    text = ""
    for filename in ("AGENTS.md", "CLAUDE.md", "README.md"):
        text = _read_text(path / filename)
        if text:
            break
    if not text:
        return []

    match = re.search(r"^\s*##\s+.*?(?:Commands|命令).*?```(?:\w+)?\s*(.*?)```", text, re.DOTALL | re.MULTILINE)
    if not match:
        return []

    commands: list[str] = []
    for raw_line in match.group(1).splitlines():
        command = raw_line.strip()
        if command and not command.startswith("#"):
            commands.append(command)
        if len(commands) >= limit:
            break
    return commands


def _project_path(project_id: str, project_data: dict[str, Any] | None = None) -> Path:
    data = project_data or {}
    path_env = data.get("path_env")
    if isinstance(path_env, str) and path_env.strip():
        configured = os.environ.get(path_env.strip())
        if configured:
            return Path(configured).expanduser()
    if project_id == "cockpit-ui":
        configured = os.environ.get("COCKPIT_UI_ROOT") or os.environ.get("COCKPIT_UI_DIST")
        if configured:
            root = Path(configured).expanduser()
            return root.parent if root.name == "dist" else root
        return compat.WORKSPACE_ROOT / "projects" / "cockpit-ui"
    storage = data.get("storage")
    if isinstance(storage, str) and storage.strip():
        return Path(storage).expanduser()

    physical_location = data.get("physical_location")
    if isinstance(physical_location, str) and physical_location.strip():
        source_path = _resolved_physical_location(physical_location)
        return source_path.parent if source_path.is_file() else source_path

    return compat.WORKSPACE_ROOT / "projects" / project_id


def _project_source_location(project_data: dict[str, Any] | None = None) -> Path | None:
    data = project_data or {}
    if data.get("id") == "cockpit-ui":
        return _project_path("cockpit-ui", data)
    physical_location = data.get("physical_location")
    if isinstance(physical_location, str) and physical_location.strip():
        return _resolved_physical_location(physical_location)
    storage = data.get("storage")
    if isinstance(storage, str) and storage.strip():
        return Path(storage).expanduser()
    return None


def _resolved_physical_location(location: str) -> Path:
    declared = (compat.WORKSPACE_ROOT / location).expanduser()
    if declared.exists():
        return declared
    # P76 moved bin implementations under bin/gac; preserve the registry's
    # declared path while resolving the known relocation for runtime evidence.
    relocated = compat.WORKSPACE_ROOT / "bin" / "gac" / Path(location).name
    return relocated if relocated.exists() else declared


def _read_package_manifest(project_path: Path) -> dict[str, Any]:
    manifest = _read_json(project_path / "package.json")
    return manifest if isinstance(manifest, dict) else {}


def _runtime_profile(
    project_id: str,
    project_data: dict[str, Any],
    project_path: Path,
    operational: dict[str, Any],
    ports: list[dict[str, Any]],
) -> dict[str, Any]:
    role_text = str(project_data.get("role") or "").lower()
    stack_text = str(project_data.get("stack") or "").lower()
    commands = operational.get("commands") or []
    commands_text = " ".join(commands).lower()
    package_manifest = _read_package_manifest(project_path)
    scripts = package_manifest.get("scripts") if isinstance(package_manifest.get("scripts"), dict) else {}
    script_text = " ".join(f"{key} {value}" for key, value in scripts.items() if isinstance(value, str)).lower()  # type: ignore[union-attr]
    manifests = {item.get("name") for item in (operational.get("manifests") or [])}

    if project_id == "bus-foundation":
        return {
            "profile": "library",
            "needs_runtime": False,
            "probe_reason": "bus-foundation 是嵌入式库；/metrics 仅在调用 enable_metrics() 时按需开启，没有独立常驻服务。",
        }

    if project_id == "omo":
        return {
            "profile": "converged",
            "needs_runtime": False,
            "probe_reason": "OMO 历史 dashboard 已收敛到 Cockpit /api/omos/status；9190 是历史入口，9100 是外部 webhook 目标，不属于 OMO 常驻服务。",
        }

    if ports and not any(port.get("probeable", True) for port in ports):
        return {
            "profile": "stdio",
            "needs_runtime": False,
            "probe_reason": "仅登记 stdio/deprecated 传输，不存在可用 TCP 监听探针。",
        }

    if ports:
        return {
            "profile": "service",
            "needs_runtime": True,
            "probe_reason": "已登记可观测端口，可直接用监听结果判断运行状态。",
        }

    if "docker-compose.yml" in manifests:
        return {
            "profile": "service",
            "needs_runtime": True,
            "probe_reason": "存在 compose 运行清单，但当前缺少端口登记。",
        }

    if _exists_any(project_path, VITE_CONFIGS) or _exists_any(project_path, STATIC_FRONTEND_MARKERS):
        return {
            "profile": "static",
            "needs_runtime": False,
            "probe_reason": "检测到 Vite/静态前端入口，按需启动开发服务器，不作为常驻运行探针。",
        }

    if _exists_any(project_path, NEXT_CONFIGS):
        return {
            "profile": "service",
            "needs_runtime": True,
            "probe_reason": "检测到 Next.js 应用配置，通常需要显式启动并登记访问端口。",
        }

    if _exists_any(project_path, SERVICE_ENTRYPOINTS) or any(
        token in f"{commands_text} {script_text}"
        for token in ("uvicorn", "gunicorn", "fastapi", "server.ts", "server.py", "api/server", "dashboard_server")
    ):
        return {
            "profile": "service",
            "needs_runtime": True,
            "probe_reason": "检测到服务入口或启动脚本，但尚未登记运行端口。",
        }

    if _exists_any(project_path, CLI_ENTRYPOINTS) or "cli" in role_text or "cli" in commands_text:
        return {
            "profile": "cli",
            "needs_runtime": False,
            "probe_reason": "检测到 CLI 入口，命令按需执行即可，不需要常驻探针。",
        }

    if "pyproject.toml" in manifests:
        return {
            "profile": "library",
            "needs_runtime": False,
            "probe_reason": "当前更像库/框架型 Python 项目，主要靠构建与测试验证，而不是常驻服务端口。",
        }

    if "package.json" in manifests and any(
        token in f"{role_text} {stack_text}" for token in ("ui", "frontend", "前端")
    ):
        return {
            "profile": "static",
            "needs_runtime": False,
            "probe_reason": "项目角色更接近前端表现层，端口只在本地调试时按需出现。",
        }

    if any(token in f"{role_text} {stack_text}" for token in ("sdk", "framework", "monorepo", "库", "框架")):
        return {
            "profile": "library",
            "needs_runtime": False,
            "probe_reason": "项目描述偏向框架/SDK/monorepo 形态，不以常驻运行探针为主。",
        }

    return {
        "profile": "unknown",
        "needs_runtime": True,
        "probe_reason": "尚未识别运行形态；如果该项目需要服务进程，请补端口注册，否则补充无需常驻的依据。",
    }


def _project_runtime_status(
    project_id: str,
    project_data: dict[str, Any],
    operational: dict[str, Any],
    port_registry: dict[str, Any],
    port_registry_path: Path,
) -> dict[str, Any]:
    project_path = _project_path(project_id, project_data)
    ports = _project_ports(project_id, port_registry, port_registry_path, _project_path(project_id, project_data))
    latest_verification = _attach_evidence_freshness(
        _latest_project_verification(project_id, project_path, operational),
        VERIFICATION_EVIDENCE_MAX_AGE_HOURS,
    )
    probeable_ports = [port for port in ports if port.get("probeable", True)]
    listening_count = sum(1 for port in probeable_ports if port.get("listening") is True)
    profile = _runtime_profile(project_id, project_data, project_path, operational, ports)
    probe_task = _triage_task_posture(project_id, "runtime-check-ports")
    probe_audit = probe_task.get("execution_audit") or {}
    if isinstance(probe_audit, dict):
        probe_task = dict(probe_task)
        probe_task["freshness"] = _evidence_freshness(probe_audit.get("recorded_at"), RUNTIME_EVIDENCE_MAX_AGE_HOURS)

    if not profile["needs_runtime"]:
        status = "not_applicable"
        probe_reason = profile["probe_reason"]
    elif probeable_ports and listening_count:
        status = "running"
        probe_reason = "已探测到登记端口正在监听。"
    elif probeable_ports:
        status = "stopped"
        probe_reason = "已登记端口但当前未监听，需要人工确认是否应启动。"
    elif ports and not profile["needs_runtime"]:
        status = "not_applicable"
        probe_reason = profile["probe_reason"]
    elif not profile["needs_runtime"]:
        status = "not_applicable"
        probe_reason = profile["probe_reason"]
    else:
        status = "unobserved"
        probe_reason = profile["probe_reason"]

    return {
        "status": status,
        "profile": profile["profile"],
        "needs_runtime": profile["needs_runtime"],
        "probe_reason": probe_reason,
        "checked_at": datetime.now(UTC).isoformat(),
        "probe_source": "registered_port_socket" if probeable_ports else "runtime_profile",
        "probe_task": probe_task,
        "ports": ports,
        "listening_count": listening_count,
        "latest_verification": latest_verification,
    }


def _project_operational_status(
    project_id: str,
    project_data: dict[str, Any] | None = None,
    project_path: Path | None = None,
) -> dict[str, Any]:
    data = project_data or {}
    path = project_path or _project_path(project_id, data)
    source_location = _project_source_location(data)

    if isinstance(data.get("physical_location"), str):
        exists = bool(source_location and source_location.exists())
        declared_location = (compat.WORKSPACE_ROOT / str(data["physical_location"])).expanduser()
        relative_location = str(source_location.relative_to(compat.WORKSPACE_ROOT)) if source_location else ""
        location_drift = declared_location != source_location
        return {
            "status": "ready" if exists else "missing",
            "surface_type": "implemented-in-bin",
            "declared_location": str(declared_location),
            "resolved_location": str(source_location) if source_location else None,
            "docs": {
                "present": 1 if exists else 0,
                "expected": 1,
                "items": [{"name": relative_location, "path": str(source_location), "exists": exists}],
            },
            "commands": [f'python3 "{relative_location}"'] if exists else [],
            "manifests": (
                [{"name": "implemented-in-bin", "path": str(source_location), "exists": True}] if exists else []
            ),
            "risks": (["physical_location_drift"] if location_drift else [])
            if exists
            else ["physical_location_missing"],
            "next_action": (
                "更新注册表 physical_location，使其与实际实现路径一致。"
                if location_drift
                else "保持注册表 physical_location、端口和验证证据同步。"
            )
            if exists
            else "修复注册表 physical_location 或恢复实现文件。",
        }

    doc_files = [
        {"name": name, "path": str(path / name), "exists": (path / name).exists()} for name in PROJECT_DOC_FILES
    ]
    present_docs = [item for item in doc_files if item["exists"]]
    expected_doc_count = (
        1 if isinstance(data.get("storage"), str) and data["storage"].strip() else len(PROJECT_DOC_FILES)
    )
    commands = _commands_from_agents(path)
    manifests = [
        {"name": name, "path": str(path / name), "exists": (path / name).exists()} for name in PACKAGE_MANIFESTS
    ]
    existing_manifests = [item for item in manifests if item["exists"]]
    if isinstance(data.get("storage"), str) and path.exists():
        for child in sorted(path.iterdir()):
            if not child.is_dir():
                continue
            for name in PACKAGE_MANIFESTS:
                candidate = child / name
                if candidate.exists():
                    existing_manifests.append({"name": f"{child.name}/{name}", "path": str(candidate), "exists": True})
        existing_manifests = existing_manifests[:8]

    risks: list[str] = []
    if not path.exists():
        risks.append("project_path_missing")
    if not present_docs:
        risks.append("docs_missing")
    if not commands:
        risks.append("commands_missing")
    if not existing_manifests:
        risks.append("manifest_missing")

    if not path.exists():
        status = "missing"
    elif risks:
        status = "partial"
    else:
        status = "ready"

    next_action = {
        "ready": "保持项目注册表与 Cockpit 映射同步。",
        "partial": "补齐项目文档、命令或构建清单后升级为原生状态面。",
        "missing": "确认项目是否已归档、迁移或需要从注册表下线。",
    }[status]
    if status == "missing" and isinstance(data.get("path_env"), str):
        next_action = f"设置环境变量 {data['path_env']} 指向项目 worktree，再重新加载 Cockpit。"

    return {
        "status": status,
        "surface_type": (
            "external-worktree" if data.get("path_env") else "external-storage" if data.get("storage") else "native"
        ),
        "docs": {
            "present": len(present_docs),
            "expected": expected_doc_count,
            "policy": "external-guide-only" if expected_doc_count == 1 else "workspace-project-docs",
            "items": doc_files,
        },
        "commands": commands,
        "manifests": existing_manifests,
        "risks": risks,
        "next_action": next_action,
        "path_env": data.get("path_env"),
        "path_configured": bool(data.get("path_env") and os.environ.get(str(data["path_env"]).strip())),
    }


def _parse_capability_domains(path: Path) -> list[dict[str, Any]]:
    text = _read_text(path)
    headings = list(re.finditer(r"^##\s+([1-8])\.\s+(.+?)(?:\s+\((.*?)\))?\s*$", text, re.MULTILINE))
    domains: list[dict[str, Any]] = []

    for index, match in enumerate(headings):
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        body = text[start:end]
        title = match.group(2).strip()
        english = (match.group(3) or "").strip()
        rows = _parse_markdown_rows(body)
        providers = sorted(
            {
                provider.strip()
                for row in rows
                for provider in re.split(r"\s*\+\s*|\s*,\s*| / ", row.get("提供者", ""))
                if provider.strip() and provider.strip() != "—"
            }
        )
        page_id = CAPABILITY_TO_PAGE.get(title, "SystemMap")
        domains.append(
            {
                "id": f"capability-{match.group(1)}",
                "title": title,
                "english": english,
                "capability_items": [row.get("能力", "") for row in rows if row.get("能力")],
                "providers": providers,
                "cockpit_page": page_id,
                "coverage": "native" if page_id != "SystemMap" else "orientation",
                "source_refs": [
                    _source_ref(
                        path,
                        f"能力域 {title}",
                        "functional_capability_map",
                        text[: match.start()].count("\n") + 1,
                    )
                ],
            }
        )

    return domains


def _parse_markdown_rows(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) == len(header):
            rows.append(dict(zip(header, cells, strict=False)))
    return rows


def _build_layers(
    registry: dict[str, Any], projects: list[dict[str, Any]], registry_path: Path
) -> list[dict[str, Any]]:
    layer_names = registry.get("layers") or {}
    projects_by_layer: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for project in projects:
        projects_by_layer[project["layer"]].append(project)

    return [
        {
            "id": layer_id,
            "name": layer_name,
            "projects": projects_by_layer.get(layer_id, []),
            "project_count": len(projects_by_layer.get(layer_id, [])),
            "cockpit_pages": sorted({project["cockpit_page"] for project in projects_by_layer.get(layer_id, [])}),
            "source_refs": [
                _source_ref(
                    registry_path,
                    f"层级 {layer_id}",
                    "project_registry",
                    _line_number(registry_path, rf"^\s*{re.escape(layer_id)}:\s"),
                )
            ],
        }
        for layer_id, layer_name in layer_names.items()
    ]


def _project_source_refs(
    project_id: str, project_path: Path, registry_path: Path, ports: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    refs = [
        _source_ref(
            registry_path,
            "项目注册",
            "project_registry",
            _line_number(registry_path, rf"^\s*{re.escape(project_id)}:\s*$"),
        )
    ]
    agents_path = project_path / "AGENTS.md"
    if agents_path.exists():
        refs.append(_source_ref(agents_path, "项目操作指南", "project_agents", 1))
    for port in ports[:2]:
        source = port.get("source_ref")
        if source:
            refs.append(source)
    return refs


def _coverage_check(check_id: str, status: str, detail: str, next_action: str) -> dict[str, str]:
    definition = next(item for item in PROJECT_COVERAGE_DIMENSIONS if item["id"] == check_id)
    return {
        "id": check_id,
        "title": definition["title"],
        "status": status,
        "detail": detail,
        "next_action": next_action,
    }


def _latest_controlled_verification(project_id: str) -> dict[str, Any]:
    """Read the latest OMO-controlled verification audit for a project."""
    posture = _triage_task_posture(project_id, "verification-rerun")
    task_id = str(posture.get("task_id") or "")
    if not task_id or posture.get("status") == "not_queued":
        return {}
    for group in ("active", "done", "archived/done"):
        task_path = compat.WORKSPACE_ROOT / ".omo" / "tasks" / group / f"{task_id}.yaml"
        if not task_path.is_file():
            continue
        try:
            task = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            return {}
        audit = (task.get("metadata") or {}).get("execution_audit") or {}
        return audit if isinstance(audit, dict) else {}
    return {}


def _project_coverage_checks(project: dict[str, Any]) -> list[dict[str, str]]:
    operational = project.get("operational", {})
    runtime = project.get("runtime", {})
    verification = runtime.get("latest_verification", {})
    source_refs = project.get("source_refs") or []
    actions = project.get("actions") or []
    registry_contract = project.get("registry_contract") or {}
    project_path = Path(str(project.get("path") or ""))

    docs = operational.get("docs") or {}
    docs_present = int(docs.get("present") or 0)
    docs_expected = int(docs.get("expected") or len(PROJECT_DOC_FILES))
    docs_status = "failed" if docs_present == 0 else "ready" if docs_present >= docs_expected else "warning"

    runtime_status = runtime.get("status")
    verification_status = verification.get("status")
    controlled_audit = _latest_controlled_verification(str(project.get("id") or ""))
    controlled_passed = controlled_audit.get("exit_code") == 0
    missing_sources = [ref for ref in source_refs if not ref.get("exists")]
    security_doc = project_path / "SECURITY.md"
    security_audit = next(
        (
            candidate
            for candidate in (project_path / "AUDIT.md", project_path / "SECURITY-AUDIT.md")
            if candidate.is_file()
        ),
        None,
    )
    security_status = (
        "ready" if security_doc.is_file() or security_audit else "warning" if project_path.exists() else "failed"
    )
    security_detail = (
        (
            f"已发现安全合同：{security_doc.name}"
            if security_doc.is_file()
            else f"已发现安全审计入口：{security_audit.name}"  # type: ignore[union-attr]
        )
        + (f"，审计入口：{security_audit.name}。" if security_audit and security_doc.is_file() else "。")
        if security_status == "ready"
        else "项目存在，但未发现 SECURITY.md 安全合同。"
        if security_status == "warning"
        else "项目实现路径不可读，无法判断安全合同。"
    )

    verification_detail = f"最近验证：{verification_status}，checks={verification.get('checks', 0)}。" + (
        f" 已登记命令：{verification.get('command')}。" if verification.get("command") else ""
    )
    closeout_status = verification.get("closeout_status") or (
        "closed" if verification.get("closeout_ref") else "missing"
    )
    verification_next_action = (
        "保持验证与 closeout 证据同步。"
        if controlled_passed and closeout_status == "closed"
        else "将受控重跑结果通过 agent-workflow 留证并完成 closeout。"
        if controlled_passed
        else "复现失败验证并补 closeout 证据。"
        if verification_status == "failed"
        else "先补验证命令或构建清单，再建立可复制的验证入口。"
        if verification_status == "unknown"
        else "运行已登记验证命令，并通过 agent-workflow 留证。"
        if verification_status == "documented"
        else "保持验证证据新鲜。"
    )
    verification_freshness = verification.get("freshness") or {}
    if verification_freshness.get("status") == "stale":
        verification_detail += " 最近证据已过期。"
        verification_next_action = str(verification_freshness.get("next_action") or "重新执行并留存最新证据。")
    elif verification_freshness.get("status") == "unknown" and verification_status in {"verified", "documented"}:
        verification_detail += " 证据缺少可判断新鲜度的时间戳。"
        verification_next_action = str(verification_freshness.get("next_action") or "补录带时间戳的持久证据。")
    if controlled_passed:
        verification_detail += (
            " 受控重跑已通过，agent-workflow closeout 已存在。"
            if closeout_status == "closed"
            else " 受控重跑已通过，但尚未形成 agent-workflow closeout。"
        )

    return [
        _coverage_check(
            "cockpit_surface",
            "ready" if project.get("coverage") == "native" else "warning",
            f"入口：{project.get('cockpit_page', 'SystemMap')}，覆盖：{project.get('coverage', 'orientation')}。",
            "保持页面映射同步。" if project.get("coverage") == "native" else "补原生项目页面或领域应用挂载入口。",
        ),
        _coverage_check(
            "registry_contract",
            str(registry_contract.get("status_text") or "failed"),
            (
                "注册合同完整：生命周期、构建/运行约束和实现落点均已声明。"
                if not registry_contract.get("missing_fields")
                else "缺失注册字段："
                + "、".join(str(item) for item in registry_contract.get("missing_fields") or [])
                + "。"
                + (
                    f" 实际观测落点：{registry_contract.get('observed_location')}。"
                    if registry_contract.get("observed_location")
                    else ""
                )
            ),
            "在 docs/project-registry.yaml 补齐版本/生命周期、构建运行约束和实现落点。"
            if registry_contract.get("missing_fields")
            else "保持注册合同与实际项目状态同步。",
        ),
        _coverage_check(
            "security_contract",
            security_status,
            security_detail,
            "补充 SECURITY.md，说明信任边界、敏感操作和安全审计入口。"
            if security_status != "ready"
            else "保持安全合同与实际入口、权限和审计状态同步。",
        ),
        _coverage_check(
            "project_docs",
            docs_status,
            f"已找到 {docs_present} / {docs_expected} 个项目文档。",
            "补齐缺失项目文档。" if docs_status != "ready" else "保持文档与项目状态同步。",
        ),
        _coverage_check(
            "commands",
            "ready" if operational.get("commands") else "failed",
            f"已登记 {len(operational.get('commands') or [])} 条操作命令。",
            "在项目 AGENTS.md 的 Commands 区块登记常用命令。"
            if not operational.get("commands")
            else "保持验证、启动和维护命令可复制。",
        ),
        _coverage_check(
            "manifest",
            "ready" if operational.get("manifests") else "failed",
            f"已发现 {len(operational.get('manifests') or [])} 个构建清单。",
            "补 pyproject.toml、package.json 或 docker-compose.yml。"
            if not operational.get("manifests")
            else "保持机器清单可被 Cockpit 识别。",
        ),
        _coverage_check(
            "runtime_probe",
            (
                "ready"
                if runtime_status in {"running", "not_applicable"}
                else "warning"
                if runtime_status == "stopped"
                else "failed"
            ),
            (
                f"运行状态：{runtime_status}，形态：{runtime.get('profile', 'unknown')}，"
                f"监听端口 {runtime.get('listening_count', 0)} / {len(runtime.get('ports') or [])}。"
            ),
            "启动服务或修正端口注册。"
            if runtime_status == "stopped"
            else "补端口注册，或明确标注项目为何需要常驻服务。"
            if runtime_status == "unobserved"
            else "保持运行形态说明和验证证据同步。"
            if runtime_status == "not_applicable"
            else "保持端口注册和运行状态同步。",
        ),
        _coverage_check(
            "verification",
            "warning"
            if verification_freshness.get("status") in {"stale", "unknown"}
            and verification_status in {"verified", "documented"}
            else "ready"
            if controlled_passed and closeout_status == "closed"
            else "warning"
            if controlled_passed
            else "ready"
            if verification_status == "verified"
            else "failed"
            if verification_status in {"failed", "unknown"}
            else "warning",
            verification_detail,
            verification_next_action,
        ),
        _coverage_check(
            "source_refs",
            "failed" if not source_refs else "warning" if missing_sources else "ready",
            f"来源定位 {len(source_refs)} 个，缺失 {len(missing_sources)} 个。",
            "补齐注册表、端口表或项目指南的 source_ref。"
            if not source_refs or missing_sources
            else "保持来源定位可预览。",
        ),
        _coverage_check(
            "operator_actions",
            "ready" if actions else "failed",
            f"受控动作 {len(actions)} 个。",
            "至少提供打开入口、复制路径或复制验证命令。"
            if not actions
            else "继续保持动作只复制或站内导航，不直接执行。",
        ),
    ]


def _project_diagnostics(project: dict[str, Any]) -> list[dict[str, str]]:
    diagnostics: list[dict[str, str]] = []
    operational = project.get("operational", {})
    runtime = project.get("runtime", {})
    verification = runtime.get("latest_verification", {})

    if operational.get("status") != "ready":
        diagnostics.append(
            {
                "id": "operational-gap",
                "severity": "high" if operational.get("status") == "missing" else "medium",
                "title": "基础状态未就绪",
                "detail": " / ".join(operational.get("risks") or ["operational_status_not_ready"]),
                "next_action": operational.get("next_action") or "补齐项目文档、命令和 manifest。",
            }
        )
    if runtime.get("status") == "stopped":
        ports = ", ".join(f":{port['port']}" for port in runtime.get("ports", [])[:3]) or "registered port"
        diagnostics.append(
            {
                "id": "runtime-stopped",
                "severity": "medium",
                "title": "端口未监听",
                "detail": f"已登记运行端口但当前未监听：{ports}。",
                "next_action": "确认是否需要启动服务，或更新端口注册表状态。",
            }
        )
    if runtime.get("status") == "unobserved":
        diagnostics.append(
            {
                "id": "runtime-unobserved",
                "severity": "medium",
                "title": "缺少运行探针",
                "detail": runtime.get("probe_reason") or "项目未登记可观测端口，Cockpit 只能判断目录状态。",
                "next_action": "如该项目有常驻服务，补端口注册；否则补充无需常驻的依据。",
            }
        )
    if verification.get("status") == "failed":
        diagnostics.append(
            {
                "id": "verification-failed",
                "severity": "high",
                "title": "最近验证失败",
                "detail": f"最近验证事件失败，checks={verification.get('checks', 0)}。",
                "next_action": "优先复制验证命令复现，并把结果回写到 agent-workflow 证据。",
            }
        )
    elif verification.get("status") == "unknown":
        diagnostics.append(
            {
                "id": "verification-unknown",
                "severity": "high",
                "title": "缺少验证方案",
                "detail": "未找到最近 agent-workflow 验证事件，且当前没有可复制的验证命令。",
                "next_action": "先补验证命令或最小构建清单，再通过受控 workflow 留证。",
            }
        )
    elif verification.get("status") == "documented":
        diagnostics.append(
            {
                "id": "verification-documented",
                "severity": "low",
                "title": "可验证未留证",
                "detail": "项目已经登记验证命令，但最近还没有 workflow 验证证据。",
                "next_action": "择机运行已登记命令，并把结果补进 agent-workflow 证据。",
            }
        )
    if not diagnostics:
        diagnostics.append(
            {
                "id": "ready",
                "severity": "low",
                "title": "状态可日用",
                "detail": "基础状态、运行探针和最近验证未发现阻断项。",
                "next_action": "保持项目注册表、端口和验证证据同步。",
            }
        )
    return diagnostics


def _project_portfolio_state(project: dict[str, Any]) -> dict[str, Any]:
    checks = project.get("coverage_checks") or []
    ready = sum(1 for check in checks if check["status"] == "ready")
    warning = sum(1 for check in checks if check["status"] == "warning")
    failed = sum(1 for check in checks if check["status"] == "failed")
    score = round(((ready * 100) + (warning * 50)) / len(checks)) if checks else 0

    operational_status = project.get("operational", {}).get("status")
    runtime_status = project.get("runtime", {}).get("status")
    verification_status = project.get("runtime", {}).get("latest_verification", {}).get("status")
    workflow_active = int(project.get("workflow", {}).get("summary", {}).get("active") or 0)

    if operational_status == "missing" or verification_status == "failed" or failed >= 3:
        status = "blocked"
    elif failed > 0 or runtime_status in {"stopped", "unobserved"} or operational_status != "ready":
        status = "at_risk"
    elif warning > 0 or workflow_active:
        status = "watch"
    else:
        status = "healthy"

    non_ready_dimensions = [
        {
            "id": check["id"],
            "title": check["title"],
            "status": check["status"],
            "next_action": check["next_action"],
        }
        for check in checks
        if check["status"] != "ready"
    ]
    primary_diagnostic = (project.get("diagnostics") or [{}])[0]
    next_action = (
        primary_diagnostic.get("next_action")
        or project.get("operational", {}).get("next_action")
        or (non_ready_dimensions[0]["next_action"] if non_ready_dimensions else "保持项目状态同步。")
    )

    return {
        "score": score,
        "status": status,
        "ready": ready,
        "warning": warning,
        "failed": failed,
        "primary_gap": primary_diagnostic.get("title") or "状态可日用",
        "next_action": next_action,
        "non_ready_dimensions": non_ready_dimensions[:5],
    }
