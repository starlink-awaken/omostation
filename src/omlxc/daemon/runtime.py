"""Ordered, restart-safe lifecycle for daemon-owned runtime components."""

from __future__ import annotations

from typing import Protocol


class RuntimeComponent(Protocol):
    async def start(self) -> None: ...

    async def close(self) -> None: ...


class DaemonRuntime:
    """Start config/storage, recovery, then events; close in reverse order."""

    def __init__(
        self,
        *,
        config_runtime: RuntimeComponent,
        recovery: RuntimeComponent,
        event_runtime: RuntimeComponent,
    ) -> None:
        self._components = (config_runtime, recovery, event_runtime)
        self._started: list[RuntimeComponent] = []
        self._ready = False
        self._diagnostic = "not_started"

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def diagnostic(self) -> str:
        return self._diagnostic

    @property
    def task_settled(self) -> bool:
        return all(bool(getattr(component, "task_settled", True)) for component in self._components)

    async def start(self) -> None:
        if self._ready:
            return
        self._diagnostic = "starting"
        try:
            for component in self._components:
                await component.start()
                self._started.append(component)
        except BaseException as exc:
            self._diagnostic = "runtime_startup_failed"
            await self._close_started()
            raise RuntimeError("daemon runtime startup failed") from exc
        self._ready = True
        self._diagnostic = "ready"

    async def close(self) -> None:
        self._ready = False
        await self._close_started()
        if self._diagnostic != "runtime_startup_failed":
            self._diagnostic = "closed"

    async def _close_started(self) -> None:
        while self._started:
            component = self._started.pop()
            try:
                await component.close()
            except Exception:
                self._diagnostic = "runtime_shutdown_failed"
