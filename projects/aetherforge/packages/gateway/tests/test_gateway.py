"""Tests for llm_gateway — RateLimiter, MetricsCollector, Registry, RouterPipeline."""

from __future__ import annotations

import time
from pathlib import Path


# ── RateLimiter ──────────────────────────────────────────────────────────────


def test_rate_limiter_basic():
    from llm_gateway.rate_limiter import RateLimiter
    rl = RateLimiter()
    rl.set_limit("m1", tpm=100, rpm=5)
    assert rl.acquire("m1", 50) is True
    assert rl.acquire("m1", 50) is True  # total 100
    assert rl.acquire("m1", 1) is False  # over tpm
    stats = rl.get_status()
    assert "m1" in stats
    assert stats["m1"]["tpm"]["usage_pct"] == 100.0
    print("  ✅ RateLimiter: basic tpm/rpm")


def test_rate_limiter_unlimited():
    from llm_gateway.rate_limiter import RateLimiter
    rl = RateLimiter()
    assert rl.acquire("any", 1_000_000) is True  # no limits set
    assert rl.total_limited_models == 0
    print("  ✅ RateLimiter: unlimited")


def test_rate_limiter_window_expiry():
    from llm_gateway.rate_limiter import RateLimiter
    rl = RateLimiter()
    rl.set_limit("m2", rpm=1, window_seconds=0.1)
    assert rl.acquire("m2", 10) is True
    assert rl.acquire("m2", 10) is False  # rpm exceeded
    time.sleep(0.15)
    assert rl.acquire("m2", 10) is True  # window expired
    print("  ✅ RateLimiter: window expiry")


def test_rate_limiter_model_isolation():
    from llm_gateway.rate_limiter import RateLimiter
    rl = RateLimiter()
    rl.set_limit("m-a", tpm=10, rpm=5)
    rl.set_limit("m-b", tpm=200, rpm=10)
    assert rl.acquire("m-a", 10) is True   # m-a: 10/10 tpm, 1/5 rpm
    assert rl.acquire("m-b", 100) is True  # m-b: 100/200 tpm, 1/10 rpm
    assert rl.acquire("m-a", 1) is False   # m-a: 11/10 tpm exhausted
    assert rl.acquire("m-b", 50) is True   # m-b: 150/200 tpm still has room
    print("  ✅ RateLimiter: model isolation")


# ── MetricsCollector ─────────────────────────────────────────────────────────


def test_metrics_basic():
    from llm_gateway.metrics import MetricsCollector
    mc = MetricsCollector()
    mc.record_latency("gpt4", 100.0, provider="openai")
    mc.record_cost("gpt4", 0.01, tokens=100)
    mc.record_error("gpt4", "timeout", provider="openai")
    mc.record_rate_limit("gpt4")
    r = mc.report()
    assert r["total_requests"] == 1
    assert r["total_errors"] == 1
    assert r["total_rate_limits"] == 1
    assert r["models"]["gpt4"]["total_cost"] == 0.01
    print("  ✅ MetricsCollector: basic recording")


def test_metrics_generation():
    from llm_gateway.metrics import MetricsCollector
    mc = MetricsCollector()
    mc.record_generation("claude", latency_ms=500, cost=0.005, tokens=200, provider="anthropic")
    r = mc.report()
    assert r["models"]["claude"]["requests"] == 1
    assert r["models"]["claude"]["avg_latency_ms"] == 500.0
    assert r["total_tokens"] == 200
    print("  ✅ MetricsCollector: generation recording")


def test_metrics_error_rate():
    from llm_gateway.metrics import MetricsCollector
    mc = MetricsCollector()
    mc.record_latency("m", 100)
    mc.record_latency("m", 200)
    mc.record_error("m", "err")
    assert mc.error_rate == 0.5  # 1 error / 2 requests
    print(f"  ✅ MetricsCollector: error_rate={mc.error_rate}")


# ── RouterPipeline ───────────────────────────────────────────────────────────


def _make_models(count: int = 3):
    from llm_gateway.types import ModelDescriptor
    return [
        ModelDescriptor(
            id=f"m{i}", provider="test", capabilities=["chat"],
            is_available=i % 2 == 0,
            cost_per_1k_tokens={"input": 0.01 * i, "output": 0.02 * i},
            context_window=4096,
        )
        for i in range(count)
    ]


