from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .omo_io import write_text_atomic
from .omo_worker_core import (
    _find_dispatch_file,
    _load_yaml,
    _omo_path,
    _parse_iso8601,
    _utc_now,
    _write_yaml,
)

def collect_worker_status(
    root: Path, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    active_dir = _omo_path(root, omo_dir) / "tasks" / "active"
    runs: list[dict[str, object]] = []

    for task_file in sorted(active_dir.glob("*.yaml")):
        task = _load_yaml(task_file)
        run_ref = task.get("run_ref")
        if not run_ref:
            continue

        dispatch_path = root / run_ref
        if not dispatch_path.exists():
            continue

        dispatch = _load_yaml(dispatch_path)
        runs.append(
            {
                "task_id": dispatch.get("task_id", task.get("id")),
                "worker_id": dispatch.get("worker_id"),
                "dispatch_state": dispatch.get("dispatch_state"),
                "checkpoint_refs": dispatch.get("execution", {}).get(
                    "checkpoint_refs", []
                ),
                "reclaim_ref": dispatch.get("reclaim", {}).get("note_ref"),
                "review_ref": dispatch.get("handoff", {}).get("output_summary_ref"),
                "lease": dispatch.get("lease", {}),
            }
        )

    return {
        "active_dispatches": len(runs),
        "runs": runs,
    }


def update_dispatch_checkpoint(
    root: Path,
    dispatch_id: str,
    completed_step: str,
    changed_files: list[str],
    note: str,
    now: str | None = None,
    omo_dir: str | Path = ".omo",
) -> dict[str, object]:
    dispatch_path = _find_dispatch_file(
        _omo_path(root, omo_dir) / "workers" / "runs", dispatch_id
    )
    dispatch = _load_yaml(dispatch_path)
    checkpoint_ref = dispatch.get("execution", {}).get("checkpoint_refs", [None])[-1]
    if not checkpoint_ref:
        raise ValueError(f"dispatch {dispatch_id} has no checkpoint ref")

    timestamp = now or _utc_now()
    changed_file_lines = [f"- `{path}`" for path in changed_files] or ["- None"]
    checkpoint_lines = [
        "# Checkpoint Note",
        "",
        "## Last completed step",
        "",
        completed_step,
        "",
        "## Changed files",
        "",
        *changed_file_lines,
        "",
        "## Operator note",
        "",
        note,
        "",
    ]
    write_text_atomic(root / checkpoint_ref, "\n".join(checkpoint_lines))

    dispatch["dispatch_state"] = "checkpointed"
    dispatch["lease"]["last_checkpoint_at"] = timestamp
    dispatch["lease"]["last_material_write_at"] = timestamp
    _write_yaml(dispatch_path, dispatch)
    return dispatch


def scan_runtime_watchdog(
    root: Path, now: str | None = None, omo_dir: str | Path = ".omo"
) -> dict[str, object]:
    current_time = _parse_iso8601(now) or datetime.now(timezone.utc)
    status = collect_worker_status(root, omo_dir=omo_dir)
    runs: list[dict[str, object]] = []
    counts = {"healthy": 0, "warning": 0, "stale": 0, "reclaim_due": 0}

    for run in status["runs"]:
        lease = run.get("lease", {})
        last_seen = _parse_iso8601(
            lease.get("last_material_write_at")
        ) or _parse_iso8601(lease.get("last_checkpoint_at"))
        age_seconds = (
            int((current_time - last_seen).total_seconds()) if last_seen else None
        )
        health = "healthy"
        if age_seconds is not None:
            if age_seconds >= lease.get("reclaim_after_seconds", 0):
                health = "reclaim_due"
            elif age_seconds >= lease.get("lease_expired_after_seconds", 0):
                health = "stale"
            elif age_seconds >= lease.get("warning_after_seconds", 0):
                health = "warning"
        counts[health] += 1
        runs.append(
            {
                **run,
                "age_seconds": age_seconds,
                "health": health,
            }
        )

    return {"counts": counts, "runs": runs}
