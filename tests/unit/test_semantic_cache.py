"""Unit tests for Two-Tier Semantic & Prefix Cache."""

from __future__ import annotations

from omlxc.dataplane.semantic_cache import (
    CacheTier,
    SemanticCacheRegistry,
    normalize_semantic_fingerprint,
)


def test_semantic_fingerprint_normalization() -> None:
    p1 = "   What is   the capital  of France?  \n"
    p2 = "what is the capital of france?"
    assert normalize_semantic_fingerprint(p1) == normalize_semantic_fingerprint(p2)


def test_semantic_cache_l1_exact_and_l2_semantic() -> None:
    cache = SemanticCacheRegistry(max_entries=10)

    # 1. Store L1 Exact Prefix
    cache.store(
        "prefix_sha_123",
        "Exact Response 1",
        model_id="coding",
        tier=CacheTier.L1_EXACT,
        ttl_seconds=60.0,
    )

    res1, tier1 = cache.lookup(prefix_hash="prefix_sha_123")
    assert res1 == "Exact Response 1"
    assert tier1 == CacheTier.L1_EXACT

    # 2. Store L2 Semantic fingerprint
    prompt = "Explain quantum superposition in simple terms."
    fp = normalize_semantic_fingerprint(prompt)
    cache.store(
        fp,
        "Quantum explanation...",
        model_id="coding",
        tier=CacheTier.L2_SEMANTIC,
        ttl_seconds=60.0,
    )

    # Lookup with slight whitespace/casing differences
    res2, tier2 = cache.lookup(raw_prompt="  explain quantum superposition in simple terms. \n")
    assert res2 == "Quantum explanation..."
    assert tier2 == CacheTier.L2_SEMANTIC

    stats = cache.get_stats()
    assert stats["l1_exact_hits"] == 1
    assert stats["l2_semantic_hits"] == 1
    assert stats["hit_rate"] == 1.0


def test_semantic_cache_expiration_and_eviction() -> None:
    cache = SemanticCacheRegistry(max_entries=2)

    cache.store("k1", "v1", "coding", ttl_seconds=10.0, now=100.0)
    cache.store("k2", "v2", "coding", ttl_seconds=10.0, now=101.0)

    # Lookup after TTL expires
    res_exp, tier_exp = cache.lookup(prefix_hash="k1", now=120.0)
    assert res_exp is None
    assert tier_exp is None

    # Capacity eviction
    cache.store("k3", "v3", "coding", now=130.0)
    cache.store("k4", "v4", "coding", now=131.0)
    stats = cache.get_stats()
    assert stats["total_entries"] <= 2
