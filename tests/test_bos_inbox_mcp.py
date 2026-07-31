"""BOS Inbox Neural Mesh MCP API 测试。"""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest
import yaml

from agora.server.tools_bos import (
    bos_inbox_archive,
    bos_inbox_draft,
    bos_inbox_pending,
    bos_inbox_search,
    bos_inbox_status,
    bos_inbox_triage,
    bos_inbox_watch,
    persona_bdsk_evaluate,
)
from agora.mcp.bos_router import clean_inbox_content


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
    assert "bos://memory/inbox/watch" in uris
    assert "bos://memory/inbox/archive" in uris
    assert "bos://memory/inbox/triage" in uris
    assert "bos://memory/inbox/draft" in uris
    assert "bos://persona/bdsk/evaluate" in uris

    for s in services:
        if s.get("uri") in (
            "bos://memory/inbox/status",
            "bos://memory/inbox/search",
            "bos://memory/inbox/pending",
            "bos://memory/inbox/watch",
            "bos://memory/inbox/archive",
            "bos://memory/inbox/triage",
            "bos://memory/inbox/draft",
            "bos://persona/bdsk/evaluate",
        ):
            assert s.get("security_level") == "internal"


def test_bos_inbox_sanitizer():
    """验证 CR-DOMAIN-AUTH-01 数据清洗拦截逻辑有效性 (v2.0 XSS & Injection 防护)。"""
    dirty = "<script>alert('hack')</script>正常公文<iframe src='bad.html'></iframe><img onerror='alert(1)'>[链接](data:text/html;base64,PHNjcmlwdD4=)"
    cleaned = clean_inbox_content(dirty)
    assert "[SCRIPT_REMOVED_FOR_SECURITY]" in cleaned
    assert "[IFRAME_REMOVED_FOR_SECURITY]" in cleaned
    assert "onerror=" not in cleaned.lower()
    assert "[DATA_URI_REMOVED]" in cleaned
    assert "正常公文" in cleaned
    assert "alert('hack')" not in cleaned


def test_bos_inbox_router_resolution():
    """验证 BOSRouter 能正确解析和发现 inbox 的 7 个核心服务(含 triage/draft)。"""
    from agora.mcp.bos_resolver import list_services
    from agora.mcp.bos_router import bos_router

    bos_router.seed_from_poc(list_services())

    inbox_uris = [
        "bos://memory/inbox/status",
        "bos://memory/inbox/search",
        "bos://memory/inbox/pending",
        "bos://memory/inbox/watch",
        "bos://memory/inbox/archive",
        "bos://memory/inbox/triage",
        "bos://memory/inbox/draft",
    ]
    for uri in inbox_uris:
        route = bos_router.resolve(uri)
        assert route is not None, f"未能在 bos_router 中路由: {uri}"
        assert route["config"]["domain"] == "memory"
        assert route["config"]["action"] in (
            "status",
            "search",
            "pending",
            "watch",
            "archive",
            "triage",
            "draft",
            "inbox-status",
            "inbox-search",
            "inbox-pending",
            "inbox-watch",
            "inbox-archive",
            "inbox-triage",
            "inbox-draft",
        )


def test_bos_persona_router_resolution():
    """验证 BOSRouter 能正确解析和发现 B.D.S.K. persona 服务。"""
    from agora.mcp.bos_resolver import list_services
    from agora.mcp.bos_router import bos_router

    bos_router.seed_from_poc(list_services())
    route = bos_router.resolve("bos://persona/bdsk/evaluate")
    assert route is not None
    assert route["config"]["domain"] == "persona"


@pytest.mark.asyncio
async def test_bos_inbox_mcp_endpoints(monkeypatch):
    """测试 inbox status / search / pending / watch / triage / draft 等异步 MCP Tool 接口。"""
    res_status = await bos_inbox_status()
    assert res_status.get("result") or res_status.get("error") or res_status.get("status")

    res_search = await bos_inbox_search("规划", top_k=2)
    assert isinstance(res_search, dict)

    res_pending = await bos_inbox_pending(source="seeyon_oa")
    assert isinstance(res_pending, dict)

    res_watch = await bos_inbox_watch(priority_only=True)
    assert isinstance(res_watch, dict)

    res_archive = await bos_inbox_archive("non_existent_file.md", reason="test")
    assert isinstance(res_archive, dict)

    res_triage = await bos_inbox_triage(limit=5)
    assert isinstance(res_triage, dict)
    assert res_triage.get("status") == "ok"

    res_draft = await bos_inbox_draft("test_inbox_item.md")
    assert isinstance(res_draft, dict)
    assert res_draft.get("status") == "ok"


@pytest.mark.asyncio
async def test_bos_persona_bdsk_endpoint():
    """测试 B.D.S.K. 虚拟董事会评估网关能力。"""
    res_deep = await persona_bdsk_evaluate("系统升级到 V3", mode="deep")
    assert res_deep.get("status") == "ok"
    assert res_deep.get("verdict") == "PROCEED_WITH_GUARDRAILS"
    assert "builder" in res_deep.get("board_reviews", {})

    res_fast = await persona_bdsk_evaluate("紧急修复文档格式", mode="fast")
    assert res_fast.get("status") == "ok"
    assert res_fast.get("verdict") == "PROCEED_FAST"
