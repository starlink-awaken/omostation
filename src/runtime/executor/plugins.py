"""Plugin Manager — lifecycle management for agent plugins with sandbox isolation."""

import time
from dataclasses import dataclass, field
from enum import StrEnum


class PluginState(StrEnum):
    REGISTERED = "registered"
    LOADED = "loaded"
    ACTIVE = "active"
    DISABLED = "disabled"
    FAILED = "failed"

@dataclass
class PluginDef:
    name: str
    version: str = "1.0.0"
    description: str = ""
    entry_point: str = ""
    capabilities: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    state: PluginState = PluginState.REGISTERED
    loaded_at: float = 0.0

@dataclass
class PluginSandboxConfig:
    """Sandbox configuration for a plugin."""
    allow_filesystem: bool = False
    allow_network: bool = False
    allow_subprocess: bool = False
    allow_imports: list[str] = field(default_factory=list)
    max_memory_mb: int = 128
    timeout_sec: float = 30.0

class PluginManager:
    """Manage plugin lifecycle with sandbox isolation."""

    def __init__(self):
        self._plugins: dict[str, PluginDef] = {}  # type: ignore[annotation-unchecked]
        self._sandboxes: dict[str, PluginSandboxConfig] = {}  # type: ignore[annotation-unchecked]

    def register(self, name: str, version: str = "1.0.0", entry_point: str = "",
                 capabilities: list[str] | None = None, permissions: list[str] | None = None) -> str:
        plugin = PluginDef(name=name, version=version, entry_point=entry_point,
                           capabilities=capabilities or [], permissions=permissions or [])
        self._plugins[name] = plugin
        return name

    def configure_sandbox(self, name: str, config: PluginSandboxConfig):
        self._sandboxes[name] = config

    def load(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        if not plugin or plugin.state not in (PluginState.REGISTERED, PluginState.DISABLED):
            return False
        plugin.state = PluginState.LOADED
        plugin.loaded_at = time.time()
        return True

    def activate(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        if not plugin or plugin.state != PluginState.LOADED:
            return False
        try:
            plugin.state = PluginState.ACTIVE
            return True
        except Exception:
            plugin.state = PluginState.FAILED
            return False

    def disable(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        if not plugin:
            return False
        plugin.state = PluginState.DISABLED
        return True

    def get_sandbox(self, name: str) -> PluginSandboxConfig:
        return self._sandboxes.get(name, PluginSandboxConfig())

    def check_permission(self, name: str, permission: str) -> bool:
        plugin = self._plugins.get(name)
        return plugin is not None and permission in plugin.permissions

    def list_active(self) -> list[PluginDef]:
        return [p for p in self._plugins.values() if p.state == PluginState.ACTIVE]

    def get_status(self) -> dict:
        states = {}  # type: ignore[var-annotated]
        for p in self._plugins.values():
            states.setdefault(p.state.value, 0)
            states[p.state.value] += 1
        return {"total": len(self._plugins), "by_state": states}
