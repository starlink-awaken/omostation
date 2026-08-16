"""
Plugin execution context.

Provides the PluginContext dataclass that is injected into plugins
at runtime, providing access to services and utilities.
"""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginContext:
    """
    Execution context for plugins.

    Provides plugins with access to services, configuration,
    and execution metadata.

    Attributes:
        plugin_id: ID of the currently executing plugin
        workspace: Path to the current workspace
        config: Plugin configuration dictionary
        metadata: Execution metadata (tenant, user, etc.)
        services: Available services
    """

    plugin_id: str = ""
    workspace: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    services: dict[str, Any] = field(default_factory=dict)

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata value.

        Args:
            key: Metadata key
            default: Default value if key not found

        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)

    def get_service(self, name: str) -> Any:
        """
        Get a service by name.

        Args:
            name: Service name

        Returns:
            Service instance or None if not found
        """
        return self.services.get(name)

    @property
    def environment(self) -> dict[str, Any]:
        """Get system environment information."""
        return {
            "timestamp": time.time(),
            "os": platform.system().lower(),
            "python_version": platform.python_version(),
            "arch": platform.machine(),
        }

    @property
    def workspace_path(self) -> str:
        """Alias for workspace path."""
        return self.workspace
