#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from .omo_io import write_text_atomic


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _iter_dispatch_runs(root: Path) -> list[dict]:
    runs_dir = root / ".omo" / "workers" / "runs"
    runs: list[dict] = []
    for dispatch_file in sorted(runs_dir.glob("*-dispatch.yaml")):
        runs.append(_load_yaml(dispatch_file))
    return runs


def _parse_launched_at(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def write_worker_utilization_summary(root: Path) -> str:
    by_worker: dict[str, dict[str, int | float]] = {}
    launched_at_values: list[str] = []
    for run in _iter_dispatch_runs(root):
        worker_id = run.get("worker_id", "unknown")
        stats = by_worker.setdefault(
            worker_id,
            {
                "dispatches": 0,
                "reclaims": 0,
                "completed": 0,
                "review_notes": 0,
                "handoffs_out": 0,
            },
        )
        stats["dispatches"] += 1
        if run.get("dispatch_state") == "reclaimed":
            stats["reclaims"] += 1
        if run.get("dispatch_state") == "completed":
            stats["completed"] += 1
        if run.get("handoff", {}).get("output_summary_ref"):
            stats["review_notes"] += 1
        if run.get("reclaim", {}).get("successor_dispatch_id"):
            stats["handoffs_out"] += 1
        if run.get("launched_at"):
            launched_at_values.append(run["launched_at"])

    launched_at_values.sort()
    lines = [
        "# Worker Utilization Baseline",
        "",
        f"- period_start: {launched_at_values[0] if launched_at_values else 'n/a'}",
        f"- period_end: {launched_at_values[-1] if launched_at_values else 'n/a'}",
        f"- total_dispatches: {sum(int(stats['dispatches']) for stats in by_worker.values())}",
        f"- workers: {len(by_worker)}",
        "",
    ]
    for worker_id, stats in sorted(by_worker.items()):
        average_handoffs = (
            round(float(stats["handoffs_out"]) / float(stats["dispatches"]), 2)
            if stats["dispatches"]
            else 0.0
        )
        lines.extend(
            [
                f"## {worker_id}",
                "",
                f"- dispatches: {stats['dispatches']}",
                f"- reclaims: {stats['reclaims']}",
                f"- completed: {stats['completed']}",
                f"- review_notes: {stats['review_notes']}",
                f"- handoffs_out: {stats['handoffs_out']}",
                f"- average_handoffs_per_dispatch: {average_handoffs}",
                "",
            ]
        )

    output = root / ".omo" / "summaries" / "worker-utilization-baseline.md"
    write_text_atomic(output, "\n".join(lines).rstrip() + "\n")
    return str(output.relative_to(root))
