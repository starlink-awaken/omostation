#!/usr/bin/env python3
from __future__ import annotations
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .omo_io import write_text_atomic, write_yaml_atomic
from .omo_redaction import redact_sensitive_text

def _timestamp_slug(now: str | None = None) -> str:
    if now:
        return now.replace("-", "").replace(":", "").replace("T", "-").replace("Z", "")
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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


def _worker_command(registry: dict, worker_id: str, transport: str) -> str:
    for worker in registry.get("workers", []):
        if worker.get("id") == worker_id:
            return worker["transports"][transport]["command"]
    raise KeyError(f"Worker not registered: {worker_id}")


def _default_enabled_worker_id(registry: dict) -> str:
    default_role = registry.get("default_worker_role")
    for worker in registry.get("workers", []):
        if worker.get("enabled", True) and (
            default_role is None or worker.get("role") == default_role
        ):
            return str(worker["id"])
    for worker in registry.get("workers", []):
        if worker.get("enabled", True):
            return str(worker["id"])
    raise ValueError("no enabled worker is registered")


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
) -> dict[str, object]:
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


