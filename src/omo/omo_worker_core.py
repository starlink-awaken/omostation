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
    argv = _build_launch_argv(registry, worker_id, transport, prompt_text)
    result = subprocess.run(argv, cwd=root, capture_output=True, text=True)
    output = redact_sensitive_text((result.stdout or "") + (result.stderr or ""))
    write_text_atomic(stdout_path, output)
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
    registry: dict, worker_id: str, transport: str, prompt_text: str
) -> list[str]:
    sentinel = "__OMO_PROMPT__"
    template = _worker_command(registry, worker_id, transport).format(prompt=sentinel)
    argv = shlex.split(template)
    forbidden_fragments = ("&&", "||", "|")
    for index, arg in enumerate(argv):
        if index > 0 and argv[index - 1] == "-c":
            continue
        if any(fragment in arg for fragment in forbidden_fragments):
            raise ValueError(f"unsafe worker command template: {template}")
        if ";" in arg and arg != ";" and not arg.startswith("-c"):
            raise ValueError(f"unsafe worker command template: {template}")
    return [prompt_text if arg == sentinel else arg for arg in argv]
