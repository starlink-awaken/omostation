"""OMO-governed write bridge for AetherForge swarm components.

Swarm modules may read Workspace state directly, but mutations must be executed
by the OMO core.  This adapter keeps the dependency optional at import time and
fails explicitly when a governed write is requested outside a Workspace checkout.
"""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


class GovernedIOUnavailableError(RuntimeError):
    """Raised when the Workspace OMO broker cannot service a write."""


def _workspace_root_for(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    for parent in (resolved, *resolved.parents):
        if parent.name in {".omo", "spaces"}:
            return parent.parent
    raise ValueError(f"governed path must be under .omo/ or spaces/: {path}")


@lru_cache(maxsize=4)
def _omo_primitives(workspace_root: Path) -> tuple[Any, Any, Any]:
    omo_src = workspace_root / "projects" / "omo" / "src"
    if not (omo_src / "omo").is_dir():
        raise GovernedIOUnavailableError(f"OMO broker unavailable: {omo_src}")
    if str(omo_src) not in sys.path:
        sys.path.insert(0, str(omo_src))
    try:
        from omo.omo_io import (  # type: ignore[reportMissingImports]
            AppendOnlyLog as OMOAppendOnlyLog,
        )
        from omo.omo_io import fcntl_lock as omo_fcntl_lock  # type: ignore[reportMissingImports]
        from omo.omo_io import (  # type: ignore[reportMissingImports]
            write_text_atomic as omo_write_text,
        )
    except ImportError as exc:
        raise GovernedIOUnavailableError(f"failed to import OMO broker: {exc}") from exc
    return omo_write_text, OMOAppendOnlyLog, omo_fcntl_lock


def write_text(path: Path, payload: str) -> None:
    """Write text atomically through the Workspace OMO core."""
    target = Path(path)
    workspace_root = _workspace_root_for(target)
    omo_write_text, _, _ = _omo_primitives(workspace_root)
    omo_write_text(target, payload)


def write_json(path: Path, payload: Any, *, sort_keys: bool = False) -> None:
    """Serialize JSON and persist it through the Workspace OMO core."""
    write_text(
        path,
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=sort_keys),
    )


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Append one JSONL record through OMO's append-only log abstraction."""
    target = Path(path)
    workspace_root = _workspace_root_for(target)
    _, append_only_log, fcntl_lock = _omo_primitives(workspace_root)
    lock_path = target.with_suffix(f"{target.suffix}.lock")
    append_only_log(target, lock=fcntl_lock(lock_path)).append(record, default=str)
