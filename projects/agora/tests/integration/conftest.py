"""conftest — 集成测试自动 mock 缺后端的 stdio 服务.

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

    不影响 POC_SERVICES 注册表结构，只替换 command 为静态 echo。
    """
    from agora.mcp import bos_resolver as br

    import sys as _sys

    # 只替换缺后端的 URI
    for uri, mock_response in _MOCK_SERVICES.items():
        if uri not in br.POC_SERVICES:
            continue
        svc = br.POC_SERVICES[uri]
        # 替换命令为 python3 -c 打印 mock JSON 响应
        mock_cmd = [
            "python3", "-c",
            f"import sys,json; sys.stdout.write(json.dumps({json.dumps(mock_response)}) + '\\n'); sys.stdout.flush()",
        ]
        # monkeypatch 替换 service 的 command
        monkeypatch.setattr(svc, "command", mock_cmd)
