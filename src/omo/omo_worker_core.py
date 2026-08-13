#!/usr/bin/env python3
from __future__ import annotations

import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import write_text_atomic, write_yaml_atomic
from .omo_redaction import redact_sensitive_text
from .omo_shared import load_yaml

_OPERATION_LEVELS = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}


def _timestamp_slug(now: str | None = None) -> str:
    if now:
        return now.replace("-", "").replace(":", "").replace("T", "-").replace("Z", "")
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _load_yaml(path: Path) -> dict:
    return load_yaml(path)


def _write_yaml(path: Path, data: dict) -> None:
    write_yaml_atomic(path, data)


def _find_task_file(active_dir: Path, task_id: str) -> Path:
    for task_file in active_dir.glob("*.yaml"):
        task = _load_yaml(task_file)
        if task.get("id") == task_id:
            return task_file
    raise FileNotFoundError(f"Task not found in active/: {task_id}")


def _find_planned_task_file(planned_dir: Path, task_id: str) -> Path:
    for task_file in planned_dir.glob("*.yaml"):
        task = _load_yaml(task_file)
        if task.get("id") == task_id:
            return task_file
    raise FileNotFoundError(f"Task not found in planned/: {task_id}")


def _find_task_file_safe(search_dir: Path, task_id: str) -> Path | None:
    if not search_dir.exists():
        return None
    for task_file in search_dir.glob("*.yaml"):
        task = _load_yaml(task_file)
        if task.get("id") == task_id:
            return task_file
    return None


def _find_dispatch_file(runs_dir: Path, dispatch_id: str) -> Path:
    path = runs_dir / f"{dispatch_id}-dispatch.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Dispatch not found: {dispatch_id}")
    return path


def _require_admitted_worker(
    registry: dict, worker_id: str, transport: str
) -> dict[str, Any]:
    """Return an admitted worker or fail before dispatch side effects.

    The registry is the admission SSOT.  A worker that is merely declared (or
    enabled without an admission decision) must never reach command
    construction.  Keeping this validation in one helper lets callers place it
    at their own side-effect boundary while preserving one stable error shape.
    """
    worker = next(
        (
            candidate
            for candidate in registry.get("workers", [])
            if isinstance(candidate, dict) and candidate.get("id") == worker_id
        ),
        None,
    )
    if worker is None:
        raise ValueError(
            f"worker admission denied: worker_id={worker_id} reason=not_registered"
        )
    if worker.get("enabled") is not True:
        raise ValueError(
            f"worker admission denied: worker_id={worker_id} reason=disabled"
        )
    if worker.get("admission_state") != "admitted":
        raise ValueError(
            f"worker admission denied: worker_id={worker_id} reason=not_admitted"
        )
    transports = worker.get("transports")
    transport_spec = transports.get(transport) if isinstance(transports, dict) else None
    if (
        not isinstance(transport_spec, dict)
        or not str(transport_spec.get("command", "")).strip()
    ):
        raise ValueError(
            "worker admission denied: "
            f"worker_id={worker_id} reason=transport_missing transport={transport}"
        )
    return worker


def _worker_command(registry: dict, worker_id: str, transport: str) -> str:
    worker = _require_admitted_worker(registry, worker_id, transport)
    return str(worker["transports"][transport]["command"])


