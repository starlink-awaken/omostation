"""BOS URI 进程池 — 子进程复用管理"""

from __future__ import annotations

import logging
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .services import BosService, _with_uv_package

_log = logging.getLogger(__name__)


@dataclass
class ProcessPool:
    """进程池 — 复用 stdio 子进程 (按 URI 索引)."""

    _procs: dict[str, subprocess.Popen] = field(default_factory=dict)
    seen_uris: set[str] = field(default_factory=set)

    @property
    def processes(self) -> dict[str, subprocess.Popen]:
        """Backward-compat alias for _procs."""
        return self._procs

    def _next_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def get_or_spawn(self, service: BosService) -> subprocess.Popen:
        uri = service.uri
        if uri in self._procs:
            proc = self._procs[uri]
            if proc.poll() is None:
                return proc
            _log.warning("进程 %s 已退出 (code=%s), 重新 spawn", uri, proc.returncode)
        cmd = _with_uv_package(service)
        _log.info("spawn %s: %s", uri, " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(Path.home() / "Workspace"),
        )
        self._procs[uri] = proc
        return proc

    def is_alive(self, uri: str) -> bool:
        proc = self._procs.get(uri)
        if proc is None:
            return False
        if proc.poll() is not None:
            self._procs.pop(uri, None)
            return False
        return True

    def respawn_dead(self) -> list[str]:
        respawned: list[str] = []
        for uri, proc in list(self._procs.items()):
            if proc.poll() is not None:
                _log.info("respawn dead process: %s", uri)
                self._procs.pop(uri, None)
                # Need service to respawn — caller must provide
        return respawned

    def shutdown(self, uri: str | None = None) -> int:
        if uri:
            proc = self._procs.pop(uri, None)
            if proc:
                proc.terminate()
                return 0
            return 1
        count = 0
        for proc in self._procs.values():
            proc.terminate()
            count += 1
        self._procs.clear()
        return count


_pool = ProcessPool()


def get_pool() -> ProcessPool:
    return _pool
