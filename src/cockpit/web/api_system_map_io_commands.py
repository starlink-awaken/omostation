"""cockpit system-map io/source-ref + command/port helpers. Split from api_system_map.py."""

from __future__ import annotations

import json
import re
import socket
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException, Query

from cockpit import compat

MAX_SOURCE_PREVIEW_BYTES = 1_000_000

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


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        if path.name == "port-registry.yaml":
            return _recover_port_registry(path)
        return {}


def _recover_port_registry(path: Path) -> dict[str, Any]:
    """Recover simple port records while preserving a malformed-registry signal.

    The registry is an external SSOT and remains read-only here. This parser only
    recovers the stable ``port -> name/transport/status`` records needed for the
    project runtime view; it never invents a port or a listening result.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    ports: dict[int, dict[str, str]] = {}
    current_port: int | None = None
    current: dict[str, str] = {}

    def flush() -> None:
        if current_port is not None and current.get("name"):
            ports[current_port] = dict(current)

    for line in lines:
        port_match = re.match(r"^\s{2}(\d+):\s*$", line)
        if port_match:
            flush()
            current_port = int(port_match.group(1))
            current = {}
            continue
        if current_port is None:
            continue
        field_match = re.match(r'^\s{4}(name|transport|status):\s*["\']?([^"\']+?)["\']?\s*$', line)
        if field_match:
            current[field_match.group(1)] = field_match.group(2).strip()
    flush()

    return {"ports": ports, "types": {}, "_parse_warning": "port-registry.yaml recovered after YAML parse failure"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _read_text_lossy(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise HTTPException(status_code=404, detail="source file is not readable") from exc


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def _path_state(path: Path) -> dict[str, Any]:
    return {"path": str(path), "exists": path.exists()}


def _exists_any(base: Path, candidates: tuple[str, ...]) -> bool:
    return any((base / candidate).exists() for candidate in candidates)


def _line_number(path: Path, pattern: str) -> int | None:
    text = _read_text(path)
    if not text:
        return None
    matcher = re.compile(pattern)
    for index, line in enumerate(text.splitlines(), start=1):
        if matcher.search(line):
            return index
    return None


def _source_ref(path: Path, label: str, source_key: str, line: int | None = None) -> dict[str, Any]:
    target = str(path)
    if line:
        target = f"{target}:{line}"
    return {
        "source_key": source_key,
        "label": label,
        "path": str(path),
        "line": line,
        "exists": path.exists(),
        "target": target,
    }


def _source_ref_for_id(path: Path, item_id: str, label: str, source_key: str) -> dict[str, Any]:
    return _source_ref(path, label, source_key, _line_number(path, rf'"id": "{re.escape(item_id)}"'))


def _parse_source_ref_target(target: str | None, path: str | None, line: int | None) -> tuple[Path, int | None]:
    raw_path = path
    parsed_line = line
    if target:
        raw_target = target.strip()
        line_match = re.match(r"^(?P<path>.+):(?P<line>\d+)$", raw_target)
        if line_match:
            raw_path = line_match.group("path")
            parsed_line = int(line_match.group("line"))
        else:
            raw_path = raw_target
    if not raw_path:
        raise HTTPException(status_code=400, detail="target or path is required")

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = compat.WORKSPACE_ROOT / candidate
    resolved = candidate.resolve(strict=False)
    workspace_root = compat.WORKSPACE_ROOT.resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="source path must stay inside workspace") from exc
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="source file does not exist")
    if resolved.stat().st_size > MAX_SOURCE_PREVIEW_BYTES:
        raise HTTPException(status_code=413, detail="source file is too large for preview")
    return resolved, max(1, parsed_line) if parsed_line else None


def build_source_ref_preview(
    target: str | None = None,
    path: str | None = None,
    line: int | None = None,
    context: int = 4,
) -> dict[str, Any]:
    source_path, source_line = _parse_source_ref_target(target, path, line)
    text = _read_text_lossy(source_path)
    lines = text.splitlines()
    total_lines = len(lines)
    focus_line = min(source_line or 1, total_lines or 1)
    start = max(1, focus_line - context)
    end = min(total_lines, focus_line + context) if total_lines else 0
    preview_lines = [
        {
            "number": number,
            "text": lines[number - 1],
            "highlight": bool(source_line and number == focus_line),
        }
        for number in range(start, end + 1)
    ]
    return {
        "path": str(source_path),
        "workspace_relative_path": str(source_path.relative_to(compat.WORKSPACE_ROOT.resolve())),
        "line": source_line,
        "target": f"{source_path}:{source_line}" if source_line else str(source_path),
        "total_lines": total_lines,
        "context_start": start,
        "context_end": end,
        "lines": preview_lines,
        "guard": "只读来源预览；路径必须位于当前 Workspace 内，接口不执行本机打开命令。",
    }


def _command_with_cwd(path: Path, command: str) -> str:
    return f'cd "{path}" && {command}'


def _first_matching_command(commands: list[str], include: tuple[str, ...], exclude: tuple[str, ...] = ()) -> str | None:
    for command in commands:
        lowered = command.lower()
        if any(token in lowered for token in include) and not any(token in lowered for token in exclude):
            return command
    return None


def _package_scripts(path: Path) -> dict[str, str]:
    package = _read_json(path / "package.json")
    scripts = package.get("scripts")
    if isinstance(scripts, dict):
        return {str(key): str(value) for key, value in scripts.items()}
    return {}


def _project_verify_command(path: Path, commands: list[str], manifests: list[dict[str, Any]]) -> str | None:
    command = _first_matching_command(
        commands,
        ("verify", "test", "lint", "build", "pytest", "gac", "docker compose config"),
        ("dev", "serve", "start"),
    )
    if command:
        # mesh-router is a daemon mounted from bin/gac. Its verification path
        # must use the non-serving --check mode and the workspace uv runtime.
        if path == compat.WORKSPACE_ROOT / "bin" / "gac" and command.startswith('python3 "bin/gac/'):
            return _command_with_cwd(
                compat.WORKSPACE_ROOT,
                'uv run python "bin/gac/gac-mesh-router.py" --check',
            )
        return _command_with_cwd(path, command)

    manifest_names = {item["name"] for item in manifests}
    scripts = _package_scripts(path)
    if "test" in scripts:
        return _command_with_cwd(path, "bun run test")
    if "build" in scripts:
        return _command_with_cwd(path, "bun run build")
    if "pyproject.toml" in manifest_names:
        return _command_with_cwd(path, "uv run pytest -q")
    if "docker-compose.yml" in manifest_names:
        return _command_with_cwd(path, "docker compose config -q")
    return None


def _project_start_command(path: Path, commands: list[str]) -> str | None:
    command = _first_matching_command(
        commands,
        ("dev", "serve", "start", "uvicorn", "dashboard_server", "run api"),
        ("test", "lint", "build", "verify"),
    )
    if command:
        return _command_with_cwd(path, command)

    scripts = _package_scripts(path)
    if "dev" in scripts:
        return _command_with_cwd(path, "bun run dev")
    if "api" in scripts:
        return _command_with_cwd(path, "bun run api")
    return None


def _project_actions(
    project_id: str, project_path: Path, page_id: str, operational: dict[str, Any]
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = [
        {
            "id": "open-cockpit-page",
            "label": "打开入口",
            "kind": "navigate",
            "value": page_id,
            "enabled": True,
            "risk": "low",
            "executes": False,
            "guard": "站内导航，不执行项目命令。",
        },
        {
            "id": "copy-project-path",
            "label": "复制路径",
            "kind": "copy_text",
            "value": str(project_path),
            "enabled": project_path.exists(),
            "risk": "low",
            "executes": False,
            "guard": "只复制项目路径，不读取或写入项目数据。",
        },
    ]

    commands = list(operational.get("commands") or [])
    manifests = list(operational.get("manifests") or [])
    verify_command = _project_verify_command(project_path, commands, manifests)
    if verify_command:
        actions.append(
            {
                "id": "copy-verify-command",
                "label": "复制验证",
                "kind": "copy_command",
                "value": verify_command,
                "enabled": project_path.exists(),
                "risk": "low",
                "executes": False,
                "guard": "复制验证命令，由用户在终端手动执行。",
            }
        )

    start_command = _project_start_command(project_path, commands)
    if start_command:
        actions.append(
            {
                "id": "copy-start-command",
                "label": "复制启动",
                "kind": "copy_command",
                "value": start_command,
                "enabled": project_path.exists(),
                "risk": "medium",
                "executes": False,
                "guard": "复制启动命令；Cockpit 不直接启动或重启服务。",
            }
        )

    if project_id == "cockpit":
        actions.append(
            {
                "id": "copy-cockpit-preview",
                "label": "复制预览",
                "kind": "copy_text",
                "value": "http://127.0.0.1:5173/",
                "enabled": True,
                "risk": "low",
                "executes": False,
                "guard": "复制当前 Cockpit 前端预览地址。",
            }
        )

    return actions


def _first_action(actions: list[dict[str, Any]], action_id: str) -> dict[str, Any] | None:
    return next((action for action in actions if action.get("id") == action_id), None)


def _triage_task_posture(project_id: str, command_id: str) -> dict[str, Any]:
    """Expose the OMO task state for a project triage command."""
    base_task_id = f"cockpit-triage-{project_id}-{command_id}"
    candidates: list[tuple[int, float, str, Path]] = []
    for group in ("active", "planned", "done"):
        task_root = compat.WORKSPACE_ROOT / ".omo" / "tasks" / group
        for task_path in task_root.glob(f"{base_task_id}*.yaml"):
            task_id = task_path.stem
            if task_id == base_task_id:
                attempt = 1
            else:
                match = re.fullmatch(rf"{re.escape(base_task_id)}-r(\d+)", task_id)
                if not match:
                    continue
                attempt = int(match.group(1))
            try:
                mtime = task_path.stat().st_mtime
            except OSError:
                mtime = 0.0
            candidates.append((attempt, mtime, group, task_path))

    if not candidates:
        return {"task_id": base_task_id, "status": "not_queued", "execution_audit": {}}

    _, _, group, task_path = max(candidates, key=lambda item: (item[0], item[1]))
    task_id = task_path.stem
    try:
        task = yaml.safe_load(task_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        task = {}
    audit = (task.get("metadata") or {}).get("execution_audit") or {}
    raw_status = str(task.get("status") or "pending")
    if isinstance(audit, dict) and "exit_code" in audit:
        status = "succeeded" if audit.get("exit_code") == 0 else "failed"
    elif group == "done" or raw_status in {"completed", "complete"}:
        status = "completed"
    elif group == "active" or raw_status in {"in_progress", "running"}:
        status = "active"
    else:
        status = "planned"
    return {
        "task_id": task_id,
        "status": status,
        "execution_audit": audit if isinstance(audit, dict) else {},
    }


def _triage_command(
    project_id: str,
    command_id: str,
    label: str,
    category: str,
    command: str,
    reason: str,
    *,
    enabled: bool = True,
    risk: str = "low",
) -> dict[str, Any]:
    return {
        "id": command_id,
        "label": label,
        "kind": "copy_command",
        "value": command,
        "enabled": enabled,
        "risk": risk,
        "executes": False,
        "guard": "复制排查命令；Cockpit 不直接执行终端命令。",
        "category": category,
        "project_id": project_id,
        "reason": reason,
        "task": _triage_task_posture(project_id, command_id),
    }


def _port_probe_command(ports: list[dict[str, Any]]) -> str | None:
    port_values = [str(port["port"]) for port in ports[:6] if port.get("port") and port.get("probeable", True)]
    if not port_values:
        return None
    return f"for port in {' '.join(port_values)}; do lsof -nP -iTCP:$port -sTCP:LISTEN || true; done"


def _port_registry_search_command(project_id: str) -> str:
    aliases = PROJECT_PORT_ALIASES.get(project_id, (project_id,))
    pattern = "|".join(re.escape(alias) for alias in aliases)
    return _command_with_cwd(
        compat.WORKSPACE_ROOT,
        f'rg -n "{pattern}" "protocols/port-registry.yaml" "projects/agora/etc/bos-services.yaml"',
    )


def _workflow_evidence_search_command(project_id: str) -> str:
    return _command_with_cwd(
        compat.WORKSPACE_ROOT, f'rg -n "{re.escape(project_id)}" ".omo/_delivery/agent-workflows/runs"'
    )


def _project_inventory_command(project_path: Path) -> str:
    return _command_with_cwd(
        project_path,
        'ls -la "AGENTS.md" "CLAUDE.md" "README.md" "ARCHITECTURE.md" '
        '"pyproject.toml" "package.json" "docker-compose.yml" 2>/dev/null || true',
    )


def _project_verification_plan_command(project_path: Path) -> str:
    return _command_with_cwd(
        project_path,
        'rg -n "pytest|test|verify|lint|build|check" '
        '"AGENTS.md" "CLAUDE.md" "README.md" "pyproject.toml" "package.json" '
        '"Makefile" "docker-compose.yml" 2>/dev/null || true',
    )


def _project_triage_commands(project: dict[str, Any]) -> list[dict[str, Any]]:
    project_id = project["id"]
    project_path = Path(project["path"])
    runtime = project.get("runtime", {})
    verification = runtime.get("latest_verification", {})
    actions = list(project.get("actions") or [])
    commands: list[dict[str, Any]] = []

    port_command = _port_probe_command(runtime.get("ports") or [])
    if port_command:
        commands.append(
            _triage_command(
                project_id,
                "runtime-check-ports",
                "检查端口",
                "runtime",
                port_command,
                "确认已登记端口是否真的在本机监听。",
                risk="low" if runtime.get("status") == "running" else "medium",
            )
        )

    if runtime.get("status") == "stopped":
        start_action = _first_action(actions, "copy-start-command")
        if start_action:
            commands.append(
                _triage_command(
                    project_id,
                    "runtime-copy-start",
                    "复制启动",
                    "runtime",
                    start_action["value"],
                    "项目端口已登记但未监听，先复制启动命令由人确认执行。",
                    enabled=bool(start_action.get("enabled")),
                    risk="medium",
                )
            )

    if runtime.get("status") == "unobserved":
        commands.append(
            _triage_command(
                project_id,
                "runtime-find-registry",
                "查端口登记",
                "runtime",
                _port_registry_search_command(project_id),
                "项目缺少可观测端口，先核对端口注册表和 BOS 服务。",
                risk="low",
            )
        )

    if verification.get("status") in {"documented", "failed", "unknown"}:
        verify_action = _first_action(actions, "copy-verify-command")
        if verify_action:
            rerun_label = "复跑验证" if verification.get("status") in {"failed", "unknown"} else "运行验证"
            rerun_reason = (
                "最近验证失败或缺失，复制项目验证命令复现。"
                if verification.get("status") in {"failed", "unknown"}
                else "项目已有验证命令但还没有 agent-workflow 证据，复制命令运行后留证。"
            )
            commands.append(
                _triage_command(
                    project_id,
                    "verification-rerun",
                    rerun_label,
                    "verification",
                    verify_action["value"],
                    rerun_reason,
                    enabled=bool(verify_action.get("enabled")),
                    risk="low",
                )
            )
        commands.append(
            _triage_command(
                project_id,
                "verification-find-evidence",
                "查验证证据",
                "verification",
                _workflow_evidence_search_command(project_id),
                "查找 agent-workflow 里是否已有该项目的验证或 closeout 证据。",
                risk="low",
            )
        )
        if verification.get("status") == "unknown" and not verify_action:
            commands.append(
                _triage_command(
                    project_id,
                    "verification-plan",
                    "生成验证方案",
                    "verification",
                    _project_verification_plan_command(project_path),
                    "项目没有可复制验证命令，先扫描测试、构建和校验线索，再登记可执行验证方案。",
                    risk="low",
                )
            )

    if project.get("operational", {}).get("status") != "ready":
        commands.append(
            _triage_command(
                project_id,
                "coverage-inventory",
                "查项目清单",
                "coverage",
                _project_inventory_command(project_path),
                "项目文档、命令或 manifest 不完整，先核对本地清单。",
                enabled=project_path.exists(),
                risk="low",
            )
        )

    missing_contract_fields = list((project.get("registry_contract") or {}).get("missing_fields") or [])
    if missing_contract_fields:
        commands.append(
            _triage_command(
                project_id,
                "registry-contract",
                "查注册合同",
                "coverage",
                _command_with_cwd(
                    compat.WORKSPACE_ROOT,
                    f'rg -n "^{re.escape(project_id)}:" "docs/project-registry.yaml"',
                ),
                "项目注册合同缺少：" + "、".join(str(item) for item in missing_contract_fields) + "；先定位注册表声明。",
                risk="low",
            )
        )

    return commands


def _is_port_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.04):
            return True
    except OSError:
        return False


def _project_ports(project_id: str, port_registry: dict[str, Any], port_registry_path: Path) -> list[dict[str, Any]]:
    aliases = PROJECT_PORT_ALIASES.get(project_id, (project_id,))
    registry_ports = port_registry.get("ports") or {}
    port_types = port_registry.get("types") or {}
    ports: list[dict[str, Any]] = []

    for raw_port, service in registry_ports.items():
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            continue
        if isinstance(service, dict):
            label = str(service.get("name") or service.get("service") or "")
            transport = service.get("transport")
        else:
            label = str(service)
            transport = None
        service_name = label.split("#", 1)[0].strip()
        searchable = service_name.lower()
        if any(alias.lower() in searchable for alias in aliases):
            port_type = str(transport or port_types.get(port) or port_types.get(str(port)) or "registered").lower()
            probeable = port_type in {"http", "https", "sse", "tcp", "udp"}
            ports.append(
                {
                    "port": port,
                    "service": service_name or label,
                    "raw_label": label,
                    "type": port_type,
                    "probeable": probeable,
                    "listening": _is_port_listening(port) if probeable else None,
                    "source_ref": _source_ref(
                        port_registry_path,
                        f"端口 {port}",
                        "port_registry",
                        _line_number(port_registry_path, rf"^\s*{port}:\s"),
                    ),
                }
            )

    return sorted(ports, key=lambda item: item["port"])
