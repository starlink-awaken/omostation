"""Checkpoint Manager — save, restore, and rollback project execution state."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class Checkpoint:
    """Point-in-time snapshot of a project's state."""

    id: str
    project_id: str
    phase: str
    timestamp: float
    description: str
    recoverable: bool = True
    state_json: str = ""


@dataclass
class RollbackPreview:
    target_checkpoint: Checkpoint
    will_be_removed: list[dict[str, Any]] = field(default_factory=list)
    will_be_added: list[dict[str, Any]] = field(default_factory=list)
    phase_change: dict[str, str] = field(default_factory=dict)
    decisions_lost: int = 0
    token_diff: int = 0
    risks: list[str] = field(default_factory=list)


@dataclass
class RollbackOptions:
    scope: str = "full"  # full | state | artifacts | decisions
    preserve_artifacts: list[str] = field(default_factory=list)
    preserve_decision_indices: list[int] = field(default_factory=list)
    preserve_token_usage: bool = False
    create_backup: bool = True
    force: bool = False


# ---------------------------------------------------------------------------
# CheckpointManager
# ---------------------------------------------------------------------------


class CheckpointManager:
    """In-memory checkpoint management with JSON serialization."""

    def __init__(self) -> None:
        self._checkpoints: dict[str, Checkpoint] = {}
        self._projects: dict[str, dict[str, Any]] = {}
        self._sequence: int = 0

    # -- Project persistence -------------------------------------------------

    def save_project_state(self, project_id: str, state: dict[str, Any]) -> None:
        state["updated_at"] = time.time()
        self._projects[project_id] = dict(state)

    def load_project_state(self, project_id: str) -> dict[str, Any] | None:
        raw = self._projects.get(project_id)
        if raw is None:
            return None
        return dict(raw)

    def list_projects(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for pid, state in self._projects.items():
            result.append({"project_id": pid, "project_name": state.get("project_name", ""), "updated_at": state.get("updated_at", 0)})
        result.sort(key=lambda x: x["updated_at"], reverse=True)
        return result

    def delete_project(self, project_id: str) -> None:
        self._projects.pop(project_id, None)
        keys_to_delete = [k for k, cp in self._checkpoints.items() if cp.project_id == project_id]
        for k in keys_to_delete:
            del self._checkpoints[k]

    # -- Checkpoint operations -----------------------------------------------

    def create_checkpoint(self, project_id: str, state: dict[str, Any], description: str = "") -> Checkpoint:
        self._sequence += 1
        now = time.time()

        cp = Checkpoint(
            id=uuid.uuid4().hex[:16],
            project_id=project_id,
            phase=str(state.get("current_phase", "")),
            timestamp=now,
            description=description or f"Checkpoint at {now}",
            recoverable=True,
            state_json=json.dumps(state),
        )
        self._checkpoints[cp.id] = cp
        self.save_project_state(project_id, state)
        return cp

    def restore_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        cp = self._checkpoints.get(checkpoint_id)
        if cp is None:
            msg = f"Checkpoint not found: {checkpoint_id}"
            raise ValueError(msg)
        try:
            return json.loads(cp.state_json)
        except json.JSONDecodeError as exc:
            msg = f"Failed to parse checkpoint state: {exc}"
            raise ValueError(msg) from exc

    def list_checkpoints(self, project_id: str) -> list[Checkpoint]:
        cps = [cp for cp in self._checkpoints.values() if cp.project_id == project_id]
        cps.sort(key=lambda x: x.timestamp, reverse=True)
        return cps

    def delete_checkpoint(self, checkpoint_id: str) -> None:
        if checkpoint_id not in self._checkpoints:
            msg = f"Checkpoint not found: {checkpoint_id}"
            raise ValueError(msg)
        del self._checkpoints[checkpoint_id]

    def get_latest_checkpoint(self, project_id: str) -> Checkpoint | None:
        cps = self.list_checkpoints(project_id)
        return cps[0] if cps else None

    # -- Rollback operations -------------------------------------------------

    def preview_rollback(self, project_id: str, checkpoint_id: str) -> RollbackPreview:
        current = self.load_project_state(project_id)
        if current is None:
            msg = f"Project not found: {project_id}"
            raise ValueError(msg)

        cp_row = self._checkpoints.get(checkpoint_id)
        if cp_row is None:
            msg = f"Checkpoint not found: {checkpoint_id}"
            raise ValueError(msg)

        old_state = json.loads(cp_row.state_json)
        if old_state.get("project_id") != project_id:
            msg = f"Checkpoint {checkpoint_id} does not belong to project {project_id}"
            raise ValueError(msg)

        current_artifacts = {a.get("id") for a in current.get("artifacts", [])}
        old_artifacts = {a.get("id") for a in old_state.get("artifacts", [])}

        removed = [a for a in current.get("artifacts", []) if a.get("id") not in old_artifacts]
        added = [a for a in old_state.get("artifacts", []) if a.get("id") not in current_artifacts]

        risks: list[str] = []
        decisions_lost = max(0, len(current.get("decisions", [])) - len(old_state.get("decisions", [])))
        if decisions_lost > 0:
            risks.append(f"{decisions_lost} decisions will be lost")

        phase_from = str(current.get("current_phase", ""))
        phase_to = str(old_state.get("current_phase", ""))
        if phase_from != phase_to:
            risks.append(f"Phase will change from {phase_from} to {phase_to}")

        if removed:
            risks.append(f"{len(removed)} artifacts will be removed")

        return RollbackPreview(
            target_checkpoint=cp_row,
            will_be_removed=removed,
            will_be_added=added,
            phase_change={"from": phase_from, "to": phase_to},
            decisions_lost=decisions_lost,
            token_diff=old_state.get("total_token_usage", 0) - current.get("total_token_usage", 0),
            risks=risks,
        )

    def rollback(self, project_id: str, checkpoint_id: str, options: RollbackOptions | None = None) -> dict[str, Any]:
        opts = options or RollbackOptions()
        preview = self.preview_rollback(project_id, checkpoint_id)
        restored = self.restore_checkpoint(checkpoint_id)
        current = self.load_project_state(project_id)

        if current is None:
            msg = f"Project not found: {project_id}"
            raise ValueError(msg)

        if opts.scope == "artifacts":
            restored["artifacts"] = preview.will_be_added
            restored["current_phase"] = current.get("current_phase")
            restored["decisions"] = current.get("decisions", [])
            restored["total_token_usage"] = current.get("total_token_usage", 0)

        elif opts.scope == "decisions":
            restored["current_phase"] = current.get("current_phase")
            restored["artifacts"] = current.get("artifacts", [])

        elif opts.scope == "state":
            restored["artifacts"] = current.get("artifacts", [])

        restored["updated_at"] = time.time()
        self.save_project_state(project_id, restored)
        return restored

    # -- Utility -------------------------------------------------------------

    def close(self) -> None:
        self._checkpoints.clear()
        self._projects.clear()
