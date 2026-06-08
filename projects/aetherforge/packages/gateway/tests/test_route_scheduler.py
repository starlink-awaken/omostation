"""Tests for RouteScheduler."""

from __future__ import annotations


def test_route_scheduler_basic():
    from llm_gateway.route_scheduler import RouteScheduler
    sched = RouteScheduler()
    route = sched.select(task="hello")
    if route:
        assert route.provider
        assert route.score > 0
        print(f"  ✅ Route: {route.provider} score={route.score}")
    else:
        print("  ⚠️  No providers available (expected offline)")


def test_route_strategies():
    from llm_gateway.route_scheduler import RouteStrategies
    b = RouteStrategies.get("balanced")
    c = RouteStrategies.get("cost_first")
    s = RouteStrategies.get("speed_first")
    q = RouteStrategies.get("quota_first")
    assert abs(sum(b.values()) - 1.0) < 0.01
    assert abs(sum(c.values()) - 1.0) < 0.01
    assert abs(sum(s.values()) - 1.0) < 0.01
    assert abs(sum(q.values()) - 1.0) < 0.01
    assert b["cost"] == 0.35
    assert c["cost"] == 0.70
    print("  ✅ RouteStrategies: 4 strategies validated")


def test_route_dataclass():
    from llm_gateway.route_scheduler import Route
    r = Route(provider="test", model="m1", score=0.9, cost_per_1k_input=0.01)
    assert r.provider == "test"
    assert r.model == "m1"
    assert r.score == 0.9
    assert r.cost_per_1k_input == 0.01
    print("  ✅ Route dataclass works")


def test_select_all_ranking():
    from llm_gateway.route_scheduler import RouteScheduler
    sched = RouteScheduler()
    routes = sched.select_all(task="hello")
    if routes:
        # Verify sorted descending
        for i in range(len(routes) - 1):
            assert routes[i].score >= routes[i + 1].score
        print(f"  ✅ select_all: {len(routes)} routes, top={routes[0].provider} ({routes[0].score})")
    else:
        print("  ⚠️  No routes (expected offline)")


def run_all():
    tests = [
        test_route_scheduler_basic,
        test_route_strategies,
        test_route_dataclass,
        test_select_all_ranking,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            import traceback
            print(f"  ❌ {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n  RouteScheduler tests: {passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all())
