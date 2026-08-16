"""Unit tests for System Prefix Warmer in omlxc."""

from __future__ import annotations

from omlxc.dataplane.semantic_cache import (
    BUILTIN_SYSTEM_PREFIXES,
    CacheTier,
    SemanticCacheRegistry,
    warm_system_prefixes,
)


def test_warm_system_prefixes_populates_cache() -> None:
    registry = SemanticCacheRegistry(max_entries=100)
    res = warm_system_prefixes(registry, model_id="coding")

    assert res["warmed_count"] == len(BUILTIN_SYSTEM_PREFIXES)
    assert res["warmed_count"] >= 3
    assert res["estimated_saved_tokens"] > 0
    assert "bdsk_virtual_board" in res["prefixes"]

    # Verify lookups hit L1 or L2
    for _prefix_name, raw_prompt in BUILTIN_SYSTEM_PREFIXES.items():
        content, tier = registry.lookup(raw_prompt=raw_prompt)
        assert content is not None
        assert tier in (CacheTier.L1_EXACT, CacheTier.L2_SEMANTIC)


def test_warm_system_prefixes_custom_override() -> None:
    registry = SemanticCacheRegistry(max_entries=100)
    custom = {"my_custom_prompt": "You are a specialized medical expert assistant."}
    res = warm_system_prefixes(registry, model_id="qwen-72b", custom_prefixes=custom)

    assert res["warmed_count"] == len(BUILTIN_SYSTEM_PREFIXES) + 1
    assert "my_custom_prompt" in res["prefixes"]

    content, tier = registry.lookup(raw_prompt="You are a specialized medical expert assistant.")
    assert content is not None
