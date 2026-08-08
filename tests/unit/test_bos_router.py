"""Unit tests for agora.mcp.bos_router — BOSRouter.

验证:
  1. register 路由注册 (前缀标准化 + 去重)
  2. unregister 路由注销
  3. resolve 最长前缀匹配
  4. list_all 前缀过滤
  5. count / stats 统计
"""

from __future__ import annotations

from agora.mcp.bos_router import BOSRouter


class TestBOSRouterRegister:
    """路由注册。"""

    def test_register_normalizes_trailing_slash(self):
        """register 应自动补全尾部斜杠。"""
        router = BOSRouter()
        router.register("bos://memory/kos", adapter="poc")
        assert "bos://memory/kos/" in router._routes

    def test_register_normalizes_double_slash(self):
        """尾部已有斜杠时不重复添加。"""
        router = BOSRouter()
        router.register("bos://memory/kos/", adapter="poc")
        assert "bos://memory/kos/" in router._routes

    def test_register_stores_config(self):
        """register 应存储 adapter 和 config。"""
        router = BOSRouter()
        config = {"domain": "memory", "transport": "stdio"}
        router.register("bos://memory/kos/search", adapter="poc", config=config)
        route = router._routes.get("bos://memory/kos/search/")
        assert route is not None
        assert route[0]["adapter"] == "poc"
        assert route[0]["config"] == config

    def test_register_default_config(self):
        """config 不传时应为 {}。"""
        router = BOSRouter()
        router.register("bos://memory/kos", adapter="poc")
        route = router._routes.get("bos://memory/kos/")
        assert route[0]["config"] == {}  # type: ignore[reportOptionalSubscript]
        assert route[0]["admission"]["status"] == "admitted"  # type: ignore[reportOptionalSubscript]

    def test_register_duplicate_skips(self):
        """重复注册同一 prefix 应跳过并记录 warning。"""
        router = BOSRouter()
        router.register("bos://memory/kos", adapter="poc")
        router.register("bos://memory/kos", adapter="proxy")  # duplicate
        route = router._routes.get("bos://memory/kos/")
        assert (
            route[0]["adapter"] == "poc"  # type: ignore[reportOptionalSubscript]
        )  # 仍然保留第一次的  # type: ignore[reportOptionalSubscript]

    def test_register_rejects_without_admission_and_keeps_route_absent(self):
        router = BOSRouter(
            admission_evaluator=lambda _request: {
                "status": "rejected",
                "reasons": ["provider_unavailable"],
            }
        )

        registered = router.register(
            "bos://external/provider/search",
            adapter="proxy",
            config={"domain": "external", "source": "external.resources"},
        )

        assert registered is False
        assert router.resolve("bos://external/provider/search") is None
        assert router.admission_rejections() == [
            {
                "prefix": "bos://external/provider/search/",
                "adapter": "proxy",
                "status": "rejected",
                "reasons": ["provider_unavailable"],
                "provider": None,
            }
        ]

    def test_register_sends_only_allowlisted_admission_metadata(self):
        requests = []

        def evaluate(request):
            requests.append(request)
            return {"status": "admitted", "provider": "stub"}

        router = BOSRouter(admission_evaluator=evaluate)
        router.register(
            "bos://external/provider/search",
            adapter="proxy",
            config={
                "domain": "external",
                "source": "external.resources",
                "secret": "must-not-cross-boundary",
                "admission": {
                    "resource_id": "source:provider",
                    "permission_ref": "credential://external",
                },
            },
        )

        assert requests == [
            {
                "domain": "external",
                "role": "route_registry",
                "capability": "bos://external/provider/search/",
                "adapter": "proxy",
                "source": "external.resources",
                "resource_id": "source:provider",
                "permission_ref": "credential://external",
            }
        ]

    def test_register_rejects_unsupported_admission_metadata(self):
        router = BOSRouter(
            admission_evaluator=lambda _request: {
                "status": "admitted",
            }
        )

        assert (
            router.register(
                "bos://external/provider/search",
                adapter="proxy",
                config={
                    "domain": "external",
                    "admission": {"access_token": "must-not-land"},
                },
            )
            is False
        )
        assert router.resolve("bos://external/provider/search") is None

    def test_default_router_fails_closed_when_provider_is_missing(self, monkeypatch):
        from agora.admission import port, reset_admission_provider_cache

        monkeypatch.delenv("AGORA_ADMISSION_MODE", raising=False)
        monkeypatch.setenv("AGORA_ADMISSION_PROVIDER", "missing.module:PROVIDER")
        monkeypatch.setattr(port, "_SOFT_PROVIDERS", ())
        monkeypatch.setattr(
            port.metadata,
            "entry_points",
            lambda: type("EP", (), {"select": lambda **k: []})(),
        )
        reset_admission_provider_cache()

        router = BOSRouter()
        assert (
            router.register("bos://external/provider/search", adapter="proxy") is False
        )
        assert router.count() == 0
        assert router.admission_rejections()[0]["reasons"]

    def test_seed_count_excludes_rejected_routes(self):
        router = BOSRouter(
            admission_evaluator=lambda _request: {
                "status": "rejected",
                "reasons": ["denied"],
            }
        )

        count = router.seed_from_poc(
            [{"uri": "bos://external/provider/search", "domain": "external"}]
        )

        assert count == 0
        assert router.count() == 0


