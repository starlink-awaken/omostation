"""Durable checkpoint store for the Swarm graph executor."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class WorkflowCheckpointStore:
    """Append-only JSONL checkpoints keyed by workflow run."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def save(
        self,
        workflow_run_id: str,
        *,
        status: str,
        next_node: str | None,
        visited: set[str],
        state: dict[str, Any],
        attempt: int = 1,
    ) -> dict[str, Any]:
        record = {
            "workflow_run_id": workflow_run_id,
            "status": status,
            "attempt": attempt,
            "next_node": next_node,
            "visited": sorted(visited),
            "state": state,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return record

    def latest(self, workflow_run_id: str) -> dict[str, Any] | None:
        matches = [record for record in self._read() if record.get("workflow_run_id") == workflow_run_id]
        return matches[-1] if matches else None


__all__ = ["WorkflowCheckpointStore"]
