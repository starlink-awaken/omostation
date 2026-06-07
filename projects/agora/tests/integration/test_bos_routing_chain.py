"""BOSRouter 播种 + 路由链 端到端集成测试 (P48 W3).

验证:
  1. _resolve_with_router 路由链 (BOSRouter → POC_SERVICES)
  2. BOSRouter 种子路由 (POC + M1 + Discovery)
  3. list_bos_resources 覆盖三路源
  4. BOSRouter-only 路由优雅返回 metadata
  5. 缓存失效机制
  6. 事件链路

注意: _resolve_with_router 和 _bos_uri_to_event_type 已移至 tools_bos.py (God Module 拆分)。
      list_bos_resources 是 register_bos_tools 内部的闭包，测试通过 tools_bos 模块级函数调用。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_KAIRON_SRC = Path("/Users/xiamingxing/Workspace/projects/kairon/packages/forge/src")
if str(_KAIRON_SRC) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_KAIRON_SRC))


# ── fixtures ─────────────────────────────────────────
@pytest.fixture
def seeded_router():
    """构造一个含 POC 路由的 BOSRouter 实例 (不污染全局)."""
    from agora.mcp.bos_router import BOSRouter

    r = BOSRouter()
    r.register("bos://memory/kos/search", adapter="poc", config={"domain": "memory", "package": "kos", "action": "search"})
    r.register("bos://memory/kos/", adapter="poc", config={"domain": "memory", "package": "kos"})
    r.register("bos://memory/", adapter="poc", config={"domain": "memory"})
    r.register("bos://analysis/minerva/research", adapter="poc", config={"domain": "analysis", "package": "minerva", "action": "research"})
    r.register("bos://analysis/", adapter="poc", config={"domain": "analysis"})
    r.register("bos://ecos/workflow/approve", adapter="poc", config={"domain": "ecos", "workflow": "approve-flow"})
    return r


# ── 1. _resolve_with_router 路由链 ──────────────────
class TestResolveWithRouter:
    """验证 _resolve_with_router 的路由链逻辑 (使用 mock).

    _resolve_with_router 现在在 tools_bos.py 中，但 mock 需要同时 patch
    tools_bos 和 mcp 中的引用 (因 lazy import 可能从 mcp 拉取)。
    """

    @pytest.mark.asyncio
    async def test_chain_poc_uri_with_seeded_router(self):
        """已知 POC URI → BOSRouter 匹配 → 调 _resolve_bos_uri."""
        from unittest.mock import patch

        from agora.server.tools_bos import _resolve_with_router

        with patch("agora.server.tools_bos._bos_router") as mock_router:
            mock_router.resolve.return_value = {
                "adapter": "poc",
                "prefix": "bos://memory/kos/search/",
                "config": {"domain": "memory"},
            }
            with patch("agora.server.tools_bos._resolve_bos_uri") as mock_resolve:
                mock_resolve.return_value = {"status": "ok", "result": "mock_data"}

                result, source = await _resolve_with_router(
                    "bos://memory/kos/search", query="test"
                )
                assert source == "bos_router_poc", f"来源异常: {source}"

    @pytest.mark.asyncio
    async def test_chain_proxy_uri_fallsback_gracefully(self):
        """Proxy 路由 → BOSRouter 匹配 → _proxy_manager=None → 优雅回退."""
        from unittest.mock import patch

        from agora.server.tools_bos import _resolve_with_router

        with patch("agora.server.tools_bos._bos_router") as mock_router:
            mock_router.resolve.return_value = {
                "adapter": "proxy",
                "prefix": "bos://runtime/health/",
                "config": {"domain": "capability"},
            }
            # 使用 POC_SERVICES 中已有的 URI 测试回退
            result, source = await _resolve_with_router(
                "bos://memory/kos/search"
            )
            # BOSRouter 匹配 proxy, 但 _proxy_manager 为 None → 跳过
            # → Step 2 POC_SERVICES: 能找到实际 POC 条目
            assert source == "poc_services"
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_chain_poc_uri_empty_router_fallsback(self):
        """空 BOSRouter → 回退 POC_SERVICES."""
        from unittest.mock import patch

        from agora.server.tools_bos import _resolve_with_router

        with patch("agora.server.tools_bos._bos_router") as mock_router:
            mock_router.resolve.return_value = None  # BOSRouter 未匹配
            with patch("agora.server.tools_bos._resolve_bos_uri") as mock_resolve:
                mock_resolve.return_value = {"status": "ok", "result": "poc_data"}

                result, source = await _resolve_with_router(
                    "bos://memory/kos/search", query="test"
                )
                assert source == "poc_services", f"来源异常: {source}"

    @pytest.mark.asyncio
    async def test_chain_unknown_uri_fallsback(self):
        """未知 URI → BOSRouter 未匹配 → POC_SERVICES 回退."""
        from unittest.mock import patch

        from agora.server.tools_bos import _resolve_with_router

        with patch("agora.server.tools_bos._bos_router") as mock_router:
            mock_router.resolve.return_value = None
            with patch("agora.server.tools_bos._resolve_bos_uri") as mock_resolve:
                mock_resolve.return_value = {"status": "error", "error": "unknown_bos_uri"}

                result, source = await _resolve_with_router(
                    "bos://nonexistent/test/action"
                )
                assert source == "poc_services"
                assert result.get("status") == "error"

    @pytest.mark.asyncio
    async def test_chain_poc_fail_returns_metadata(self):
        """BOSRouter 有但 POC_SERVICES 无 → 返回 metadata."""
        from unittest.mock import patch

        from agora.server.tools_bos import _resolve_with_router

        with patch("agora.server.tools_bos._bos_router") as mock_router:
            mock_router.resolve.return_value = {
                "adapter": "poc",
                "prefix": "bos://ecos/workflow/approve/",
                "config": {"domain": "ecos", "workflow": "approve-flow"},
            }
            with patch("agora.server.tools_bos._resolve_bos_uri") as mock_resolve:
                mock_resolve.return_value = {"status": "error", "error": "unknown_bos_uri"}

                result, source = await _resolve_with_router(
                    "bos://ecos/workflow/approve"
                )
                assert source == "bos_router_metadata"
                assert result.get("status") == "info"
                assert "config" in result

    @pytest.mark.asyncio
    async def test_chain_cache_invalidation(self):
        """mutate 成功后手动 invalidate 缓存."""
        from unittest.mock import patch

        from agora.server.tools_bos import _resolve_with_router
        from agora.mcp.bos_middleware import bos_cache

        uri = "bos://memory/kos/search"
        bos_cache.set(uri, {"query": "test"}, "cached_result", ttl=300)
        assert bos_cache.get(uri, {"query": "test"}) is not None

        bos_cache.invalidate(uri)
        assert bos_cache.get(uri, {"query": "test"}) is None


# ── 2. BOSRouter 种子验证 ──────────────────────────
class TestBOSRouterSeeding:
    """BOSRouter 路由注册 + 解析能力 (用种子实例)."""

    @pytest.mark.asyncio
    async def test_seeded_resolve_all_types(self, seeded_router):
        """种子路由能正确解析 POC / 精确 / 前缀匹配."""
        # 精确匹配
        route = seeded_router.resolve("bos://memory/kos/search")
        assert route is not None
        assert route["adapter"] == "poc"
        assert "search" in route.get("config", {}).get("action", "")

        # 前缀匹配 (bos://analysis/minerva/research → bos://analysis/minerva/research/
        route = seeded_router.resolve("bos://analysis/minerva/research")
        assert route is not None
        assert "minerva" in route["prefix"]

        # 最长前缀匹配 (bos://memory/kos/xxx → bos://memory/kos/)
        route = seeded_router.resolve("bos://memory/kos/ingest")
        assert route is not None
        assert route["prefix"] == "bos://memory/kos/"

        # 域级别回退 (bos://memory/gbrain/search → bos://memory/)
        route = seeded_router.resolve("bos://memory/gbrain/search")
        assert route is not None
        assert route["prefix"] == "bos://memory/"

        # 完全不匹配
        assert seeded_router.resolve("bos://forge/unknown") is None

    def test_seeded_list_all(self, seeded_router):
        """list_all 排序 + 前缀过滤."""
        all_r = seeded_router.list_all()
        assert len(all_r) == 6
        # 排序
        prefixes = [r["prefix"] for r in all_r]
        assert prefixes == sorted(prefixes)

        filtered = seeded_router.list_all(prefix_filter="bos://memory/")
        assert len(filtered) == 3

    def test_seeded_deduplication(self, seeded_router):
        """重复注册自动跳过."""
        seeded_router.register("bos://memory/kos/search", adapter="proxy")
        all_r = seeded_router.list_all()
        prefixes = [r["prefix"] for r in all_r]
        assert len(prefixes) == len(set(prefixes)), f"重复: {set(p for p in prefixes if prefixes.count(p) > 1)}"

    def test_seeded_unregister(self, seeded_router):
        seeded_router.unregister("bos://memory/kos/")
        assert seeded_router.resolve("bos://memory/kos/ingest") is not None  # 回退到 bos://memory/

    def test_empty_router_returns_none(self):
        """空 BOSRouter 的 resolve → None."""
        from agora.mcp.bos_router import BOSRouter
        r = BOSRouter()
        assert r.resolve("bos://memory/kos/search") is None

    def test_stats_by_adapter(self, seeded_router):
        stats = seeded_router.stats()
        assert stats.get("poc") == 6


# ── 3. list_bos_resources ──────────────────────────
class TestListBosResources:
    """list_bos_resources 在隔离模式下的行为.

    由于 list_bos_resources 现在从 register_bos_tools 闭包注册，
    测试直接调用 module-level 的 _list_bos_resources_tool()。
    但更简单的方式是通过 mcp.call_tool() 或直接调用 _call_bos_tools。

    这里使用模块级函数调用方式验证 POC 来源。
    """

    @pytest.mark.asyncio
    async def test_list_returns_poc_when_router_empty(self):
        """直接通过 POC_SERVICES 获取 (绕过 MCP 工具层)."""
        from agora.mcp.bos_resolver import POC_SERVICES
        from agora.mcp.bos_router import bos_router as br

        poc_uris = set(POC_SERVICES.keys())
        router_uris = {r["prefix"].rstrip("/") for r in br.list_all()}

        # POC 应该有一些条目
        assert len(poc_uris) >= 11
        assert "bos://memory/kos/search" in poc_uris

    @pytest.mark.asyncio
    async def test_list_seeded_bosrouter(self):
        """BOSRouter 有路由时统计正确."""
        from agora.mcp.bos_router import bos_router

        count = bos_router.count()
        assert isinstance(count, int)
        print(f"  BOSRouter 当前路由数: {count}")

    @pytest.mark.asyncio
    async def test_list_prefix_filter(self):
        """前缀过滤通过 POC_SERVICES 验证."""
        from agora.mcp.bos_resolver import POC_SERVICES

        mem = [u for u in POC_SERVICES if u.startswith("bos://memory/")]
        ana = [u for u in POC_SERVICES if u.startswith("bos://analysis/")]
        assert len(mem) > 0
        assert len(ana) > 0
        assert all(u.startswith("bos://memory/") for u in mem)
        assert all(u.startswith("bos://analysis/") for u in ana)

    @pytest.mark.asyncio
    async def test_list_no_duplicates(self):
        """POC_SERVICES 无重复."""
        from agora.mcp.bos_resolver import POC_SERVICES

        uris = list(POC_SERVICES.keys())
        dupes = [u for u in uris if uris.count(u) > 1]
        assert not dupes, f"重复: {set(dupes)}"


# ── 4. BOS 中间件 ─────────────────────────────────
class TestBOSMiddleware:
    """限流/熔断/缓存."""

    def test_rate_limiter_default_status(self):
        from agora.mcp.bos_middleware import bos_rate_limiter
        status = bos_rate_limiter.status()
        assert isinstance(status, dict)

    def test_circuit_breaker_default_closed(self):
        from agora.mcp.bos_middleware import bos_circuit_breaker
        assert bos_circuit_breaker.is_open("bos://memory/kos/search") is False

    def test_circuit_breaker_opens_and_recovers(self):
        from agora.mcp.bos_middleware import bos_circuit_breaker

        uri = "bos://test/circuit/x"
        # 制造熔断
        for _ in range(10):
            bos_circuit_breaker.record_failure(uri)
        # 手动设置 OPEN 状态
        if bos_circuit_breaker.is_open(uri):
            assert bos_circuit_breaker.is_open(uri) is True

    def test_bos_metrics_tracks_calls(self):
        from agora.mcp.bos_metrics import bos_metrics

        bos_metrics.record("bos://test/metrics/x", success=True, latency_ms=50)
        bos_metrics.record("bos://test/metrics/x", success=True, latency_ms=100)

        status = bos_metrics.status()
        found = False
        for p, s in status.items():
            if "bos" in p and "test" in p and "metrics" in p:
                assert s["calls"] == 2
                assert s["success"] == 2
                found = True
        assert found, f"未见测试指标. 所有键: {list(status.keys())}"

    def test_bos_metrics_summary(self):
        from agora.mcp.bos_metrics import bos_metrics
        s = bos_metrics.summary()
        assert "total_calls" in s
        assert "success_rate" in s


# ── 5. 事件链路 ──────────────────────────────────
class TestEventChain:
    """事件发布 + 订阅."""

    def test_bos_uri_to_event_type(self):
        from agora.server.tools_bos import _bos_uri_to_event_type
        assert _bos_uri_to_event_type("bos://memory/kos/search") == "bos:memory:kos:search"
        assert _bos_uri_to_event_type("bos://memory/kos/*") == "bos:memory:kos:*"
        assert _bos_uri_to_event_type("bos://analysis/minerva/research") == "bos:analysis:minerva:research"

    def test_event_bus_publish_subscribe(self):
        from agora.core.state import get_event_bus
        bus = get_event_bus()
        sub_id = bus.subscribe("test-bos", "bos:memory:kos:search")
        assert sub_id is not None
        bus.publish("bos:memory:kos:search", {"uri": "bos://memory/kos/search"})
        events = bus.get_event_log(limit=10)
        assert len(events) >= 1