class TestBOSRouterUnregister:
    """路由注销。"""

    def test_unregister_removes_route(self):
        router = BOSRouter()
        router.register("bos://memory/kos", adapter="poc")
        router.unregister("bos://memory/kos")
        assert "bos://memory/kos/" not in router._routes

    def test_unregister_normalizes_slash(self):
        router = BOSRouter()
        router.register("bos://memory/kos/", adapter="poc")
        router.unregister("bos://memory/kos/")
        assert "bos://memory/kos/" not in router._routes

    def test_unregister_nonexistent_silent(self):
        """注销不存在的路由不应报错。"""
        router = BOSRouter()
        router.unregister("bos://nonexistent/xxx")  # should not raise


class TestBOSRouterResolve:
    """最长前缀匹配。"""

    def setup_method(self):
        self.router = BOSRouter()
        self.router.register(
            "bos://memory/", adapter="poc", config={"domain": "memory"}
        )
        self.router.register(
            "bos://memory/kos/",
            adapter="poc",
            config={"domain": "memory", "package": "kos"},
        )
        self.router.register(
            "bos://memory/kos/search", adapter="poc", config={"action": "search"}
        )
        self.router.register(
            "bos://analysis/", adapter="poc", config={"domain": "analysis"}
        )

    def test_exact_match(self):
        """完整 URI 最长前缀匹配 — 无尾部斜杠也匹配。"""
        route = self.router.resolve("bos://memory/kos/search")
        assert route is not None
        assert route["prefix"] == "bos://memory/kos/search/"
        assert route["config"]["action"] == "search"

    def test_longest_prefix_wins(self):
        """bos://memory/kos/xxx 应匹配 bos://memory/kos/ 而非 bos://memory/。"""
        route = self.router.resolve("bos://memory/kos/ingest")
        assert route is not None
        assert route["prefix"] == "bos://memory/kos/"

    def test_fallback_to_shorter_prefix(self):
        """bos://memory/gbrain/search 无更精确匹配，回退到 bos://memory/。"""
        route = self.router.resolve("bos://memory/gbrain/search")
        assert route is not None
        assert route["prefix"] == "bos://memory/"
        assert route["config"]["domain"] == "memory"

    def test_no_match_returns_none(self):
        """完全不匹配应返回 None。"""
        route = self.router.resolve("bos://forge/unknown")
        assert route is None

    def test_different_domain_match(self):
        """不同域应正确匹配。"""
        route = self.router.resolve("bos://analysis/minerva/research")
        assert route is not None
        assert route["prefix"] == "bos://analysis/"


class TestBOSRouterListAll:
    """路由列表。"""

    def setup_method(self):
        self.router = BOSRouter()
        self.router.register("bos://memory/kos/search", adapter="poc")
        self.router.register("bos://memory/kronos/ingest", adapter="poc")
        self.router.register("bos://analysis/minerva/research", adapter="poc")

    def test_list_all_returns_all(self):
        all_routes = self.router.list_all()
        assert len(all_routes) == 3

    def test_list_all_sorted(self):
        """列表应按 prefix 排序。"""
        all_routes = self.router.list_all()
        prefixes = [r["prefix"] for r in all_routes]
        assert prefixes == sorted(prefixes)

    def test_list_all_with_prefix_filter(self):
        """前缀过滤。"""
        filtered = self.router.list_all(prefix_filter="bos://memory/")
        assert len(filtered) == 2
        assert all(r["prefix"].startswith("bos://memory/") for r in filtered)

    def test_list_all_no_match_filter(self):
        filtered = self.router.list_all(prefix_filter="bos://forge/")
        assert filtered == []


class TestBOSRouterStats:
    """统计功能。"""

    def test_count_empty(self):
        router = BOSRouter()
        assert router.count() == 0

    def test_count_after_register(self):
        router = BOSRouter()
        router.register("bos://memory/kos", adapter="poc")
        router.register("bos://analysis/", adapter="proxy")
        assert router.count() == 2

    def test_stats_by_adapter(self):
        router = BOSRouter()
        router.register("bos://memory/kos", adapter="poc")
        router.register("bos://memory/kronos", adapter="poc")
        router.register("bos://analysis/", adapter="proxy")
        stats = router.stats()
        assert stats.get("poc") == 2
        assert stats.get("proxy") == 1

    def test_stats_empty(self):
        router = BOSRouter()
        assert router.stats() == {}


class TestBOSRouterSingleton:
    """全局单例。"""

    def test_singleton_is_default_instance(self):
        from agora.mcp.bos_router import bos_router

        assert isinstance(bos_router, BOSRouter)

    def test_singleton_registers_and_resolves(self):
        from agora.mcp.bos_router import bos_router

        bos_router.register("bos://test/route", adapter="poc")
        route = bos_router.resolve("bos://test/route/go")
        assert route is not None
        assert route["adapter"] == "poc"
        bos_router.unregister("bos://test/route")
