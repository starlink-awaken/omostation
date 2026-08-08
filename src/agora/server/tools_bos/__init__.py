"""BOS URI 工具包 (tools_bos 拆分后聚合层)。

拆分前: server/tools_bos.py (1626 行 god module)
拆分后:
  - _helpers.py      共享状态 + 基础工具
  - inbox.py         BOS Inbox 神经网工具
  - bdsk.py          B.D.S.K. 虚拟董事会工具
  - routing.py       BOS 路由辅助
  - registration.py  register_bos_tools 工具注册

本模块 re-export 全部符号, 保持 `from agora.server.tools_bos import X` 兼容。
"""

from __future__ import annotations

from ._helpers import (
    _AGORA_API_KEY,
    _PROJECTS_DIR,
    _bos_domain_authorized,
    _bos_uri_to_event_type,
    _get_inbox_paths,
    _get_proxy_manager,
    _publish_bos_event,
    logger,
)
from .bdsk import _persist_bdsk_adr, persona_bdsk_evaluate
from .inbox import (
    bos_inbox_archive,
    bos_inbox_draft,
    bos_inbox_pending,
    bos_inbox_search,
    bos_inbox_status,
    bos_inbox_triage,
    bos_inbox_watch,
)
from .registration import register_bos_tools
from .routing import _resolve_with_router

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
