"""Unit tests for VRAM and KV Cache budget estimator."""

from __future__ import annotations

from omlxc.dataplane.vram_budget import ModelArchitectureMeta, VRAMBudgetEstimator


def test_vram_estimator_bytes_per_token() -> None:
    # 64 layers, 8 kv heads, 128 head dim, 2 bytes/elem (FP16)
    # 2 * 64 * 8 * 128 * 2 = 262,144 bytes/token
    meta = ModelArchitectureMeta(
        model_id="coding",
        num_layers=64,
        num_kv_heads=8,
        head_dim=128,
        bytes_per_elem=2,
    )
    assert meta.bytes_per_token == 262144


def test_vram_estimator_calculation() -> None:
    estimator = VRAMBudgetEstimator()

    # 32,768 tokens on coding model (approx 8.44 GB KV Cache)
    kv_mb = estimator.estimate_kv_cache_mb("coding", context_tokens=32768, max_output_tokens=1024)
    assert 8000.0 < kv_mb < 9000.0

    total_mb = estimator.estimate_total_vram_mb("coding", context_tokens=32768, max_output_tokens=1024)
    # 17.5GB weights + ~8.4GB KV Cache = ~25.9GB
    assert 25000.0 < total_mb < 27000.0


def test_vram_headroom_admission() -> None:
    estimator = VRAMBudgetEstimator()

    # MBP with 128GB node (80GB available VRAM) -> safe headroom 85% = 68GB -> fits 8.4GB KV Cache
    admitted, kv_mb, reason = estimator.check_headroom_admission(
        "coding",
        context_tokens=32768,
        available_node_vram_mb=80000.0,
        safe_headroom_ratio=0.85,
    )
    assert admitted is True
    assert "admitted" in reason

    # Tiny node with only 4GB free memory -> 8.4GB KV Cache rejected with compaction advice
    res_fail = estimator.check_headroom_admission(
        "coding",
        context_tokens=32768,
        available_node_vram_mb=4000.0,
        safe_headroom_ratio=0.85,
    )
    assert res_fail.admitted is False
    assert res_fail.compaction_advised is True
    assert 0 < res_fail.max_safe_tokens < 32768
    assert 0.0 < res_fail.recommended_compaction_ratio <= 1.0
    assert "exceeds safe node headroom" in res_fail.reason


def test_context_compactor_messages() -> None:
    from omlxc.dataplane.vram_budget import ContextCompactor

    messages = [
        {"role": "system", "content": "You are a coding assistant."},
        {"role": "user", "content": "Let's build a distributed cache." + " long details" * 50},
        {"role": "assistant", "content": "Here is cache design." + " code sample" * 50},
        {"role": "user", "content": "Let's add LRU eviction policy." + " more specs" * 50},
        {"role": "assistant", "content": "Added LRU eviction." + " code" * 50},
        {"role": "user", "content": "Now run the tests."},
        {"role": "assistant", "content": "All tests passed successfully."},
    ]

    # Target small token budget (e.g. 150 tokens) -> triggers distillation
    result = ContextCompactor.compact_messages(messages, target_safe_tokens=150, keep_recent_turns=2)

    assert result.compacted_tokens < result.original_tokens
    assert result.pruned_tokens > 0
    assert result.compression_ratio > 0.0
    assert result.distilled_summary is not None
    assert "[Auto-Compacted Context Window Summary]" in result.distilled_summary
    # Recent turns preserved
    assert result.compacted_messages[-1]["content"] == "All tests passed successfully."
    assert result.compacted_messages[-2]["content"] == "Now run the tests."
    # System prompt preserved
    assert result.compacted_messages[0]["content"] == "You are a coding assistant."
