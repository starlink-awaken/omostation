"""End-to-end long-running agent stress & compute fabric resilience validation suite.

Validates:
1. 0ms TTFT System Prompt Prefix Warmer & Semantic Invariant Matching
2. Pre-emptive KV Cache Headroom Admission & Compaction Advisory (>85% limit)
3. Sliding-window Context Distillation (ContextCompactor) preserving recency
4. Heterogeneous cluster thermal/battery degradation and Priority QoS scoring
"""

from __future__ import annotations

from omlxc.dataplane.semantic_cache import (
    CacheTier,
    SemanticCacheRegistry,
    warm_system_prefixes,
)
from omlxc.dataplane.thermal import (
    PowerSource,
    ThermalGuard,
    ThermalPressureLevel,
)
from omlxc.dataplane.vram_budget import (
    ContextCompactor,
    VRAMBudgetEstimator,
)


def test_prefix_warmer_zero_latency_ttft_hit():
    """Verify that pre-warmed system prompt prefixes result in exact L1/L2 0ms hits."""
    cache = SemanticCacheRegistry(max_entries=100)
    system_prompt = (
        "You are the BDSK Virtual Board assistant. Adhere strictly to the four perspectives: "
        "Builder (Engineering & MVP), Devil (Risk & ROI), Sage (Context & First Principles), "
        "Keeper (Cybernetics & Process Memory). Always deliver objective, robust analysis."
    )

    # 1. Warm builtin system prefixes
    warm_result = warm_system_prefixes(cache, model_id="coding")
    assert warm_result["warmed_count"] >= 3
    assert "bdsk_virtual_board" in warm_result["prefixes"]

    # 2. Simulate subsequent Agent turn 1 with identical prompt
    resp, tier = cache.lookup(raw_prompt=system_prompt)
    assert resp is not None
    assert "[WARMED_PREFIX:bdsk_virtual_board]" in resp
    assert tier == CacheTier.L2_SEMANTIC


def test_vram_headroom_compaction_trigger_on_expansion():
    """Verify headroom admission detects safe threshold breaches and advises compaction."""
    estimator = VRAMBudgetEstimator()

    # 1. Small context (1,000 tokens) on a 32GB unified memory node
    small_admission = estimator.check_headroom_admission(
        model_id="coding",
        context_tokens=1000,
        available_node_vram_mb=32768.0,
        safe_headroom_ratio=0.85,
    )
    assert small_admission.admitted is True
    assert small_admission.compaction_advised is False

    # 2. Expanding long context (64,000 tokens) with limited available headroom (1,000 MB)
    # KV cache for coding model (64 layers, 8 heads, 128 dim) @ 64k tokens is ~16 GB > 850 MB safe budget
    large_admission = estimator.check_headroom_admission(
        model_id="coding",
        context_tokens=64000,
        available_node_vram_mb=1000.0,
        safe_headroom_ratio=0.85,
    )
    assert large_admission.admitted is False
    assert large_admission.compaction_advised is True
    assert large_admission.max_safe_tokens < 64000
    assert 0.0 < large_admission.recommended_compaction_ratio < 1.0


def test_sliding_window_context_compaction_continuity():
    """Verify ContextCompactor distills historical conversation into structured summary while preserving recency."""
    messages: list[dict[str, str]] = [
        {"role": "system", "content": "You are a specialized health informatics code architect."},
    ]

    # Generate 30 turns of realistic conversation history (each turn ~150-300 tokens)
    long_user_prompt = (
        "Develop an enterprise DRG settlement engine with strict medical insurance validation rules, "
        "including ICD-10 diagnostic code cross-checks, patient category reconciliation, and outlier cost capping. "
        "Include unit tests and edge cases for multiple concurrent ward admissions."
    )
    long_assistant_resp = (
        "Here is the production implementation of the DRG settlement engine: "
        "class DRGSettlementEngine: def __init__(self, rules): self.rules = rules; "
        "def calculate_payout(self, diagnosis, cost): return min(cost * 1.2, 50000.0). "
        "All edge cases and security isolation barriers have been verified."
    )

    for i in range(1, 31):
        messages.append({"role": "user", "content": f"Iteration {i}: {long_user_prompt}"})
        messages.append({"role": "assistant", "content": f"Response {i}: {long_assistant_resp}"})

    assert len(messages) == 61  # 1 system + 30 user + 30 assistant

    # Compaction strategy: target 1000 safe tokens, keep 2 recent turns
    compaction_res = ContextCompactor.compact_messages(
        messages=messages,
        target_safe_tokens=1000,
        keep_recent_turns=2,
    )

    assert compaction_res.compacted_tokens < compaction_res.original_tokens
    assert compaction_res.compression_ratio > 0.3
    assert compaction_res.distilled_summary is not None
    assert "[Auto-Compacted Context Window Summary]" in compaction_res.distilled_summary

    compacted_msgs = compaction_res.compacted_messages
    assert len(compacted_msgs) < len(messages)
    # System prompt + Summary message + 2 recent turns
    assert len(compacted_msgs) == 4  # system + summary + 2 recent turns (1 user + 1 assistant)
    assert compacted_msgs[0]["role"] == "system"
    assert "specialized health informatics" in compacted_msgs[0]["content"]
    assert "Iteration 30" in compacted_msgs[-2]["content"]  # Most recent user turn preserved


def test_heterogeneous_thermal_penalty_and_priority_qos():
    """Verify ThermalGuard applies correct degradation penalties under thermal pressure."""
    guard = ThermalGuard()

    # 1. Nominal AC state
    penalty_nominal = guard.calculate_penalty(ThermalPressureLevel.NOMINAL, PowerSource.AC)
    assert penalty_nominal == 1.0

    # 2. Heavy thermal throttle with battery low
    penalty_heavy = guard.calculate_penalty(ThermalPressureLevel.HEAVY, PowerSource.BATTERY, battery_percent=18.0)
    assert penalty_heavy <= 0.5  # Significant routing score reduction

    # 3. Trapping (critical)
    penalty_trapping = guard.calculate_penalty(ThermalPressureLevel.TRAPPING, PowerSource.BATTERY, battery_percent=10.0)
    assert penalty_trapping == 0.1
