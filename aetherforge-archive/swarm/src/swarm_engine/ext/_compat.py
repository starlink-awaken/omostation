"""Compatibility stubs for migrated aetherforge-swarm-ext modules.

These symbols were originally imported from a missing private module.
Minimal implementations are provided so downstream modules can be imported.
"""

from __future__ import annotations

import enum
import logging
import os
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


class ProjectPaths:
    """Fallback path resolver."""

    ROOT: Path = Path(os.environ.get("AETHERFORGE_ROOT", Path.home() / ".aetherforge"))

    @classmethod
    def get_db_path(cls, *parts: str) -> Path:
        path = cls.ROOT / "data" / "db"
        for part in parts:
            path = path / part
        return path

    @classmethod
    def get_core_db_path(cls, name: str) -> Path:
        return cls.ROOT / "data" / "db" / name


class WorkerState(enum.Enum):
    """Placeholder worker state enumeration."""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class WorkerHandle:
    """Placeholder worker handle."""

    def __init__(self, worker_id: str, state: WorkerState = WorkerState.IDLE) -> None:
        self.worker_id = worker_id
        self.state = state


class InferenceOracle:
    """Placeholder inference oracle."""

    _instance: InferenceOracle | None = None

    @classmethod
    def get_instance(cls) -> InferenceOracle:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def infer(self, prompt: str, **kwargs: Any) -> str:
        _log.warning("InferenceOracle stub invoked for %r", prompt[:40])
        return ""


def get_path_resolver() -> ProjectPaths:
    return ProjectPaths()
