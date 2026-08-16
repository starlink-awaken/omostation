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

    total_mb = estimator.estimate_total_vram_mb(
        "coding", context_tokens=32768, max_output_tokens=1024
    )
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

    # Tiny node with only 4GB free memory -> 8.4GB KV Cache rejected
    admitted_fail, kv_mb_fail, reason_fail = estimator.check_headroom_admission(
        "coding",
        context_tokens=32768,
        available_node_vram_mb=4000.0,
        safe_headroom_ratio=0.85,
    )
    assert admitted_fail is False
    assert "exceeds safe node headroom" in reason_fail
