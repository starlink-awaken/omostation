"""Plugin Manager -- full lifecycle with sandbox isolation."""

from __future__ import annotations

import time
from typing import Any

from runtime.executor.engine_types import (
    EngineError,
    ErrorCategory,
    PluginLoadResult,
    PluginMetadata,
    PluginPermission,
    PluginSandboxConfig,
    PluginStateInfo,
    PluginStatus,
    PluginType,
)


class PluginSandbox:
    """Sandbox isolation for plugin execution."""

    def __init__(self, config: PluginSandboxConfig, plugin_id: str) -> None:
        self._config = config
        self._plugin_id = plugin_id
        self._sandbox_id = f"sandbox-{plugin_id}-{time.time_ns()}"

    def check_read_path(self, file_path: str) -> bool:
        if self._config.deny_paths and any(file_path.startswith(d) or file_path == d for d in self._config.deny_paths):
            return False
        if self._config.allow_read_paths and not any(file_path.startswith(a) for a in self._config.allow_read_paths):
            return False
        return True

    def check_write_path(self, file_path: str) -> bool:
        if self._config.deny_paths and any(file_path.startswith(d) or file_path == d for d in self._config.deny_paths):
            return False
        if self._config.allow_write_paths and not any(file_path.startswith(a) for a in self._config.allow_write_paths):
            return False
        return True

    def check_network(self, url: str) -> bool:
        if not self._config.allow_network:
            return False
        if self._config.allow_domains and not any(d in url for d in self._config.allow_domains):
            return False
        return True

    def check_command(self, command: str) -> bool:
        if not self._config.allow_spawn:
            return False
        cmd = command.split()[0]
        if self._config.allow_commands and cmd not in self._config.allow_commands:
            return False
        return True

    async def execute_securely(self, fn: Any, *args: Any, **kw: Any) -> Any:
        if not self._config.enabled:
            return await fn(*args, **kw) if hasattr(fn, "__call__") else fn(*args, **kw)
        try:
            return await fn(*args, **kw) if hasattr(fn, "__call__") else fn(*args, **kw)
        except Exception as e:
            raise EngineError(f"Sandbox error in {self._plugin_id}: {e}", ErrorCategory.PLUGIN, original=e)