def _capability_values(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _required_capabilities(
    task: dict[str, Any],
    workflow_packet: dict[str, Any] | None,
    *,
    worker_id: str,
) -> tuple[list[str], bool]:
    required: list[str] = []
    explicit = False

    def collect(container: dict[str, Any], source: str) -> None:
        nonlocal explicit
        for key in ("required_capabilities", "capabilities"):
            if key not in container:
                continue
            explicit = True
            value = container[key]
            if (
                not isinstance(value, list)
                or not value
                or any(not isinstance(item, str) or not item.strip() for item in value)
            ):
                raise ValueError(
                    "worker policy denied: "
                    f"worker_id={worker_id} "
                    "reason=invalid_capability_requirements "
                    f"source={source}.{key}"
                )
            required.extend(item.strip() for item in value)

    collect(task, "task")
    if workflow_packet:
        collect(workflow_packet, "workflow_packet")
        admission = workflow_packet.get("admission")
        if isinstance(admission, dict):
            collect(admission, "workflow_packet.admission")
    return list(dict.fromkeys(required)), explicit


def _require_worker_policy(
    registry: dict[str, Any],
    worker: dict[str, Any],
    task: dict[str, Any],
    *,
    allowed_write_paths: list[str],
    workflow_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enforce the worker's bounded execution contract before dispatch writes."""
    worker_id = str(worker.get("id", "unknown"))
    allowed_level = str(
        worker.get(
            "allowed_operation_level",
            registry.get("default_allowed_operation_level", "L1"),
        )
    ).upper()
    if allowed_level not in _OPERATION_LEVELS:
        raise ValueError(
            "worker policy denied: "
            f"worker_id={worker_id} reason=invalid_worker_operation_level"
        )
    task_levels: list[str] = []
    for field in ("risk_level", "allowed_operation_level"):
        level = str(task.get(field) or "L0").upper()
        if level not in _OPERATION_LEVELS:
            raise ValueError(
                "worker policy denied: "
                f"worker_id={worker_id} reason=invalid_task_operation_level "
                f"field={field}"
            )
        task_levels.append(level)
    requested_level = max(task_levels, key=_OPERATION_LEVELS.__getitem__)
    if _OPERATION_LEVELS[requested_level] > _OPERATION_LEVELS[allowed_level]:
        raise ValueError(
            "worker policy denied: "
            f"worker_id={worker_id} reason=operation_level_exceeded "
            f"requested={requested_level} allowed={allowed_level}"
        )

    write_scope = worker.get("write_scope")
    scope_mode = write_scope.get("mode") if isinstance(write_scope, dict) else None
    if scope_mode == "none" and allowed_write_paths:
        raise ValueError(
            "worker policy denied: "
            f"worker_id={worker_id} reason=write_scope_denied mode=none"
        )

    required, explicit_capabilities = _required_capabilities(
        task,
        workflow_packet,
        worker_id=worker_id,
    )
    if (
        worker.get("require_explicit_capabilities") is True
        and not explicit_capabilities
    ):
        raise ValueError(
            "worker policy denied: "
            f"worker_id={worker_id} reason=capability_requirements_missing"
        )
    provided = set(_capability_values(worker.get("capabilities")))
    missing = [capability for capability in required if capability not in provided]
    if missing:
        raise ValueError(
            "worker policy denied: "
            f"worker_id={worker_id} reason=capability_mismatch "
            f"missing={','.join(missing)}"
        )
    return worker


def _default_enabled_worker_id(registry: dict) -> str:
    default_role = registry.get("default_worker_role")
    for worker in registry.get("workers", []):
        if (
            worker.get("enabled") is True
            and worker.get("admission_state") == "admitted"
            and (default_role is None or worker.get("role") == default_role)
        ):
            return str(worker["id"])
    for worker in registry.get("workers", []):
        if (
            worker.get("enabled") is True
            and worker.get("admission_state") == "admitted"
        ):
            return str(worker["id"])
    raise ValueError("no admitted worker is registered")


def _dispatch_allowed_write_paths(task: dict) -> list[str]:
    paths: list[str] = []
    for deliverable in task.get("deliverables", []):
        path = str(deliverable)
        if path.endswith("/"):
            candidate = path
        else:
            candidate = str(Path(path).parent)
            if candidate == ".":
                candidate = path
            elif not candidate.endswith("/"):
                candidate = f"{candidate}/"
        if candidate not in paths:
            paths.append(candidate)
    return paths


def _launch_worker_from_prompt(
    root: Path,
    registry: dict,
    worker_id: str,
    transport: str,
    prompt_path: Path,
    stdout_path: Path,
) -> str:
    prompt_text = prompt_path.read_text(encoding="utf-8")
    argv = _build_launch_argv(
        registry,
        worker_id,
        transport,
        prompt_text,
        workspace_root=root,
    )
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
    output = redact_sensitive_text((result.stdout or "") + (result.stderr or ""))
    write_text_atomic(stdout_path, output)
    if result.returncode != 0:
        raise RuntimeError(
            "worker launch failed: "
            f"worker_id={worker_id} returncode={result.returncode} log={stdout_path}"
        )
    return output


def _launch_existing_dispatch(
    root: Path, dispatch_path: Path, *, omo_dir: str | Path = ".omo"
) -> dict[str, Any]:
    dispatch = _load_yaml(dispatch_path)
    registry = _load_yaml(
        _omo_path(root, omo_dir) / "_truth" / "registry" / "workers.yaml"
    )
    prompt_ref = (
        dispatch.get("inputs", {}).get("prompt_file")
        or dispatch["execution"]["prompt_file"]
    )
    prompt_path = root / str(prompt_ref)
    stdout_path = root / dispatch["execution"]["log_ref"]
    _launch_worker_from_prompt(
        root,
        registry,
        str(dispatch["worker_id"]),
        str(dispatch["transport_mode"]),
        prompt_path,
        stdout_path,
    )
    dispatch["dispatch_state"] = "active"
    dispatch.setdefault("lease", {})
    dispatch["lease"]["last_material_write_at"] = _utc_now()
    _write_yaml(dispatch_path, dispatch)
    return dispatch


def _append_unique(items: list[str], values: list[str]) -> list[str]:
    result = list(items)
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _omo_path(root: Path, omo_dir: str | Path = ".omo") -> Path:
    return root / Path(omo_dir)


def _build_launch_argv(
    registry: dict,
    worker_id: str,
    transport: str,
    prompt_text: str,
    *,
    workspace_root: Path | None = None,
    redact_workspace_root: bool = False,
) -> list[str]:
    prompt_sentinel = "__OMO_PROMPT__"
    workspace_sentinel = "__OMO_WORKSPACE_ROOT__"
    command = _worker_command(registry, worker_id, transport)
    if "{workspace_root}" in command:
        if workspace_root is None:
            raise ValueError("worker command requires a workspace root")
        resolved_root = workspace_root.resolve()
        if not resolved_root.is_dir():
            raise ValueError(f"invalid workspace root: {resolved_root}")
    else:
        resolved_root = None
    try:
        template = command.format(
            prompt=prompt_sentinel,
            workspace_root=workspace_sentinel,
        )
    except (KeyError, ValueError) as exc:
        raise ValueError(f"invalid worker command template: {command}") from exc
    argv = shlex.split(template)
    forbidden_fragments = ("&&", "||", "|")
    for index, arg in enumerate(argv):
        if index > 0 and argv[index - 1] == "-c":
            continue
        if any(fragment in arg for fragment in forbidden_fragments):
            raise ValueError(f"unsafe worker command template: {template}")
        if ";" in arg and arg != ";" and not arg.startswith("-c"):
            raise ValueError(f"unsafe worker command template: {template}")
    resolved_argv: list[str] = []
    for arg in argv:
        if arg == prompt_sentinel:
            resolved_argv.append(prompt_text)
            continue
        if workspace_sentinel in arg:
            if resolved_root is None:
                raise ValueError("worker command requires a workspace root")
            workspace_value = (
                "<workspace_root>" if redact_workspace_root else str(resolved_root)
            )
            arg = arg.replace(workspace_sentinel, workspace_value)
        resolved_argv.append(arg)
    return resolved_argv
