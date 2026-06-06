# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Cross-session state persistence for workflow-backed autonomous planning."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

_log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[5]
STATE_DIR = PROJECT_ROOT / "data" / "planning_results"
STATE_FILE = STATE_DIR / "planner_state.json"


@dataclass
class StepCheckpoint:
    step_name: str
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    error_message: str | None = None
    result_checksum: str | None = None


@dataclass
class PipelineState:
    pipeline_id: str
    goal: str
    steps: list[StepCheckpoint] = field(default_factory=list)
    current_step_index: int = 0
    started_at: str = ""
    updated_at: str = ""
    checksum: str = ""

    def compute_checksum(self) -> str:
        data = asdict(self)
        data.pop("checksum", None)
        content = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(str(tmp), str(path))


def _load_state() -> PipelineState | None:
    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        steps = [
            StepCheckpoint(
                step_name=step.get("step_name", ""),
                status=step.get("status", "pending"),
                started_at=step.get("started_at"),
                completed_at=step.get("completed_at"),
                error_message=step.get("error_message"),
                result_checksum=step.get("result_checksum"),
            )
            for step in data.get("steps", [])
            if isinstance(step, dict)
        ]
        state = PipelineState(
            pipeline_id=data.get("pipeline_id", ""),
            goal=data.get("goal", ""),
            steps=steps,
            current_step_index=data.get("current_step_index", 0),
            started_at=data.get("started_at", ""),
            updated_at=data.get("updated_at", ""),
            checksum=data.get("checksum", ""),
        )
        stored = data.get("checksum", "")
        if stored and state.compute_checksum() != stored:
            _log.warning("State checksum mismatch; ignoring corrupted state")
            return None
        return state
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def _save_state(state: PipelineState) -> None:
    state.updated_at = datetime.now(UTC).isoformat()
    state.checksum = state.compute_checksum()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _atomic_write(STATE_FILE, json.dumps(asdict(state), ensure_ascii=False, indent=2))


def save_pipeline_state(goal: str, steps: list[str]) -> PipelineState:
    now = datetime.now(UTC).isoformat()
    state = PipelineState(
        pipeline_id=str(uuid.uuid4())[:8],
        goal=goal,
        steps=[StepCheckpoint(step_name=name, status="pending") for name in steps],
        started_at=now,
        updated_at=now,
    )
    _save_state(state)
    return state


def checkpoint_step(
    state: PipelineState,
    step_name: str,
    status: str,
    error: str | None = None,
) -> PipelineState:
    now = datetime.now(UTC).isoformat()
    for checkpoint in state.steps:
        if checkpoint.step_name == step_name:
            checkpoint.status = status
            checkpoint.completed_at = now
            if error:
                checkpoint.error_message = error
            break
    state.current_step_index = next(
        (i for i, checkpoint in enumerate(state.steps) if checkpoint.status == "pending"),
        len(state.steps),
    )
    _save_state(state)
    return state


def get_resume_state(goal: str, requested_steps: list[str]) -> tuple[list[str], PipelineState | None]:
    state = _load_state()
    if state is None:
        return requested_steps, None
    saved_steps = [checkpoint.step_name for checkpoint in state.steps]
    if state.goal != goal or saved_steps != requested_steps:
        return requested_steps, None
    passed = {checkpoint.step_name for checkpoint in state.steps if checkpoint.status == "passed"}
    remaining = [name for name in requested_steps if name not in passed]
    if len(remaining) == len(requested_steps):
        return requested_steps, None
    state.current_step_index = len(passed)
    _save_state(state)
    return remaining, state


def clear_state() -> None:
    try:
        STATE_FILE.unlink(missing_ok=True)
    except OSError as exc:
        _log.debug("Failed to clear planner state: %s", exc)
