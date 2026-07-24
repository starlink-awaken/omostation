"""BOS URI 进程池 — 子进程复用管理"""

from __future__ import annotations

import logging
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .services import POC_SERVICES, BosService, _with_uv_package

_log = logging.getLogger(__name__)


def _workspace_root() -> Path:
    return Path(os.environ.get("WORKSPACE_ROOT", Path.home() / "Workspace"))


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
        if not cmd:
            raise ValueError(f"service {uri} has empty command")
        # Scheme C 5b: process-pool spawn via container executor facade
        from agora.execution.container_executor import SpawnSpec, spawn_sync

        command, *args = cmd
        _log.info("spawn %s: %s", uri, " ".join(cmd))
        proc, handle = spawn_sync(
            SpawnSpec(
                command=command,
                args=tuple(args),
                cwd=str(_workspace_root()),
                env=None,
                service_name=getattr(service, "name", None) or uri,
                text=True,
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _log.info(
            "spawn backend=%s profile=%s docker_wrapped=%s uri=%s",
            handle.backend,
            handle.profile,
            handle.docker_wrapped,
            uri,
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

    def respawn_dead(self, services: list[BosService] | None = None) -> list[str]:
        """检查并重新 spawn 已退出进程.

        Args:
            services: 可选服务列表；未提供时从 POC_SERVICES 查找。
        """
        services = services or POC_SERVICES
        by_uri = {s.uri: s for s in services}
        respawned: list[str] = []
        for uri, proc in list(self._procs.items()):
            if proc.poll() is not None:
                _log.info("respawn dead process: %s", uri)
                self._procs.pop(uri, None)
                svc = by_uri.get(uri)
                if svc is not None:
                    self.get_or_spawn(svc)
                    respawned.append(uri)
        return respawned

    def shutdown(self, uri: str | None = None) -> int:
        if uri:
            proc = self._procs.pop(uri, None)
            if proc:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2.0)
                return 0
            return 1
        count = 0
        for proc in list(self._procs.values()):
            proc.terminate()
            count += 1
        for uri, proc in list(self._procs.items()):
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2.0)
        self._procs.clear()
        return count


_pool = ProcessPool()


def get_pool() -> ProcessPool:
    return _pool
