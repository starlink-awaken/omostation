"""BOS 服务类型 + URI 模式 (从 services.py 提取, ISC-34 God Module 拆分第一步).

治本 ISC-34: services.py 1339L God Module, 第一步提取 types/常量 (~45 行) 到本模块.
services.py re-export 保下游兼容 (from agora.mcp.resolver.services import BosService 仍工作).
完整 ≤800 需后续按域拆服务定义 (~500 行, sprint 级, omo-srp-refactor skill 模式).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Transport = Literal["stdio", "internal", "http", "mcp_stdio", "mcp_proxy", "inline"]

# ── BOS URI 模式 ─────────────────────────────────────
BOS_URI_DOMAINS = (
    "memory",
    "governance",
    "omo",
    "analysis",
    "persona",
    "compute",
    "capability",
    "forge",
    "meta",
    "ecos",
    "agora",
    "cockpit",
    "l4-kernel",
    "runtime",
    "swarm",
    "system",
    "toolbox",
    "perception",
)
BOS_URI_DOMAIN_PATTERN = "|".join(BOS_URI_DOMAINS)

BOS_URI_PATTERN = re.compile(
    rf"^bos://(?P<domain>{BOS_URI_DOMAIN_PATTERN})"
    # package is required; action is optional and may itself contain
    # slashes (sub-actions like `tools/cards_status` or `minerva` under
    # `kairon/minerva`). 3+ segments is the contract. Both package and
    # action accept underscores so names like `circuit_breaker`,
    # `omo_worker_dispatch`, `audit_evaluator` are first-class.
    r"/(?P<package>[a-z_][a-z0-9_-]+)"
    r"(?:/(?P<action>[a-z_][a-z0-9_/-]+))?$"
)


@dataclass
class BosService:
    """BOS 服务描述 — 怎么调用一个 URI."""

    uri: str
    domain: str
    package: str
    action: str
    transport: Transport = "stdio"
    command: list[str] = field(default_factory=list)
    module_path: str = ""
    func_name: str = ""
    http_url: str = ""
    description: str = ""
    mcp_tool: str = ""
    tools: list[str] = field(default_factory=list)
