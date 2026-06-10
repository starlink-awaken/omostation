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
_BOS_DECL_PATTERN = re.compile(
    r"`bos://(?P<domain>[a-z0-9-]+)/(?P<package>[a-z0-9-]+)/(?P<action>[a-z0-9-]+)`"
    r"\s*[-—]\s*(?P<desc>.+?)\s*\((?P<adapter>[a-z]+)\)\s*`(?P<command>.+?)`",
    re.IGNORECASE,
)

# 简化版：只匹配 `bos://domain/package/action`
_SIMPLE_PATTERN = re.compile(
    r"`bos://(?P<domain>[a-z0-9-]+)/(?P<package>[a-z0-9-]+)/(?P<action>[a-z0-9-]+)`"
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
                bos_router.register(
                    uri,
                    adapter=match["adapter"],
                    config={
                        "domain": match["domain"],
                        "description": match["desc"].strip(),
                        "command": match["command"].strip(),
                        "project": proj,
                        "source": "AGENTS.md",
                    },
                )
                registered += 1

            # 简化版：只有 URI，没有命令（标记为 poc adapter）
            for match in _SIMPLE_PATTERN.finditer(section):
                uri = f"bos://{match['domain']}/{match['package']}/{match['action']}"
                # 检查是否已被上面注册
                already = False
                for prefix in bos_router.list_all():
                    if uri.startswith(prefix["prefix"].rstrip("/")):
                        already = True
                        break
                if not already:
                    bos_router.register(
                        uri,
                        adapter="poc",
                        config={
                            "domain": match["domain"],
                            "project": proj,
                            "source": "AGENTS.md",
                        },
                    )
                    registered += 1
        except Exception as e:
            _log.warning("Failed to parse %s: %s", agents_md, e)

    _log.info("bos_discovery: registered %d URIs from AGENTS.md", registered)
    return registered