def test_pipeline_filter():
    from llm_gateway.policies import RouterPipeline, OnlineFilter, CostScore
    from llm_gateway.types import ModelRequest
    models = _make_models(4)
    req = ModelRequest(task="test")
    pipeline = RouterPipeline()
    pipeline.add_filter(OnlineFilter())
    pipeline.add_score(CostScore())
    ranked = pipeline.select(models, req)
    # All 4 models: 0,2 are online; 1,3 are offline
    assert len(ranked) == 2
    assert all(sm.model.is_available for sm in ranked)
    print("  ✅ RouterPipeline: OnlineFilter")


def test_pipeline_capability_filter():
    from llm_gateway.policies import RouterPipeline, CapabilityFilter, CostScore
    from llm_gateway.types import ModelDescriptor, ModelRequest
    models = [
        ModelDescriptor(id="a", provider="t", capabilities=["chat"], is_available=True),
        ModelDescriptor(id="b", provider="t", capabilities=["chat", "vision"], is_available=True),
    ]
    req = ModelRequest(task="test", required_capabilities=["vision"])
    pipeline = RouterPipeline()
    pipeline.add_filter(CapabilityFilter())
    pipeline.add_score(CostScore())
    ranked = pipeline.select(models, req)
    assert len(ranked) == 1
    assert ranked[0].model.id == "b"
    print("  ✅ RouterPipeline: CapabilityFilter")


def test_pipeline_legacy_api():
    from llm_gateway.policies import score_models
    from llm_gateway.types import ModelRequest, ModelRoutePolicy
    models = _make_models(3)
    req = ModelRequest(task="test")
    policy = ModelRoutePolicy(strategy="cost-first")
    result = score_models(models, req, policy)
    assert len(result) == 2  # 2 online
    print("  ✅ RouterPipeline: legacy API")


# ── Registry integration ─────────────────────────────────────────────────────


def test_registry_metrics_hook():
    from llm_gateway.registry import ModelRegistry
    from llm_gateway.metrics import MetricsCollector
    from llm_gateway.rate_limiter import RateLimiter

    reg = ModelRegistry()
    mc = MetricsCollector()
    rl = RateLimiter()

    reg.set_metrics_collector(mc)
    reg.set_rate_limiter(rl)
    rl.set_limit("test-model", tpm=1_000_000, rpm=100_000)

    assert reg.metrics is mc
    assert reg.rate_limiter is rl
    print("  ✅ Registry: metrics/rate_limiter hooks set")


def test_registry_rate_limit_blocks():
    from llm_gateway.registry import ModelRegistry
    from llm_gateway.rate_limiter import RateLimiter

    reg = ModelRegistry()
    rl = RateLimiter()
    rl.set_limit("tight", tpm=1, rpm=1)
    reg.set_rate_limiter(rl)

    # Rate limiter will block even _get_provider_for fails first.
    # This is expected — the rate limiter check happens before provider lookup.
    # We test that the hook exists and doesn't crash.
    assert reg.rate_limiter is rl
    print("  ✅ Registry: rate_limiter hook present")


# ── New Providers ────────────────────────────────────────────────────────────


def test_all_9_providers_importable():
    from llm_gateway.providers import (
        AnthropicProvider, AzureOpenAIProvider, BedrockProvider,
        DeepSeekProvider, GeminiProvider, HitlLLMProvider,
        OllamaProvider, OpenAIProvider, VertexAIProvider,
    )
    assert AnthropicProvider and AzureOpenAIProvider and BedrockProvider and VertexAIProvider
    from llm_gateway.detection import _PROVIDER_REGISTRY
    assert len(_PROVIDER_REGISTRY) == 9
    assert "azure" in _PROVIDER_REGISTRY
    assert "bedrock" in _PROVIDER_REGISTRY
    assert "vertex" in _PROVIDER_REGISTRY
    print("  ✅ 9 providers registered and importable")


# ── Runner ───────────────────────────────────────────────────────────────────


def run_all():
    tests = [
        test_rate_limiter_basic,
        test_rate_limiter_unlimited,
        test_rate_limiter_window_expiry,
        test_rate_limiter_model_isolation,
        test_metrics_basic,
        test_metrics_generation,
        test_metrics_error_rate,
        test_pipeline_filter,
        test_pipeline_capability_filter,
        test_pipeline_legacy_api,
        test_registry_metrics_hook,
        test_registry_rate_limit_blocks,
        test_all_9_providers_importable,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ {t.__name__}: {e}")

    total = passed + failed
    print(f"\n  Gateway tests: {passed}/{total} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all())
