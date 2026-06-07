"""Provider plugin system — allow external packages to register custom LLM providers.

Third-party packages can register providers by exposing an entry point
in their ``pyproject.toml``::

    [project.entry-points."aetherforge.providers"]
    my-provider = "my_package.my_provider:MyProvider"

The provider class must inherit from :class:`LLMProvider` and implement
all abstract methods.

Usage::

    from llm_gateway.plugins import discover_plugins, register_plugin

    # Auto-discover installed plugins
    discover_plugins()

    # Or manually register
    from my_provider import MyProvider
    register_plugin("my-custom", MyProvider)
"""

from __future__ import annotations

import logging
from typing import Any

from .provider import LLMProvider, NoneProvider

_log = logging.getLogger(__name__)

# Global plugin registry: name → provider class
_plugin_registry: dict[str, type[LLMProvider]] = {}
_discovered = False


def register_plugin(name: str, provider_cls: type[LLMProvider]) -> None:
    """Register a custom provider plugin.

    Args:
        name: Provider identifier (e.g. ``"my-custom"``).
        provider_cls: A subclass of :class:`LLMProvider`.
    """
    if not issubclass(provider_cls, LLMProvider):
        raise TypeError(f"{provider_cls.__name__} must inherit from LLMProvider")
    _plugin_registry[name] = provider_cls
    _log.info("Registered provider plugin: %s → %s", name, provider_cls.__name__)


def unregister_plugin(name: str) -> None:
    """Remove a previously registered plugin."""
    _plugin_registry.pop(name, None)


def discover_plugins() -> int:
    """Auto-discover installed provider plugins via entry points.

    Scans the ``aetherforge.providers`` entry point group using
    ``importlib.metadata`` (PEP 302).

    Returns the number of plugins discovered.
    """
    global _discovered
    count = 0
    try:
        from importlib.metadata import entry_points

        eps = entry_points(group="aetherforge.providers")
        for ep in eps:
            try:
                cls = ep.load()
                if issubclass(cls, LLMProvider):
                    register_plugin(ep.name, cls)
                    count += 1
                else:
                    _log.warning(
                        "Plugin %s does not inherit from LLMProvider, skipping", ep.name
                    )
            except Exception as exc:
                _log.warning("Failed to load plugin %s: %s", ep.name, exc)
    except Exception:
        _log.debug("Entry point discovery not available")

    _discovered = True
    if count:
        _log.info("Discovered %d provider plugin(s)", count)
    return count


def get_plugin(name: str) -> type[LLMProvider] | None:
    """Get a plugin provider class by name."""
    return _plugin_registry.get(name)


def list_plugins() -> list[str]:
    """List all registered plugin names."""
    if not _discovered:
        discover_plugins()
    return list(_plugin_registry.keys())


def create_plugin_provider(
    name: str, **kwargs: Any
) -> LLMProvider:
    """Instantiate a plugin provider by name.

    Args:
        name: Plugin identifier.
        **kwargs: Forwarded to the provider constructor.

    Returns:
        An :class:`LLMProvider` instance, or :class:`NoneProvider` if
        the plugin is not found.
    """
    cls = get_plugin(name)
    if cls is None:
        _log.warning("Plugin provider '%s' not found", name)
        return NoneProvider()
    try:
        return cls(**kwargs)
    except Exception as exc:
        _log.warning("Failed to instantiate plugin %s: %s", name, exc)
        return NoneProvider()


# Auto-discover on import
discover_plugins()
