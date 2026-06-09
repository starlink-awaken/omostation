"""Forge 集市 hot-reload — agora 侧 (P33-W5 战役 3).

新工具安装后, 自动注入 agora ProcessPool + POC_SERVICES.
P33-W4 战役 1: 11 静态 POC service.
P33-W5 战役 3: 动态加载额外服务, **不重启 agora**.

关键约束:
  - 修改 POC_SERVICES 全局 dict (mock 测试可达, 真实 mcp_bootstrap 启动时加载)
  - 修改 ProcessPool (P33-W4 战役 1 同款, 复用)
  - 不破 P32 修复 (12/12 健康 + 0 ruff)
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

from agora.mcp.bos_resolver import (
    BOS_URI_PATTERN,
    KAIRON_ROOT,
    POC_SERVICES,
    BosService,
    ProcessPool,
)

_log = logging.getLogger(__name__)

CAPS_ROOT = Path(
    os.environ.get(
        "OMO_CAPABILITIES_ROOT", str(Path.home() / "Workspace/.omo/capabilities")
    )
)
MARKET_REGISTRY = CAPS_ROOT / "market.json"


@dataclass
class LoadedTool:
    """已加载的 forge 工具."""

    name: str
    source: str
    bos_uri: str
    install_path: str
    loaded_at: float
    service: BosService | None = None

    @property
    def age_seconds(self) -> float:
        return time.time() - self.loaded_at


# ── BOS URI → service 工厂 ─────────────────────────
def _build_service(tool: dict) -> BosService | None:
    """从注册条目构造 BosService.

    规则:
      - domain/package/action 从 bos_uri 解析
      - install_path 末段当 module_name
      - stdio: uv run --directory <kairon> python -m <module> serve --action <action>
    """
    bos_uri = tool.get("bos_uri", "")
    m = BOS_URI_PATTERN.match(bos_uri)
    if not m:
        return None

    domain = m.group(1)
    package = m.group(2)
    action = m.group(3)

    install_path = tool.get("install_path", tool.get("path", ""))
    module_name = Path(install_path).name or package

    # stdio command — 与 P33-W4 战役 1 同模式
    command = [
        "uv",
        "run",
        "--directory",
        str(KAIRON_ROOT),
        "python",
        "-m",
        module_name,
        "serve",
        "--action",
        action,
    ]

    return BosService(
        uri=bos_uri,
        domain=domain,
        package=package,
        action=action,
        transport="stdio",
        command=command,
        description=tool.get("description", "")
        or f"forge-loaded tool: {tool.get('name', '')}",
    )


# ── 主引擎 ───────────────────────────────────────
class ForgeLoader:
    """Forge hot-reload 引擎.

    Usage:
        loader = ForgeLoader()
        results = loader.load_from_market()     # 全部加载
        r = loader.load_tool({"name": ..., "bos_uri": ..., "install_path": ...})  # 单条
        loader.unload_tool("xxx")                # 卸载
        loader.list_loaded()                     # 已加载列表
    """

    def __init__(self, pool: ProcessPool | None = None) -> None:
        self.pool = pool or ProcessPool()
        self.loaded: dict[str, LoadedTool] = {}

    # ── 加载 ──────────────────────────────────────
    def load_from_market(self) -> list[dict]:
        """从 .omo/capabilities/market.json 加载所有工具."""
        if not MARKET_REGISTRY.exists():
            return []
        try:
            market = json.loads(MARKET_REGISTRY.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        if not isinstance(market, list):
            return []

        results: list[dict] = []
        for tool in market:
            if not tool.get("enabled", True):
                results.append({"skipped": tool.get("name", "?"), "reason": "disabled"})
                continue
            r = self.load_tool(tool)
            results.append(r)
        return results

    def load_tool(self, tool: dict) -> dict:
        """加载单条工具到 ProcessPool + POC_SERVICES."""
        name = tool.get("name", "")
        bos_uri = tool.get("bos_uri", "")
        install_path = tool.get("install_path", tool.get("path", ""))

        if not name or not bos_uri or not install_path:
            return {
                "error": f"missing_fields: name/bos_uri/install_path required, got {tool}"
            }

        if name in self.loaded:
            return {"skipped": name, "reason": "already_loaded"}

        if bos_uri in POC_SERVICES:
            return {
                "skipped": name,
                "reason": f"bos_uri_already_registered: {bos_uri}",
            }

        service = _build_service(tool)
        if service is None:
            return {"error": f"invalid_bos_uri: {bos_uri}"}

        # 注入全局注册表 (动态扩容)
        POC_SERVICES[bos_uri] = service

        self.loaded[name] = LoadedTool(
            name=name,
            source=tool.get("source", "unknown"),
            bos_uri=bos_uri,
            install_path=install_path,
            loaded_at=time.time(),
            service=service,
        )
        _log.info("forge.loaded name=%s uri=%s", name, bos_uri)
        return {
            "loaded": name,
            "bos_uri": bos_uri,
            "path": install_path,
            "transport": service.transport,
            "command": service.command,
        }

    # ── 卸载 ──────────────────────────────────────
    def unload_tool(self, name: str) -> bool:
        """从 ProcessPool + POC_SERVICES 卸载工具."""
        if name not in self.loaded:
            return False
        tool = self.loaded.pop(name)
        # 关闭 stdio 进程 (如有)
        if tool.service and tool.service.uri in self.pool.processes:
            self.pool.shutdown(tool.service.uri)
        # 从全局注册表移除
        if tool.bos_uri in POC_SERVICES:
            del POC_SERVICES[tool.bos_uri]
        _log.info("forge.unloaded name=%s uri=%s", name, tool.bos_uri)
        return True

    # ── 查询 ──────────────────────────────────────
    def list_loaded(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "source": t.source,
                "bos_uri": t.bos_uri,
                "install_path": t.install_path,
                "age_seconds": round(t.age_seconds, 1),
                "transport": t.service.transport if t.service else None,
            }
            for t in self.loaded.values()
        ]

    def get_loaded(self, name: str) -> dict | None:
        t = self.loaded.get(name)
        if t is None:
            return None
        return {
            "name": t.name,
            "source": t.source,
            "bos_uri": t.bos_uri,
            "install_path": t.install_path,
            "age_seconds": round(t.age_seconds, 1),
        }


# ── 全局单例 ──────────────────────────────────────
loader = ForgeLoader()


# ── 兼容: market 工具函数 (供 MCP tools 复用) ─────
def install_local_tool(  # noqa: F811 — 兼容 forge.market 命名
    name: str,
    source_path: str,
    bos_uri: str = "",
    description: str = "",
) -> dict:
    """包装: agora 进程内 import forge.market.install_local_tool."""
    from forge.market import install_local_tool as _impl

    return _impl(name, source_path, bos_uri, description)


def remove_tool(name: str) -> bool:  # noqa: F811
    """包装: agora 进程内 import forge.market.remove_tool."""
    from forge.market import remove_tool as _impl

    return _impl(name)


def list_market_tools() -> list[dict]:
    """包装: 读取注册表."""
    from forge.market import list_tools as _impl

    return _impl()


__all__ = (
    "CAPS_ROOT",
    "ForgeLoader",
    "LoadedTool",
    "MARKET_REGISTRY",
    "install_local_tool",
    "list_market_tools",
    "loader",
    "remove_tool",
)
