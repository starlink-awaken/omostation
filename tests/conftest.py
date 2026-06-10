"""conftest — 集成测试子进程降级 + 测试工具.

POC_SERVICES 已升级到 mcp_stdio transport (P54-W0)，
内部用 asyncio.run() 启动 MCP bridge，在 pytest-asyncio 中嵌套调用非法。

此 conftest 在测试模式下将所有 mcp_stdio 降级为 stdio（同步 select+Popen），
使子进程测试在 pytest-asyncio 中可用。
同时为已迁出的后端提供 echo mock。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


class FakeToolCatalog:
    """Minimal mock of ToolCatalog for LifecycleManager / Orchestrator tests.

    Provides an in-memory ``tools`` dict with the same interface contract
    that vida._catalog uses::

        get_tool(tool_id)       -> dict | None
        update_status(id, s)   -> None
        record_usage(id)       -> None
        list_tools(status=...) -> list[dict]
        search_tools(...)      -> list[dict]
        add_tool(item)         -> None
        count_by_status()      -> dict[str, int]
        close()                -> None
    """

    def __init__(self, _tools: dict | None = None):
        self.tools: dict[str, dict] = _tools if _tools is not None else {}
        self.usage_records: dict[str, float] = {}

    # ── Read ────────────────────────────────
    def get_tool(self, tool_id: str) -> dict | None:
        return self.tools.get(tool_id)

    def list_tools(self, status: str | None = None) -> list[dict]:
        if status is None:
            return list(self.tools.values())
        return [t for t in self.tools.values() if t.get("status") == status]

    def search_tools(self, query: str = "", limit: int = 20, **filters) -> list[dict]:
        results = []
        for tid, t in self.tools.items():
            if not query or query.lower() in tid.lower() or query.lower() in t.get("name", "").lower():
                if all(t.get(k) == v for k, v in filters.items()):
                    results.append(t)
        return results[:limit]

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self.tools.values():
            s = t.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    # ── Write ───────────────────────────────
    def add_tool(self, item: dict) -> None:
        self.tools[item.get("id") or item.get("name", "unknown")] = item

    def update_status(self, tool_id: str, status: str) -> None:
        if tool_id in self.tools:
            self.tools[tool_id]["status"] = status

    def record_usage(self, tool_id: str) -> None:
        if tool_id in self.tools:
            self.usage_records[tool_id] = __import__("time").time()

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def downgrade_mcp_stdio_to_stdio(monkeypatch: pytest.MonkeyPatch):
    """自动降级 POC_SERVICES 的 mcp_stdio transport 到 stdio.

    不影响测试验证路由层逻辑 — 仅替换通信方式。
    """
    from agora.mcp import bos_resolver as br

    for uri, svc in list(br.POC_SERVICES.items()):
        if hasattr(svc, "transport") and svc.transport == "mcp_stdio":
            monkeypatch.setattr(svc, "transport", "stdio")
