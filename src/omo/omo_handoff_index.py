#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import yaml

from .omo_io import write_text_atomic


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _load_task(root: Path, task_id: str) -> dict:
    for group in ("active", "done"):
        for task_file in (root / ".omo" / "tasks" / group).glob("*.yaml"):
            task = _load_yaml(task_file)
            if task.get("id") == task_id:
                return task
    raise FileNotFoundError(f"Task not found: {task_id}")


def _append_unique(items: list[str], value: str | None) -> None:
    if value and value not in items:
        items.append(value)


def _dispatch_runs_for_task(root: Path, task_id: str) -> list[tuple[str, dict]]:
    runs: list[tuple[str, dict]] = []
    runs_dir = root / ".omo" / "workers" / "runs"
    for dispatch_file in sorted(runs_dir.glob("*-dispatch.yaml")):
        dispatch = _load_yaml(dispatch_file)
        if dispatch.get("task_id") == task_id:
            runs.append((str(dispatch_file.relative_to(root)), dispatch))
    return runs


def write_handoff_index(root: Path, task_id: str) -> str:
    task = _load_task(root, task_id)
    refs = list(task.get("handoff_refs", []))
    _append_unique(refs, task.get("run_ref"))
    _append_unique(refs, task.get("review_ref"))

    dispatch_runs = _dispatch_runs_for_task(root, task_id)
    for dispatch_ref, dispatch in dispatch_runs:
        _append_unique(refs, dispatch_ref)
        for checkpoint_ref in dispatch.get("execution", {}).get("checkpoint_refs", []):
            _append_unique(refs, checkpoint_ref)
        _append_unique(refs, dispatch.get("handoff", {}).get("output_summary_ref"))
        _append_unique(refs, dispatch.get("reclaim", {}).get("note_ref"))

    prior_evidence: list[str] = []
    for ref in refs:
        if ref.endswith("-envelope.yaml"):
            envelope = _load_yaml(root / ref)
            prior_evidence.extend(envelope.get("inputs", {}).get("prior_evidence", []))

    lines = [
        f"# Handoff Index — {task_id}",
        "",
        "## Core refs",
        "",
        *(f"- `{ref}`" for ref in refs),
        "",
        "## Dispatch chain",
        "",
        *(
            f"- `{dispatch_ref}` → state={dispatch.get('dispatch_state')}"
            for dispatch_ref, dispatch in dispatch_runs
        ),
        "",
        "## Prior evidence",
        "",
        *(f"- `{ref}`" for ref in prior_evidence),
        "",
    ]
    if task.get("completion_summary"):
        lines.extend(
            [
                "## Completion summary",
                "",
                task["completion_summary"],
                "",
            ]
        )

    output = root / ".omo" / "evidence" / "handoffs" / f"{task_id}.md"
    write_text_atomic(output, "\n".join(lines).rstrip() + "\n")
    return str(output.relative_to(root))
