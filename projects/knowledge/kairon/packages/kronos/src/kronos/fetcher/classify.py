"""URL classification — content type detection and routing rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any


class ContentType(StrEnum):
    ARTICLE = "article"
    PAPER = "paper"
    SOCIAL = "social"
    POLICY = "policy"
    RESOURCE = "resource"
    VIDEO = "video"
    GITHUB = "github"
    CODE = "code"
    FORUM = "forum"
    WEIXIN = "weixin"
    UNKNOWN = "unknown"


class FetchLayer(int, Enum):
    """抓取层级: 数字越小优先级越高"""

    L0_NATIVE = 0  # 原生 HTTP 直连(最快,不依赖任何外部工具)
    L0_5_SCRAPLING = 1  # Scrapling 智能抓取(TLS 指纹伪装 + Selector 解析)
    L1_MCP_DIRECT = 2  # MCP 工具直连
    L2_JINA_PROXY = 2  # Jina AI Reader 代理
    L3_CACHE = 3  # 缓存/转载查找
    L4_BROWSER = 4  # CloakBrowser 浏览器自动化
    L5_ARCHIVE = 5  # 归档快照兜底


@dataclass
class FetchPlan:
    """对单个 URL 的完整抓取方案"""

    url: str
    content_type: ContentType
    layer: FetchLayer
    method_name: str
    method_desc: str
    call_params: dict[str, Any] = field(default_factory=dict)
    fallback_plan: FetchPlan | None = None
    requires_user_agent: bool = False
    estimated_cost: str = "free"


# ═══════════════════════════════════════════════════
# L1: MCP 直接抓取
# ═══════════════════════════════════════════════════


@dataclass
class MCPTool:
    name: str
    description: str
    domains: list[str]
