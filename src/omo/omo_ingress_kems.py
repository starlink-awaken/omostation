"""KEMS-to-OMO ingress broker for evidence-bound planned tasks."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from .omo_ingress_task_lifecycle import create_planned_task
from .omo_task_schema import validate_task_data


def create_kems_planned_task(
    omo_dir: Path,
    *,
    task_payload: dict[str, Any],
    source_ref: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Create an idempotent OMO planned task from a KEMS adapter payload.

    This is ingress-only. Worker assignment, approval, promotion, dispatch,
    and execution remain OMO-controlled operations.
    """
    if not source_ref.strip():
        raise ValueError("KEMS ingress requires a stable source_ref")
    payload = deepcopy(task_payload)
    payload.setdefault("status", "candidate")
    payload.setdefault("assigned_to", None)
    payload.setdefault("dispatch_id", None)
    payload.setdefault("run_ref", None)
    payload.setdefault("approval_ref", None)
    payload.setdefault("review_ref", None)
    errors = validate_task_data(payload, group="planned")
    if errors:
        raise ValueError("invalid KEMS planned task: " + "; ".join(errors))
    return create_planned_task(
        omo_dir,
        task_data=payload,
        ingress_plane="projects/omo:kems",
        source_ref=source_ref,
        now=now,
    )
