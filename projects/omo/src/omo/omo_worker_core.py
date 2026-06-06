#!/usr/bin/env python3
"""OMO Worker core utilities — shared helpers for file I/O, paths, and YAML."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml


def _timestamp_slug(now: str | None = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc).isoformat()
    return now.replace(":", "-").replace(".", "-")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso8601(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _find_task_file(active_dir: Path, task_id: str) -> Path:
    for p in active_dir.iterdir():
        if p.stem == task_id:
            return p
    raise FileNotFoundError(f"Task {task_id} not found in {active_dir}")


def _find_planned_task_file(planned_dir: Path, task_id: str) -> Path:
    for p in planned_dir.iterdir():
        if p.stem == task_id:
            return p
    raise FileNotFoundError(f"Planned task {task_id} not found in {planned_dir}")


def _find_task_file_safe(search_dir: Path, task_id: str) -> Path | None:
    try:
        return _find_task_file(search_dir, task_id)
    except FileNotFoundError:
        return None


def _find_dispatch_file(runs_dir: Path, dispatch_id: str) -> Path:
    for p in runs_dir.iterdir():
        if p.stem == dispatch_id:
            return p
    raise FileNotFoundError(f"Dispatch {dispatch_id} not found in {runs_dir}")


def _worker_command(registry: dict, worker_id: str, transport: str) -> str:
    entry = registry.get(worker_id, {})
    cmd = entry.get("command", "")
    if transport == "docker":
        cmd = entry.get("docker_command", cmd)
    return cmd


def _default_enabled_worker_id(registry: dict) -> str:
    enabled = [k for k, v in registry.items() if v.get("enabled", True)]
    if not enabled:
        raise RuntimeError("No enabled workers in registry")
    if len(enabled) > 1:
        raise RuntimeError(f"Multiple enabled workers: {enabled}")
    return enabled[0]


def _dispatch_allowed_write_paths(task: dict) -> list[str]:
    raw = task.get("allowed_write_paths", [])
    if isinstance(raw, str):
        return [raw]
    return list(raw)


def _append_unique(items: list[str], values: list[str]) -> list[str]:
    for v in values:
        if v not in items:
            items.append(v)
    return items


def _omo_path(root: Path, omo_dir: str | Path = ".omo") -> Path:
    return root / omo_dir


def _build_launch_argv(
    registry: dict,
    worker_id: str,
    transport: str,
    prompt_text: str | None = None,
) -> list[str]:
    entry = registry.get(worker_id, {})
    argv: list[str] = []
    if transport == "docker":
        docker_cmd = entry.get("docker_command", "")
        if docker_cmd:
            argv = docker_cmd.split()
    else:
        cmd = entry.get("command", "")
        if cmd:
            argv = cmd.split()
    if prompt_text is not None:
        argv.append(prompt_text)
    return argv
