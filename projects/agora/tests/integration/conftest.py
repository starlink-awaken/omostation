"""conftest — 集成测试 mock 缺后端的 stdio 服务.

替换 POC_SERVICES 中缺后端的子进程命令为简单 echo，
使得跨域路由链测试不依赖真后端也能验证路由层逻辑。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

# ── 所有链测试用到的 stdio 服务 mock 响应 ─────────────
# 每个服务启动后读一行 JSON 请求，返回对应 mock 结果
_MOCK_RESPONSES: dict[str, dict] = {
    # 场景 1: memory → analysis
    "bos://memory/kos/search": {
        "status": "ok",
        "result": {"results": [{"id": "doc-001", "title": "mock-kos-result", "score": 0.95}]},
    },
    "bos://analysis/minerva/research": {
        "status": "ok",
        "result": {"report": "# Mock Research Report\n\nGenerated for testing.", "depth": "L2", "sources": ["mock-source-1"]},
    },
    "bos://analysis/minerva/draft": {
        "status": "ok",
        "result": {"draft": "# Mock Draft\n\nAuto-generated draft for testing.", "status": "draft"},
    },
    # 场景 2: analysis → persona
    "bos://persona/health-profile/summary": {
        "status": "ok",
        "result": {"member_id": "mock-user", "summary": "健康概况 mock 数据", "score": 85},
    },
    "bos://persona/health-profile/alert": {
        "status": "ok",
        "result": {"member_id": "mock-user", "level": "info", "message": "Mock alert - no action needed"},
    },
    # 场景 3: governance → analysis
    "bos://analysis/minerva/audit": {
        "status": "ok",
        "result": {"audit_id": "audit-mock-001", "status": "clean", "issues": []},
    },
    # 场景 4: persona → capability
    "bos://persona/sot-bridge-persona/recall-entity": {
        "status": "ok",
        "result": {"entity": "mock-user", "confidence": 0.85},
    },
    "bos://persona/sot-bridge-persona/recall": {
        "status": "ok",
        "result": {"entity": "mock-user-002", "confidence": 0.75},
    },
    "bos://capability/forge/list-tools": {
        "status": "ok",
        "result": {"tools": [{"name": "mock-tool", "description": "A mock tool for testing"}]},
    },
    "bos://capability/forge/exec-tool": {
        "status": "ok",
        "result": {"tool": "mock-tool", "output": "Mock execution completed", "exit_code": 0},
    },
    # 场景 5: capability → governance — 只 forge/list-tools 需要 mock，omo/inspect 是 internal
}


def _make_mock_script(uri: str, mock_response: dict) -> list[str]:
    """生成一个 echo 子进程命令，读取 stdin 请求后返回 mock 响应。

    子进程收到的请求格式:
      {"request_id": "req-N-xxx", "action": "<action>", "args": [...]}
    返回格式:
      {"status": "ok", "result": {...}, "request_id": "...", "service": "...", "action": "..."}
    """
    python_code = f"""\
import sys,json
line = sys.stdin.readline()
try:
    req = json.loads(line)
except Exception:
    req = {{}}
resp = {json.dumps(mock_response)}
resp["request_id"] = req.get("request_id", "mock-req-000")
resp["service"] = req.get("action", "mock")
resp["action"] = req.get("action", "mock")
sys.stdout.write(json.dumps(resp) + "\\n")
sys.stdout.flush()
"""
    return ["python3", "-c", python_code]


@pytest.fixture(autouse=True)
def patch_missing_backends(monkeypatch: pytest.MonkeyPatch):
    """在测试前替换所有链测试用到的 POC_SERVICE 命令为 echo mock.

    注意: mcp_stdio transport 内部使用 asyncio.run()，
    在 pytest-asyncio 事件循环中无法嵌套调用。
    因此同时将 transport 降级为 stdio (同步 select+subprocess)。
    """
    from agora.mcp import bos_resolver as br

    for uri, mock_response in _MOCK_RESPONSES.items():
        if uri not in br.POC_SERVICES:
            continue
        svc = br.POC_SERVICES[uri]
        mock_cmd = _make_mock_script(uri, mock_response)
        monkeypatch.setattr(svc, "command", mock_cmd)
        # 降级 transport 到 stdio (避 mcp_stdio 的 asyncio.run())
        monkeypatch.setattr(svc, "transport", "stdio")
