"""Connector package — all platform connectors auto-register here.

Connectors are discovered via Python entry_points (group=iris.connectors),
with hardcoded imports as fallback.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from iris.base import BaseConnector
    from iris.registry import ConnectorRegistry

logger = logging.getLogger(__name__)

# Cache entry_points discovery result (package metadata doesn't change at runtime)
_entry_points_cache: list | None = None


def _discover_entry_points(registry: ConnectorRegistry) -> int:
    """Discover and register connectors via entry_points.

    Results are cached after first call.
    Returns the number of connectors registered via entry points.
    """
    global _entry_points_cache

    if _entry_points_cache is None:
        try:
            from importlib.metadata import entry_points

            _entry_points_cache = list(entry_points(group="iris.connectors"))
        except Exception as e:
            logger.info("Entry point discovery unavailable: %s", e)
            _entry_points_cache = []

    count = 0
    for ep in _entry_points_cache:
        try:
            cls = ep.load()
            registry.register(cls())
            count += 1
        except Exception as e:
            logger.warning("Failed to load connector '%s': %s", ep.name, e)
    return count


def _register_fallback(registry: ConnectorRegistry) -> None:
    """Hardcoded fallback registration when entry_points are unavailable."""
    from iris.connectors.applenotes import AppleNotesConnector
    from iris.connectors.dingtalk.connector import DingTalkConnector
    from iris.connectors.feishu.connector import FeishuConnector
    from iris.connectors.github.connector import GitHubConnector
    from iris.connectors.local_files import LocalFilesConnector
    from iris.connectors.notebooklm import NotebookLMConnector
    from iris.connectors.obsidian import ObsidianConnector
    from iris.connectors.openhuman import OpenHumanConnector
    from iris.connectors.pocket import PocketConnector
    from iris.connectors.polar import PolarConnector
    from iris.connectors.rss.connector import RssConnector
    from iris.connectors.telegram import TelegramConnector
    from iris.connectors.wechat.connector import WeChatConnector
    from iris.connectors.wpsnote import WPSNoteConnector
    from iris.connectors.wxread import WXReadConnector
    from iris.connectors.zhihu import ZhihuConnector

    registry.register(LocalFilesConnector())
    registry.register(ObsidianConnector())
    registry.register(OpenHumanConnector())
    registry.register(WPSNoteConnector())
    registry.register(NotebookLMConnector())
    registry.register(ZhihuConnector())
    registry.register(WXReadConnector())
    registry.register(TelegramConnector())
    registry.register(WeChatConnector())
    registry.register(PocketConnector())
    registry.register(PolarConnector())
    registry.register(AppleNotesConnector())
    registry.register(GitHubConnector())
    registry.register(RssConnector())
    registry.register(cast("BaseConnector", DingTalkConnector()))
    registry.register(cast("BaseConnector", FeishuConnector()))


def register_all(registry: ConnectorRegistry) -> None:
    """Register all available connectors into the given registry.

    Each connector handles its own availability check.
    Uses entry_points discovery when available, falls back to hardcoded imports.
    """
    count = _discover_entry_points(registry)
    if count == 0:
        _register_fallback(registry)
