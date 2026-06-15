"""BOS URI 解析器 — agora 侧 (已拆分为 resolver/ 包).

此文件为向后兼容转发层。新代码请直接 import resolver 子模块。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from agora.mcp.resolver.adapter import StdioAdapter, get_stdio_adapter
from agora.mcp.resolver.api import (
    normalize_bos_uri,
    parse_bos_uri,
    list_services,
    get_service,
    list_domains,
    invoke_stdio,
    protocol_self_check,
    resolve_bos_uri,  # noqa: F401 — re-exported in __all__
)
from agora.mcp.resolver.pool import ProcessPool, get_pool as _get_pool  # noqa: F401
from agora.mcp.resolver.services import BosService, POC_SERVICES, _with_uv_package, BOS_URI_PATTERN  # noqa: F401

_pool = _get_pool()

# Re-export get_pool for backward compat
get_pool = _get_pool

_log = logging.getLogger(__name__)

# ── 兼容导出 ──────────────────────────────────────────
__all__ = [
    "BosService",
    "POC_SERVICES",
    "ProcessPool",
    "StdioAdapter",
    "normalize_bos_uri",
    "parse_bos_uri",
    "list_services",
    "get_service",
    "list_domains",
    "invoke_stdio",
    "protocol_self_check",
    "get_pool",
    "get_stdio_adapter",
    "_with_uv_package",
    "resolve_bos_uri",
    "BOS_URI_PATTERN",
    "_pool",
]

# ── 路径常量 (保持向后兼容) ────────────────────────────
_WS = os.environ.get("WORKSPACE_ROOT") or str(Path.home() / "Workspace")
KAIRON_ROOT = Path(_WS) / "projects" / "kairon"
METAOS_ROOT = Path(_WS) / "projects" / "metaos"
OMOSTATION_ROOT = Path(_WS)
