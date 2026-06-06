"""Rollback history tracking — record, undo, and persist rollback operations.

Migrated from agentmesh rollback-history.ts.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RollbackRecord:
    """A single rollback operation record."""

    rollback_id: str
    project_id: str
    from_checkpoint: str
    to_checkpoint: str | None = None
    timestamp: float = field(default_factory=time.time)
    reason: str = ""
    success: bool = True
    error: str | None = None


class RollbackHistory:
    """Manage rollback history with persistence and undo support."""

    def __init__(self, db_path: str) -> None:
        db_dir = Path(db_path).parent
        self._history_path = db_dir / f"{Path(db_path).stem}-rollback-history.json"
        self._history: dict[str, list[RollbackRecord]] = {}
        self._loaded = False
        self._load()

    # -- History Management ------------------------------------------------

    def record(self, record: RollbackRecord) -> None:
        self._history.setdefault(record.project_id, []).append(record)
        self._save()

    def get_history(self, project_id: str) -> list[RollbackRecord]:
        return list(self._history.get(project_id, []))

    def get_all_history(self) -> dict[str, list[RollbackRecord]]:
        return {pid: list(recs) for pid, recs in self._history.items()}

    def clear_history(self, project_id: str) -> None:
        self._history.pop(project_id, None)
        self._save()

    def get_last_rollback(self, project_id: str) -> RollbackRecord | None:
        records = self._history.get(project_id)
        if not records:
            return None
        return records[-1]

    # -- Undo --------------------------------------------------------------

    async def undo_last_rollback(
        self,
        project_id: str,
        restore_fn: Callable[[str], Any],
    ) -> Any:
        records = self._history.get(project_id)
        if not records:
            raise ValueError(f"No rollback history for project: {project_id}")
        last = records[-1]
        if not last.success:
            raise ValueError("Last rollback failed, cannot undo")
        target_checkpoint = last.from_checkpoint
        try:
            restored = await restore_fn(target_checkpoint) if hasattr(restore_fn, "__call__") else restore_fn(target_checkpoint)
            records.pop()
            if not records:
                self._history.pop(project_id, None)
            self._save()
            return restored
        except Exception as exc:
            raise ValueError(f"Failed to undo rollback: {exc}") from exc

    def get_undoable_count(self, project_id: str) -> int:
        records = self._history.get(project_id)
        if not records:
            return 0
        return sum(1 for r in records if r.success)

    # -- Persistence -------------------------------------------------------

    def _load(self) -> None:
        if self._loaded:
            return
        try:
            if self._history_path.exists():
                raw = self._history_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                for pid, recs in data.items():
                    self._history[pid] = [RollbackRecord(**r) for r in recs]
        except Exception:
            self._history.clear()
        self._loaded = True

    def _save(self) -> None:
        try:
            data: dict[str, list[dict]] = {}
            for pid, recs in self._history.items():
                data[pid] = [asdict(r) for r in recs]
            self._history_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass  # swallow write errors

    @property
    def history_path(self) -> str:
        return str(self._history_path)
