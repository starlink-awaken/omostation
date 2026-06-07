"""conftest — 集成测试子进程降级.

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


@pytest.fixture(autouse=True)
def downgrade_mcp_stdio_to_stdio(monkeypatch: pytest.MonkeyPatch):
    """自动降级 POC_SERVICES 的 mcp_stdio transport 到 stdio.

    不影响测试验证路由层逻辑 — 仅替换通信方式。
    """
    from agora.mcp import bos_resolver as br

    for uri, svc in list(br.POC_SERVICES.items()):
        if hasattr(svc, "transport") and svc.transport == "mcp_stdio":
            monkeypatch.setattr(svc, "transport", "stdio")
