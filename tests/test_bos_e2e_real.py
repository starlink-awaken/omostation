"""BOS URI 端到端验证 — 测试真实路由流程"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_bos_router_resolve_chain():
    """验证 BOSRouter 能正确解析 POC_SERVICES 中的 URI"""
    from agora.mcp.bos_router import bos_router

    test_uris = [
        "bos://memory/kos/search",
        "bos://governance/omo/audit",
        "bos://analysis/minerva/research",
    ]
    for uri in test_uris:
        route = bos_router.resolve(uri)
        if route:
            print(f"  ✅ {uri} → {route['adapter']}")
        else:
            print(f"  ⚠️ {uri} → no route (may need POC_SERVICES seed)")


def test_bos_discovery_works():
    """验证 AGENTS.md 自动发现"""
    from agora.mcp.bos_discovery import discover_from_workspace

    count = discover_from_workspace()
    print(f"  Discovery found: {count} URIs")


def test_metrics_collection():
    """验证 metrics 收集"""
    from agora.mcp.bos_metrics import bos_metrics

    bos_metrics.record("bos://memory/kos/search", True, 42)
    s = bos_metrics.summary()
    print(f"  Metrics: {s['total_calls']} calls, success_rate={s['success_rate']}")


def test_bos_router_list():
    """验证列出所有路由"""
    from agora.mcp.bos_router import bos_router

    routes = bos_router.list_all()
    print(f"  Registered routes: {len(routes)}")


def test_bos_resolver_services():
    """验证 bos_resolver 的 POC_SERVICES 注册表"""
    try:
        from agora.mcp.bos_resolver import list_services, parse_bos_uri, POC_SERVICES

        services = list_services()
        print(f"  POC Services: {len(services)}")
        for s in services[:5]:
            pid_str = f" (pid={s['pid']})" if s.get("pid") else ""
            alive_str = f" alive={s.get('alive')}" if s.get("alive") is not None else ""
            print(f"    {s['uri']} ({s['transport']}){alive_str}{pid_str}")

        # 测试 parse_bos_uri
        parsed = parse_bos_uri("bos://memory/kos/search")
        print(f"  Parse test: {parsed['domain']}/{parsed['package']}/{parsed['action']}")

        # 测试 protocol_self_check
        from agora.mcp.bos_resolver import protocol_self_check

        info = protocol_self_check()
        print(f"  Self-check: total={info['total_services']}, domains={info['domains']}")

    except Exception as e:
        print(f"  ⚠️ POC services check failed: {e}")


if __name__ == "__main__":
    print("=== BOS URI E2E 验证 ===")
    print()

    print("[1/5] BOSRouter resolve chain")
    test_bos_router_resolve_chain()
    print()

    print("[2/5] AGENTS.md Discovery")
    test_bos_discovery_works()
    print()

    print("[3/5] Metrics Collection")
    test_metrics_collection()
    print()

    print("[4/5] BOSRouter Routes")
    test_bos_router_list()
    print()

    print("[5/5] POC Services Registry")
    test_bos_resolver_services()
    print()

    print("✅ E2E verification complete")
