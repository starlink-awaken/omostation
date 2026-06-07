"""conftest — 集成测试 mock 缺后端的 stdio 服务.

替换 POC_SERVICES 中缺后端的子进程命令为简单 echo，
使得跨域路由链测试不依赖真后端也能验证路由层逻辑。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# 缺后端 POC URI 列表 — 用 echo mock 替代
_MOCK_SERVICES = {
    # SharedBrain-Bridge 已迁出 kairon, 无子进程
    "bos://persona/sharedbrain-bridge/recall-entity": {
        "status": "ok",
        "result": {"entity": "mock-user", "confidence": 0.85},
        "request_id": "mock-sbb-000",
    },
}


@pytest.fixture(autouse=True)
def patch_missing_backends(monkeypatch: pytest.MonkeyPatch):
    """在测试前替换缺后端的 POC_SERVICE 命令为 echo mock.

    注意: mcp_stdio transport 内部使用 asyncio.run()，
    在 pytest-asyncio 事件循环中无法嵌套调用。
    因此同时将 transport 降级为 stdio (同步 select+subprocess)。
    """
    from agora.mcp import bos_resolver as br

    for uri, mock_response in _MOCK_SERVICES.items():
        if uri not in br.POC_SERVICES:
            continue
        svc = br.POC_SERVICES[uri]
        mock_cmd = [
            "python3", "-c",
            f"import sys,json; sys.stdout.write(json.dumps({json.dumps(mock_response)}) + '\\n'); sys.stdout.flush()",
        ]
        monkeypatch.setattr(svc, "command", mock_cmd)
        # 同时降级 transport 到 stdio (避 mcp_stdio 的 asyncio.run())
        monkeypatch.setattr(svc, "transport", "stdio")