class PluginManager:
    """Manage plugin lifecycle: register, load, init, start, stop, unload."""

    def __init__(self, default_sandbox: PluginSandboxConfig | None = None) -> None:
        self._plugins: dict[str, PluginMetadata] = {}
        self._instances: dict[str, Any] = {}
        self._statuses: dict[str, PluginStatus] = {}
        self._sandboxes: dict[str, PluginSandbox] = {}
        self._timestamps: dict[str, dict[str, float]] = {}
        self._default_sandbox = default_sandbox or PluginSandboxConfig()

    def register(self, metadata: PluginMetadata) -> None:
        if metadata.plugin_id in self._plugins:
            raise ValueError(f"Plugin already registered: {metadata.plugin_id}")
        self._plugins[metadata.plugin_id] = metadata
        self._statuses[metadata.plugin_id] = PluginStatus.REGISTERED
        self._timestamps[metadata.plugin_id] = {"registered": time.time()}
        self._sandboxes[metadata.plugin_id] = PluginSandbox(
            PluginSandboxConfig(enabled=metadata.sandbox_enabled, **self._default_sandbox.__dict__), metadata.plugin_id
        )

    def batch_register(self, plugins: list[PluginMetadata]) -> list[PluginLoadResult]:
        results: list[PluginLoadResult] = []
        for p in plugins:
            try:
                self.register(p)
                results.append(PluginLoadResult(p.plugin_id, True))
            except ValueError as e:
                results.append(PluginLoadResult(p.plugin_id, False, str(e)))
        return results

    def has(self, plugin_id: str) -> bool:
        return plugin_id in self._plugins

    def get_metadata(self, plugin_id: str) -> PluginMetadata | None:
        return self._plugins.get(plugin_id)

    def get_status(self, plugin_id: str) -> PluginStatus | None:
        return self._statuses.get(plugin_id)

    def get_state_info(self, plugin_id: str) -> PluginStateInfo | None:
        meta = self._plugins.get(plugin_id)
        if meta is None:
            return None
        ts = self._timestamps.get(plugin_id, {})
        return PluginStateInfo(
            plugin_id=plugin_id,
            status=self._statuses.get(plugin_id, PluginStatus.REGISTERED),
            last_state_change=ts.get("started", ts.get("loaded", ts.get("registered", 0.0))),
            started_at=ts.get("started"),
        )

    def list_plugins(self) -> list[PluginMetadata]:
        return list(self._plugins.values())

    def list_by_type(self, plugin_type: PluginType) -> list[PluginMetadata]:
        return [p for p in self._plugins.values() if p.type == plugin_type]

    async def load(self, plugin_id: str) -> None:
        self._assert_registered(plugin_id)
        for dep in self._plugins[plugin_id].dependencies or []:
            if dep not in self._plugins:
                raise ValueError(f"Missing dependency: {dep}")
        self._statuses[plugin_id] = PluginStatus.LOADED
        self._timestamps[plugin_id]["loaded"] = time.time()

    async def initialize(self, plugin_id: str, instance: Any = None) -> None:
        self._assert_registered(plugin_id)
        if self._statuses.get(plugin_id) != PluginStatus.LOADED:
            raise ValueError(f"Plugin not loaded: {plugin_id}")
        self._instances[plugin_id] = instance
        self._statuses[plugin_id] = PluginStatus.ACTIVE
        self._timestamps[plugin_id]["started"] = time.time()

    async def start(self, plugin_id: str) -> None:
        self._assert_registered(plugin_id)
        if self._statuses.get(plugin_id) != PluginStatus.LOADED:
            raise ValueError(f"Plugin not ready: {plugin_id}")
        self._statuses[plugin_id] = PluginStatus.ACTIVE
        self._timestamps[plugin_id]["started"] = time.time()

    async def stop(self, plugin_id: str) -> None:
        self._assert_registered(plugin_id)
        if self._statuses.get(plugin_id) != PluginStatus.ACTIVE:
            return
        self._statuses[plugin_id] = PluginStatus.LOADED

    async def unload(self, plugin_id: str) -> None:
        self._assert_registered(plugin_id)
        dependents = self._find_dependents(plugin_id)
        if dependents:
            raise ValueError(f"Cannot unload {plugin_id}: needed by {chr(44).join(dependents)}")
        if self._statuses.get(plugin_id) == PluginStatus.ACTIVE:
            await self.stop(plugin_id)
        self._instances.pop(plugin_id, None)
        self._plugins.pop(plugin_id, None)
        self._statuses.pop(plugin_id, None)
        self._sandboxes.pop(plugin_id, None)

    async def start_all(self) -> list[PluginLoadResult]:
        results: list[PluginLoadResult] = []
        for pid in self._topological_sort(list(self._plugins.keys())):
            if self._statuses.get(pid) == PluginStatus.LOADED:
                try:
                    await self.start(pid)
                    results.append(PluginLoadResult(pid, True))
                except Exception as e:
                    results.append(PluginLoadResult(pid, False, str(e)))
        return results

    async def stop_all(self) -> list[PluginLoadResult]:
        results: list[PluginLoadResult] = []
        for pid in reversed(self._topological_sort(list(self._plugins.keys()))):
            if self._statuses.get(pid) == PluginStatus.ACTIVE:
                try:
                    await self.stop(pid)
                    results.append(PluginLoadResult(pid, True))
                except Exception as e:
                    results.append(PluginLoadResult(pid, False, str(e)))
        return results

    async def unload_all(self) -> None:
        for pid in reversed(self._topological_sort(list(self._plugins.keys()))):
            try:
                await self.unload(pid)
            except Exception:
                pass

    def has_permission(self, plugin_id: str, permission: PluginPermission) -> bool:
        meta = self._plugins.get(plugin_id)
        if meta is None:
            return False
        return "*" in (meta.permissions or []) or permission in (meta.permissions or [])

    def check_permissions(self, plugin_id: str, required: list[PluginPermission]) -> dict[str, Any]:
        meta = self._plugins.get(plugin_id)
        if meta is None:
            return {"granted": False, "error": "Plugin not found"}
        perms = meta.permissions or []
        if "*" in perms:
            return {"granted": True}
        missing = [p for p in required if p not in perms]
        return {"granted": len(missing) == 0, "missing": missing or None}

    def get_sandbox(self, plugin_id: str) -> PluginSandbox | None:
        return self._sandboxes.get(plugin_id)

    def get_status_summary(self) -> dict[str, int]:
        summary: dict[str, int] = {}
        for s in self._statuses.values():
            summary[s.value] = summary.get(s.value, 0) + 1
        return {"total": len(self._plugins), "by_status": summary}  # type: ignore[dict-item]

    def _assert_registered(self, plugin_id: str) -> None:
        if plugin_id not in self._plugins:
            raise ValueError(f"Plugin not found: {plugin_id}")

    def _find_dependents(self, plugin_id: str) -> list[str]:
        return [pid for pid, meta in self._plugins.items() if plugin_id in (meta.dependencies or [])]

    def _topological_sort(self, plugin_ids: list[str]) -> list[str]:
        visited: set[str] = set()
        visiting: set[str] = set()
        result: list[str] = []

        def visit(pid: str) -> None:
            if pid in visited or pid in visiting:
                return
            visiting.add(pid)
            for dep in (self._plugins.get(pid).dependencies or []) if pid in self._plugins else []:  # type: ignore[union-attr]
                if dep in plugin_ids:
                    visit(dep)
            visiting.discard(pid)
            visited.add(pid)
            result.append(pid)

        for pid in plugin_ids:
            visit(pid)
        return result
