from __future__ import annotations

"""
---
Type: API
Status: ACTIVE
Version: 1.0.0
Owner: "@Builder"
Layer: organs/D-Gateway/organs
Summary: Plugin marketplace mock API handler for the MCP server.
Tags:
  - plugin
  - market
  - api
  - m11
Authority: nucleus/Z-Core/L2-Law/plugin-spec.md
---
"""

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# PluginMarketAPI ≡ Module
# 内涵 ≝ {MarketPlugin, PluginMarketAPI, get_plugin_market_api}
# 外延 ≝ {e | e ∈ Organs ∧ uses(e, PluginMarketAPI)}
# 功能 ⊢ {List_Plugins, Get_Plugin, Install_Plugin, Search_Plugins}
# =============================================================================
import time  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # type: ignore[import-untyped]  # noqa: E402

PLUGIN_REGISTRY_PATH = Path("config/plugin_registry.yaml")


@dataclass
class MarketPlugin:
    """In-memory representation of a marketplace plugin entry."""

    name: str
    version: str
    description: str
    author: str
    tags: list[str] = field(default_factory=list)
    download_url: str = ""
    downloads: int = 0
    rating: float = 0.0


class PluginMarketAPI:
    """In-memory plugin marketplace API backed by the plugin registry YAML."""

    def __init__(self, registry_path: str | Path = PLUGIN_REGISTRY_PATH) -> None:
        self.status = "active"
        self._registry_path = Path(registry_path)
        self._plugins: dict[str, MarketPlugin] = {}
        self._load_registry()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_registry(self) -> None:
        """Populate in-memory store from config/plugin_registry.yaml."""
        if not self._registry_path.exists():
            return
        try:
            with self._registry_path.open() as fh:
                data: dict = yaml.safe_load(fh) or {}
        except (yaml.YAMLError, ValueError, OSError):
            data = {}
        for entry in data.get("plugins", []):
            name = entry.get("name", "")
            if not name:
                continue
            self._plugins[name] = MarketPlugin(
                name=name,
                version=entry.get("version", "0.0.1"),
                description=entry.get("description", ""),
                author=entry.get("author", ""),
                tags=list(entry.get("tags", [])),
                download_url=entry.get("download_url", ""),
                downloads=int(entry.get("downloads", 0)),
                rating=float(entry.get("rating", 0.0)),
            )

    def _to_dict(self, p: MarketPlugin) -> dict:
        return {
            "name": p.name,
            "version": p.version,
            "description": p.description,
            "author": p.author,
            "tags": p.tags,
            "download_url": p.download_url,
            "downloads": p.downloads,
            "rating": p.rating,
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_plugins(self, tag: str | None = None) -> list[dict]:
        """Return all marketplace plugins, optionally filtered by *tag*."""
        plugins = list(self._plugins.values())
        if tag:
            plugins = [p for p in plugins if tag in p.tags]
        return [self._to_dict(p) for p in plugins]

    def get_plugin(self, name: str) -> dict | None:
        """Return plugin details for *name*, or ``None`` if not found."""
        p = self._plugins.get(name)
        return self._to_dict(p) if p is not None else None

    def install_plugin(self, name: str) -> dict:
        """Simulate plugin install — increments download counter.

        Returns a success/error dict suitable for API consumers.
        """
        if name not in self._plugins:
            return {
                "success": False,
                "error": f"Plugin {name!r} not found in marketplace",
            }
        self._plugins[name].downloads += 1
        return {
            "success": True,
            "plugin": name,
            "version": self._plugins[name].version,
            "installed_at": time.time(),
        }

    def search_plugins(self, query: str) -> list[dict]:
        """Full-text search across name, description, and tags."""
        q = query.lower()
        results = []
        for p in self._plugins.values():
            if (
                q in p.name.lower()
                or q in p.description.lower()
                or any(q in tag for tag in p.tags)
            ):
                results.append(self._to_dict(p))
        return results

    def register_plugin(self, plugin: dict) -> dict:
        """Register a new plugin entry (in-memory only, not persisted)."""
        name = plugin.get("name", "")
        if not name:
            return {"success": False, "error": "Plugin name is required"}
        self._plugins[name] = MarketPlugin(
            name=name,
            version=plugin.get("version", "0.0.1"),
            description=plugin.get("description", ""),
            author=plugin.get("author", ""),
            tags=list(plugin.get("tags", [])),
            download_url=plugin.get("download_url", ""),
            downloads=int(plugin.get("downloads", 0)),
            rating=float(plugin.get("rating", 0.0)),
        )
        return {"success": True, "plugin": name}


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------

_market_api: PluginMarketAPI | None = None


def get_plugin_market_api() -> PluginMarketAPI:
    """Return the module-level singleton :class:`PluginMarketAPI` instance."""
    global _market_api
    if _market_api is None:
        _market_api = PluginMarketAPI()
    return _market_api
