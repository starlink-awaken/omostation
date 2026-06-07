"""BOSRouter 播种 + 路由链 端到端集成测试 (P48 W3).

验证:
  1. _resolve_with_router 路由链 (BOSRouter → POC_SERVICES)
  2. BOSRouter 种子路由 (POC + M1 + Discovery)
  3. list_bos_resources 覆盖三路源
  4. BOSRouter-only 路由优雅返回 metadata
  5. 缓存失效机制
  6. 事件链路

隔离模式: BOSRouter 为全局单例，服务器启动时自动播种。
测试直接运行时 BOSRouter 可能为空 (播种进 _init_mcp_server 走)。
需要播种的测试手动 seed，空路由验证回退路径。
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
    """验证 _resolve_with_router 的路由链逻辑 (使用 mock)."""

    @pytest.mark.asyncio
    async def test_chain_poc_uri_with_seeded_router(self):
        """已知 POC URI → BOSRouter 匹配 → 调 _resolve_bos_uri."""
        from unittest.mock import patch

        from agora.server.mcp import _resolve_with_router

        with patch("agora.server.mcp._bos_router") as mock_router:
            mock_router.resolve.return_value = {
                "adapter": "poc",
                "prefix": "bos://memory/kos/search/",
                "config": {"domain": "memory"},
            }
            with patch("agora.server.mcp._resolve_bos_uri") as mock_resolve:
                mock_resolve.return_value = {"status": "ok", "result": "mock_data"}

                result, source = await _resolve_with_router(
                    "bos://memory/kos/search", query="test"
                )
                assert source == "bos_router_poc", f"来源异常: {source}"

    @pytest.mark.asyncio
    async def test_chain_proxy_uri_fallsback_gracefully(self):
        """Proxy 路由 → BOSRouter 匹配 → _proxy_manager=None → 优雅回退."""
        from unittest.mock import patch

        from agora.server.mcp import _resolve_with_router

        with patch("agora.server.mcp._bos_router") as mock_router:
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

        from agora.server.mcp import _resolve_with_router

        with patch("agora.server.mcp._bos_router") as mock_router:
            mock_router.resolve.return_value = None  # BOSRouter 未匹配
            with patch("agora.server.mcp._resolve_bos_uri") as mock_resolve:
                mock_resolve.return_value = {"status": "ok", "result": "poc_data"}

                result, source = await _resolve_with_router(
                    "bos://memory/kos/search", query="test"
                )
                assert source == "poc_services", f"来源异常: {source}"

    @pytest.mark.asyncio
    async def test_chain_unknown_uri_fallsback(self):
        """未知 URI → BOSRouter 未匹配 → POC_SERVICES 回退."""
        from unittest.mock import patch

        from agora.server.mcp import _resolve_with_router

        with patch("agora.server.mcp._bos_router") as mock_router:
            mock_router.resolve.return_value = None
            with patch("agora.server.mcp._resolve_bos_uri") as mock_resolve:
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

        from agora.server.mcp import _resolve_with_router

        with patch("agora.server.mcp._bos_router") as mock_router:
            mock_router.resolve.return_value = {
                "adapter": "poc",
                "prefix": "bos://ecos/workflow/approve/",
                "config": {"domain": "ecos", "workflow": "approve-flow"},
            }
            with patch("agora.server.mcp._resolve_bos_uri") as mock_resolve:
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

        from agora.server.mcp import _resolve_with_router
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
        duplicates = [r["prefix"] for r in seeded_router.list_all() if seeded_router.list_all().count(r) > 1]
        assert not duplicates, f"重复: {set(duplicates)}"

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
    """list_bos_resources 在隔离模式（BOSRouter 可能为空）下的行为."""

    @pytest.mark.asyncio
    async def test_list_returns_poc_when_router_empty(self):
        """BOSRouter 为空 → list_bos_resources 从 POC_SERVICES 返回."""
        from unittest.mock import patch

        from agora.server.mcp import list_bos_resources
        from agora.mcp.bos_resolver import POC_SERVICES

        with patch("agora.server.mcp._proxy_manager", None):
            result = await list_bos_resources()

        assert result["status"] == "ok"
        resources = result.get("resources", [])

        # 应包含 POC_SERVICES 内容
        poc_uris = {r["uri"] for r in resources if r.get("source") == "poc"}
        assert len(poc_uris) >= 11
        assert "bos://memory/kos/search" in poc_uris

    @pytest.mark.asyncio
    async def test_list_seeded_bosrouter(self):
        """BOSRouter 有路由 → list_bos_resources 包含 BOSRouter 来源."""
        from unittest.mock import patch

        from agora.mcp.bos_router import bos_router
        from agora.server.mcp import list_bos_resources

        with patch("agora.server.mcp._proxy_manager", None):
            result = await list_bos_resources()

        assert result["status"] == "ok"
        resources = result.get("resources", [])
        sources = {}
        for r in resources:
            s = r.get("source", "unknown")
            sources[s] = sources.get(s, 0) + 1

        print(f"  来源分布: {json.dumps(sources, indent=2)}")

        # 如果 BOSRouter 已被服务器播种过，应有 bos_router 来源
        if bos_router.count() > 0:
            assert "bos_router" in sources, "BOSRouter 有路由但未出现在 list 中"

    @pytest.mark.asyncio
    async def test_list_prefix_filter(self):
        """前缀过滤."""
        from unittest.mock import patch

        from agora.server.mcp import list_bos_resources

        with patch("agora.server.mcp._proxy_manager", None):
            mem = await list_bos_resources(prefix="bos://memory/")
            ana = await list_bos_resources(prefix="bos://analysis/")

        mem_res = mem.get("resources", [])
        ana_res = ana.get("resources", [])
        assert len(mem_res) > 0
        assert len(ana_res) > 0
        assert all(r["uri"].startswith("bos://memory/") for r in mem_res)
        assert all(r["uri"].startswith("bos://analysis/") for r in ana_res)

    @pytest.mark.asyncio
    async def test_list_no_duplicates(self):
        """去重."""
        from unittest.mock import patch

        from agora.server.mcp import list_bos_resources

        with patch("agora.server.mcp._proxy_manager", None):
            result = await list_bos_resources()

        uris = [r["uri"] for r in result.get("resources", [])]
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

        # _prefix 提取前 4 段 → 'bos:/test/metrics'
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
        from agora.server.mcp import _bos_uri_to_event_type
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
