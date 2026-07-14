"""OMO Evolution Loop status surface.

Historical full daemon (Phase 6 debt auto-remediation) was removed in Batch 1
module cleanup; BOS still exposes ``bos://governance/evolution/loop`` as a
monitor entry. This module provides a thin ``get_loop_status`` that reads the
runtime evolution-loop state plane so the declaration stays resolvable.

State plane (runtime, gitignored):
  runtime/omo/_control/evolution/loop/{history,trace-index,YYYY-Www}.json
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _workspace_root() -> Path:
    env = os.environ.get("WORKSPACE") or os.environ.get("OMO_WORKSPACE")
    if env:
        return Path(env).expanduser().resolve()
    # Walk up from this file until we find the workspace marker.
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "projects" / "omo").is_dir() and (parent / "bin").is_dir():
            return parent
    # Fallback: projects/omo/src/omo/this_file.py → workspace root
    return here.parents[4]


def _loop_dirs(root: Path) -> list[Path]:
    """Candidate loop state directories (runtime primary, legacy .omo fallback)."""
    return [
        root / "runtime" / "omo" / "_control" / "evolution" / "loop",
        root / ".omo" / "_control" / "evolution" / "loop",
    ]


def get_loop_status(
    workspace: str | Path | None = None,
) -> dict[str, Any]:
    """Return a monitor snapshot of the evolution loop state plane.

    Used by BOS ``bos://governance/evolution/loop`` (internal transport).
    Does not run remediation — status only.
    """
    root = Path(workspace).expanduser().resolve() if workspace else _workspace_root()
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    loop_dir: Path | None = None
    for candidate in _loop_dirs(root):
        if candidate.is_dir():
            loop_dir = candidate
            break

    if loop_dir is None:
        return {
            "status": "absent",
            "alive": False,
            "checked_at": now,
            "loop_dir": None,
            "message": "evolution loop state plane not present",
            "history": None,
            "weeks": [],
        }

    history: dict[str, Any] | list[Any] | None = None
    history_path = loop_dir / "history.json"
    if history_path.is_file():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            history = {"error": "unreadable history.json"}

    weeks = sorted(p.name for p in loop_dir.glob("20*.json"))
    trace_index_path = loop_dir / "trace-index.json"
    has_trace = trace_index_path.is_file()

    return {
        "status": "present",
        "alive": True,
        "checked_at": now,
        "loop_dir": str(loop_dir.relative_to(root)) if loop_dir.is_relative_to(root) else str(loop_dir),
        "history": history,
        "weeks": weeks,
        "has_trace_index": has_trace,
        "message": f"evolution loop state plane at {loop_dir.name}/ ({len(weeks)} week snapshots)",
    }


class EvolutionLoop:
    """Minimal compatibility shell for archived scenario scripts.

    Full auto-remediation was retired; ``run_once`` is a no-op that reports
    current status rather than dispatching MutationProposals.
    """

    def __init__(self, interval_sec: int = 60) -> None:
        self.interval = interval_sec

    def run_once(self) -> int:
        """Status-only pass; returns 0 (no remediations dispatched)."""
        status = get_loop_status()
        return 0 if status.get("alive") else 0
