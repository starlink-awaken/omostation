"""BOS URI 工具 — BOS 路由/查询/监控/事件订阅。

依赖: _response.py 提供 _ok/_error/FORMAT_VERSION/_get_cache_ttl。
mcp.py 提供 FastMCP 实例、EventBus、ProxyManager 实例。

注意: 本模块已拆分为 server/tools_bos/ 子包 (god module 拆分)。
此文件保留为兼容 shim, 所有符号 re-export 自子包。
新代码请从 `agora.server.tools_bos` (包) 直接 import。
"""

from __future__ import annotations

from agora.server.tools_bos._helpers import (
    _AGORA_API_KEY,
    _PROJECTS_DIR,
    _bos_domain_authorized,
    _bos_uri_to_event_type,
    _get_inbox_paths,
    _get_proxy_manager,
    _publish_bos_event,
    logger,
)
from agora.server.tools_bos.bdsk import _persist_bdsk_adr, persona_bdsk_evaluate
from agora.server.tools_bos.inbox import (
    bos_inbox_archive,
    bos_inbox_draft,
    bos_inbox_pending,
    bos_inbox_search,
    bos_inbox_status,
    bos_inbox_triage,
    bos_inbox_watch,
)
from agora.server.tools_bos.registration import register_bos_tools
from agora.server.tools_bos.routing import _resolve_with_router

__all__ = [
    "_AGORA_API_KEY",
    "_PROJECTS_DIR",
    "_bos_domain_authorized",
    "_bos_uri_to_event_type",
    "_get_inbox_paths",
    "_get_proxy_manager",
    "_persist_bdsk_adr",
    "_publish_bos_event",
    "_resolve_with_router",
    "bos_inbox_archive",
    "bos_inbox_draft",
    "bos_inbox_pending",
    "bos_inbox_search",
    "bos_inbox_status",
    "bos_inbox_triage",
    "bos_inbox_watch",
    "logger",
    "persona_bdsk_evaluate",
    "register_bos_tools",
]
