"""BOS 自动服务发现 (P47) — 从 AGENTS.md 提取 bos:// 注册
===========================================================
扫描下游项目目录，解析 AGENTS.md 中声明的 BOS URI，自动注册到 BOSRouter。

AGENTS.md 声明格式 (在文件末尾添加):
    ## BOS Services
    - `bos://memory/kos/search` — KOS 跨域搜索 (stdio) `uv run -m kos serve --search`
    - `bos://memory/kos/query`  — KOS 查询 (stdio) `uv run -m kos serve --query`

用法:
    from agora.mcp.bos_discovery import discover_from_workspace
    count = discover_from_workspace()
    # → 扫描所有项目 AGENTS.md，自动注册到 bos_router
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

_log = logging.getLogger(__name__)

# AGENTS.md 中 BOS 声明行的正则: `bos://domain/package/action` — description (adapter) `command`
# 支持多种变体，使描述、适配器、命令都可选
_BOS_DECL_PATTERN = re.compile(
    r"`bos://(?P<domain>[a-z0-9-]+)/(?P<package>[a-z0-9-]+)/(?P<action>[a-z0-9-]+)`"
    r"(?:\s*[-—]\s*(?P<desc>[^(`\n]+))?"
    r"(?:\s*\((?P<adapter>[a-z_-]+)\))?"
    r"(?:\s*`(?P<command>[^`\n]+)`)?",
    re.IGNORECASE,
)

# 默认扫描的项目目录（相对于 HOME/Workspace/projects/）
_DEFAULT_PROJECTS = [
    "agora",
    "kairon",
    "metaos",
    "runtime",
    "ecos",
    "cockpit",
    "gbrain",
    "omo",
]


def discover_from_workspace(workspace_root: str = "") -> int:
    """扫描 Workspace 中所有项目，提取 BOS URI 注册。

    Args:
        workspace_root: Workspace 根目录 (默认 ~/Workspace/projects/)

    Returns:
        注册的 BOS URI 数量
    """
    ws = (
        Path(workspace_root)
        if workspace_root
        else Path.home() / "Workspace" / "projects"
    )
    if not ws.exists():
        _log.warning("Workspace 目录不存在: %s", ws)
        return 0

    from agora.mcp.bos_router import bos_router

    registered = 0
    for proj in _DEFAULT_PROJECTS:
        agents_md = ws / proj / "AGENTS.md"
        if not agents_md.exists():
            continue
        try:
            content = agents_md.read_text()
            # 在 BOS Services 段落或全文中查找
            section = content
            section_start = content.find("## BOS Services")
            if section_start >= 0:
                section_end = content.find("\n##", section_start + 1)
                if section_end >= 0:
                    section = content[section_start:section_end]

            for match in _BOS_DECL_PATTERN.finditer(section):
                uri = f"bos://{match['domain']}/{match['package']}/{match['action']}"

                # 规范化适配器名称
                raw_adapter = (match.group("adapter") or "poc").lower()
                adapter = "proxy" if "proxy" in raw_adapter else raw_adapter

                route_registered = bos_router.register(
                    uri,
                    adapter=adapter,
                    config={
                        "domain": match["domain"],
                        "description": (match.group("desc") or "").strip(),
                        "command": (match.group("command") or "").strip(),
                        "project": proj,
                        "source": "AGENTS.md",
                    },
                )
                registered += int(route_registered)
        except Exception as e:  # noqa: BLE001 - one bad project is isolated
            _log.warning("Failed to parse %s: %s", agents_md, e)

    _log.info("bos_discovery: registered %d URIs from AGENTS.md", registered)
    return registered
