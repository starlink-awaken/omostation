"""Uvicorn lifecycle with conservative Unix-socket ownership checks."""

from __future__ import annotations

import asyncio
import math
import os
import socket
import stat
import time
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

import uvicorn
from fastapi import FastAPI


class ServerLike(Protocol):
    started: bool
    should_exit: bool

    async def serve(self, sockets: list[socket.socket] | None = None) -> None: ...


ServerFactory = Callable[[uvicorn.Config], ServerLike]


class DaemonServer:
    """Own exactly one private UDS listener and support idempotent restart."""

    def __init__(
        self,
        application: FastAPI,
        *,
        socket_path: Path,
        server_factory: ServerFactory | None = None,
        startup_timeout: float = 30.0,
        shutdown_timeout: int = 2,
    ) -> None:
        self._application = application
        self.socket_path = socket_path
        self._server_factory = server_factory or _uvicorn_server
        if not math.isfinite(startup_timeout) or startup_timeout <= 0:
            raise ValueError("startup timeout must be finite and positive")
        self._startup_timeout = startup_timeout
        if shutdown_timeout <= 0:
            raise ValueError("shutdown timeout must be positive")
        self._shutdown_timeout = shutdown_timeout
        self._server: ServerLike | None = None
        self._task: asyncio.Task[None] | None = None
        self._socket_identity: tuple[int, int] | None = None
        self._listener: socket.socket | None = None

    @property
    def task_settled(self) -> bool:
        return self._task is None or self._task.done()

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            raise RuntimeError("daemon server is already running")
        if len(os.fsencode(self.socket_path)) >= 104:
            raise RuntimeError("Unix socket path exceeds the platform limit")
        self._prepare_parent()
        self._prepare_socket_path()
        listener = self._bind_private_socket()
        self._listener = listener
        config = uvicorn.Config(
            self._application,
            log_level="warning",
            access_log=False,
            timeout_graceful_shutdown=self._shutdown_timeout,
        )
        server = self._server_factory(config)
        self._server = server
        self._task = asyncio.create_task(server.serve(sockets=[listener]), name="omlxcd-uvicorn")
        deadline = time.monotonic() + self._startup_timeout
        try:
            while not server.started:
                if self._task.done():
                    exception = self._task.exception()
                    raise RuntimeError("daemon server failed to start") from exception
                if time.monotonic() >= deadline:
                    raise RuntimeError("daemon server startup timed out")
                await asyncio.sleep(0.01)
        except BaseException:
            with suppress(Exception):
                await self.stop()
            raise

    async def stop(self) -> None:
        server, task = self._server, self._task
        self._server = None
        if server is not None:
            server.should_exit = True
        interrupted = False
        if task is not None:
            try:
                done, pending = await asyncio.wait({task}, timeout=self._shutdown_timeout + 0.5)
                del done
                if pending:
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            except asyncio.CancelledError:
                interrupted = True
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            finally:
                self._task = None
        self._remove_owned_socket()
        self._socket_identity = None
        listener, self._listener = self._listener, None
        if listener is not None:
            listener.close()
        if task is not None:
            try:
                exception = task.exception()
            except asyncio.CancelledError:
                exception = None
            if exception is not None:
                raise RuntimeError("daemon server stopped unexpectedly") from exception
            if interrupted:
                raise asyncio.CancelledError

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    def _prepare_parent(self) -> None:
        parent = self.socket_path.parent
        if parent.exists() or parent.is_symlink():
            info = parent.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                raise RuntimeError("Unix socket parent must be a real directory")
            if info.st_uid != os.getuid():
                raise RuntimeError("Unix socket parent is not owned by the current user")
        else:
            parent.mkdir(parents=True, mode=0o700)
        os.chmod(parent, 0o700, follow_symlinks=False)
        if stat.S_IMODE(parent.stat().st_mode) != 0o700:
            raise RuntimeError("Unix socket parent permissions are not private")

    def _prepare_socket_path(self) -> None:
        try:
            info = self.socket_path.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISLNK(info.st_mode):
            raise RuntimeError("refusing Unix socket symlink")
        if not stat.S_ISSOCK(info.st_mode):
            raise RuntimeError("refusing non-socket Unix path")
        if _socket_accepts_connections(self.socket_path):
            raise RuntimeError("active Unix socket already exists")
        if info.st_uid != os.getuid():
            raise RuntimeError("stale Unix socket is not owned by the current user")
        self.socket_path.unlink()

    def _bind_private_socket(self) -> socket.socket:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            listener.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600, follow_symlinks=False)
            verified = self.socket_path.lstat()
            if not stat.S_ISSOCK(verified.st_mode) or stat.S_IMODE(verified.st_mode) != 0o600:
                raise RuntimeError("daemon Unix socket permissions are not private")
            self._socket_identity = (verified.st_dev, verified.st_ino)
            listener.listen(2048)
            listener.setblocking(False)
            return listener
        except BaseException:
            listener.close()
            self._remove_owned_socket()
            self._socket_identity = None
            raise

    def _remove_owned_socket(self) -> None:
        identity = self._socket_identity
        if identity is None:
            return
        try:
            info = self.socket_path.lstat()
        except FileNotFoundError:
            return
        if stat.S_ISSOCK(info.st_mode) and (info.st_dev, info.st_ino) == identity:
            self.socket_path.unlink()


def _socket_accepts_connections(path: Path) -> bool:
    probe = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    probe.settimeout(0.1)
    try:
        return probe.connect_ex(str(path)) == 0
    finally:
        probe.close()


def _uvicorn_server(config: uvicorn.Config) -> ServerLike:
    server = uvicorn.Server(config)
    server.install_signal_handlers = _ignore_signals  # type: ignore[method-assign]
    return server


def _ignore_signals() -> Any:
    return None
