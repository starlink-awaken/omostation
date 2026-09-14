"""kairon-plugin-sdk — Plugin development toolkit for kairon.

Provides the BosPlugin base class, PluginContext runtime context,
and CLI tools for plugin lifecycle management.
"""

from kairon_plugin_sdk.context import PluginContext
from kairon_plugin_sdk.plugin import BosPlugin

__all__ = [
    "BosPlugin",
    "PluginContext",
]
