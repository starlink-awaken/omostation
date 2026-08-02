"""F-04: resolver transport 分派对齐测试。

覆盖:
- inline transport 无 command → 结构化错误 (不再 Popen([]))
- inline transport 有 command → 走 stdio
- mcp_proxy transport → 显式降级错误 (需 ProxyManager)
- http transport → 对 http_url 发起请求
- stdio transport → 正常子进程调用
"""

from __future__ import annotations

from agora.mcp.resolver.adapter import StdioAdapter
from agora.mcp.resolver.services_types import BosService


def _svc(transport: str, **overrides) -> BosService:
    defaults = {
        "uri": f"bos://capability/test/{transport}",
        "domain": "capability",
        "package": "test",
        "action": "ping",
        "transport": transport,  # type: ignore[arg-type]
        "command": ["echo", "{}"],
    }
    defaults.update(overrides)
    return BosService(**defaults)


def test_inline_without_command_returns_structured_error():
    """inline 无 command → 结构化错误 (F-04: 消除 Popen([]))。"""
    svc = _svc("inline", command=[])
    result = StdioAdapter().call(svc)
    assert result["status"] == "error"
    assert result["transport"] == "inline"
    assert "no command" in result["error"]


def test_inline_with_command_goes_stdio():
    """inline 有 command → 走 stdio 协议。"""
    svc = _svc("inline", command=["echo", '{"status":"ok"}'])
    result = StdioAdapter().call(svc)
    assert result["status"] == "ok"
    assert "result" in result


def test_mcp_proxy_returns_explicit_degradation():
    """mcp_proxy 无 ProxyManager 上下文 → 显式降级错误。"""
    svc = _svc("mcp_proxy")
    result = StdioAdapter().call(svc)
    assert result["status"] == "error"
    assert result["transport"] == "mcp_proxy"
    assert "ProxyManager" in result["error"]


def test_http_transport_calls_http_url(monkeypatch):
    """http transport → 对 http_url 发起请求。"""
    import json

    calls: dict = {}

    class _FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"status": "ok", "data": 1}).encode()

    def _fake_urlopen(req, timeout=None):
        calls["url"] = req.full_url
        calls["method"] = req.get_method()
        return _FakeResp()

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    svc = _svc("http", http_url="http://127.0.0.1:9999/api/ping")
    result = StdioAdapter().call(svc, {"query": "x"})
    assert result["status"] == "ok"
    assert calls["url"] == "http://127.0.0.1:9999/api/ping"
    assert calls["method"] == "POST"


def test_http_transport_error_returns_structured(monkeypatch):
    """http transport 请求失败 → 结构化错误。"""
    import urllib.request

    def _fail_urlopen(req, timeout=None):
        raise ConnectionError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _fail_urlopen)
    svc = _svc("http", http_url="http://127.0.0.1:9999/nope")
    result = StdioAdapter().call(svc)
    assert result["status"] == "error"
    assert result["transport"] == "http"
    assert "connection refused" in result["error"]


def test_stdio_transport_normal_call():
    """stdio transport → 正常子进程调用。"""
    svc = _svc("stdio", command=["echo", '{"status":"ok"}'])
    result = StdioAdapter().call(svc)
    assert result["status"] == "ok"
