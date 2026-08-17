"""
Plugin base class for the kairon plugin system.

Provides the BosPlugin base class that all plugins must extend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from kairon_plugin_sdk.context import PluginContext


class BosPlugin(ABC):
    """
    Base class for all plugins.

    Plugins must extend this class and implement the required methods.

    Attributes:
        plugin_id: Unique identifier for the plugin (kebab-case)
        plugin_version: Semantic version string
        plugin_name: Human-readable name
        plugin_description: Short description of plugin functionality
        plugin_author: Plugin author name or contact
        plugin_tags: List of tags for categorization
        plugin_capabilities: List of capabilities provided by plugin
    """

    plugin_id: str = ""
    plugin_version: str = "1.0.0"
    plugin_name: str = ""
    plugin_description: str = ""
    plugin_author: str = ""
    plugin_tags: list[str] = []
    plugin_capabilities: list[str] = []

    def __init__(self, context: PluginContext | None = None) -> None:
        """
        Initialize the plugin.

        Args:
            context: Plugin execution context (injected by the runtime)
        """
        self.context = context or PluginContext()
        self._state: str = "initialized"

    @abstractmethod
    def execute(self, **kwargs: Any) -> dict[str, Any]:
        """
        Execute the plugin's primary functionality.

        This method must be implemented by all plugins.

        Args:
            **kwargs: Plugin-specific parameters

        Returns:
            Dictionary containing execution results
        """
        pass

    def configure(self, config: dict[str, Any]) -> None:
        """
        Configure the plugin with runtime settings.

        Args:
            config: Configuration dictionary
        """
        self.config = config

    def validate(self, **kwargs: Any) -> bool:
        """
        Validate plugin inputs before execution.

        Args:
            **kwargs: Inputs to validate

        Returns:
            True if inputs are valid, False otherwise
        """
        return True

    def health_check(self) -> dict[str, Any]:
        """
        Return plugin health status.

        Returns:
            Health status dictionary
        """
        return {
            "status": "healthy",
            "plugin_id": self.plugin_id,
            "version": self.plugin_version,
        }

    def get_metadata(self) -> dict[str, Any]:
        """
        Return plugin metadata.

        Returns:
            Plugin metadata dictionary
        """
        return {
            "id": self.plugin_id,
            "version": self.plugin_version,
            "name": self.plugin_name or self.plugin_id,
            "description": self.plugin_description,
            "author": self.plugin_author,
            "tags": self.plugin_tags,
            "capabilities": self.plugin_capabilities,
        }

    def __repr__(self) -> str:
        return f"<BosPlugin id={self.plugin_id!r} version={self.plugin_version!r}>"
