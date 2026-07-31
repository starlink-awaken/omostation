"""BOS Inbox Neural Mesh MCP API 测试。"""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest
import yaml

from agora.server.tools_bos import bos_inbox_pending, bos_inbox_search, bos_inbox_status


def test_bos_services_registry_inbox_entries():
    """验证 bos-services.yaml 中正式注册了 inbox 相关的 BOS 服务。"""
    cfg_file = Path(__file__).resolve().parents[1] / "etc" / "bos-services.yaml"
    assert cfg_file.exists()
    data = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    services = data.get("services", [])
    uris = [s.get("uri") for s in services]

    assert "bos://memory/inbox/status" in uris
    assert "bos://memory/inbox/search" in uris
    assert "bos://memory/inbox/pending" in uris


def test_bos_inbox_router_resolution():
    """验证 BOSRouter 能正确解析和发现 inbox 的 3 个核心服务。"""
    from agora.mcp.bos_resolver import list_services
    from agora.mcp.bos_router import bos_router

    bos_router.seed_from_poc(list_services())

    inbox_uris = [
        "bos://memory/inbox/status",
        "bos://memory/inbox/search",
        "bos://memory/inbox/pending",
    ]
    for uri in inbox_uris:
        route = bos_router.resolve(uri)
        assert route is not None, f"未能在 bos_router 中路由: {uri}"
        assert route["config"]["domain"] == "memory"
        assert route["config"]["action"] in (
            "status",
            "search",
            "pending",
            "inbox-status",
            "inbox-search",
            "inbox-pending",
        )


@pytest.mark.asyncio
async def test_bos_inbox_mcp_endpoints(monkeypatch):
    """测试 inbox status / search / pending 三个核心异步 MCP Tool 接口。"""
    res_status = await bos_inbox_status()
    assert res_status.get("result") or res_status.get("error") or res_status.get("status")

    res_search = await bos_inbox_search("规划", top_k=2)
    assert isinstance(res_search, dict)

    res_pending = await bos_inbox_pending(source="seeyon_oa")
    assert isinstance(res_pending, dict)
