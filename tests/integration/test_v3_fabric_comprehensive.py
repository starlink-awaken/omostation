"""
Comprehensive End-to-End Integration Suite for omlxc v3.3.0 Compute Fabric.

Validates:
1. Multi-node environmental telemetry & thermal guard spillover
2. Semantic intent triage & model tier routing
3. Dual-mode session & prefix cache affinity with in-flight concurrency load-shedding
4. Full-outage last-resort self-healing probe
5. Benchmark performance drift detection
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from omlxc.benchmark import PerformanceDriftDetector
from omlxc.dataplane.affinity import (
    AffinityConfig,
    SessionAffinityRegistry,
    calculate_prefix_hash,
)
from omlxc.dataplane.circuit_breaker import CircuitBreakerRegistry
from omlxc.dataplane.concurrency import ConcurrencyTracker
from omlxc.dataplane.thermal import (
    PowerSource,
    ThermalGuard,
    ThermalPressureLevel,
)
from omlxc.dataplane.triage import ComplexityTier, TriageClassifier
from omlxc.domain import RouteProfile, RouteRequest
from omlxc.domain.protocols import ChatMessage
from omlxc.scheduler.models import PlacementSnapshot, default_policies
from omlxc.scheduler.planner import RoutePlanner
from omlxc.storage.models import BenchmarkRunRecord


def _create_cluster_placements(
    *,
    mbp_thermal_penalty: float = 1.0,
    mbp_in_flight: int = 0,
    mbp_affinity_bonus: float = 1.0,
    mbp_circuit_open: bool = False,
    mini_thermal_penalty: float = 1.0,
    mini_in_flight: int = 0,
    mini_affinity_bonus: float = 1.0,
    mini_circuit_open: bool = False,
) -> tuple[PlacementSnapshot, ...]:
    mbp = PlacementSnapshot(
        placement_id="coding--mbp-m5-max",
        model_id="coding",
        backend_id="omlx_app",
        backend_model_id="qwen-27b",
        node_id="mbp-m5-max-128g",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=32768,
        memory_admitted=True,
        loaded=True,
        ttft_ms=20.0,
        throughput_tps=58.0,
        queue_depth=0,
        error_rate=0.0,
        network_cost_ms=0.0,
        affinity=1.0,
        available_concurrency=4,
        local=True,
        security_allowed=True,
        circuit_open=mbp_circuit_open,
        in_flight=mbp_in_flight,
        affinity_bonus=mbp_affinity_bonus,
        max_concurrency=4,
        thermal_penalty=mbp_thermal_penalty,
        tier="reasoning",
    )

    mini = PlacementSnapshot(
        placement_id="coding--mac-mini-m4",
        model_id="coding",
        backend_id="lm_studio",
        backend_model_id="gemma-4b",
        node_id="mac-mini-m4-24g",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=16384,
        memory_admitted=True,
        loaded=True,
        ttft_ms=35.0,
        throughput_tps=45.0,
        queue_depth=0,
        error_rate=0.0,
        network_cost_ms=5.0,
        affinity=0.85,
        available_concurrency=2,
        local=True,
        security_allowed=True,
        circuit_open=mini_circuit_open,
        in_flight=mini_in_flight,
        affinity_bonus=mini_affinity_bonus,
        max_concurrency=2,
        thermal_penalty=mini_thermal_penalty,
        tier="fast",
    )

    return (mbp, mini)


def test_fabric_thermal_spillover_when_primary_throttled() -> None:
    """When laptop node is under Heavy Thermal pressure, traffic spills to cool desktop."""
    thermal_guard = ThermalGuard()
    # Simulate MBP getting Heavy thermal
    thermal_guard.update_node_state(
        node_id="mbp-m5-max-128g",
        thermal_level=ThermalPressureLevel.HEAVY,
        power_source=PowerSource.BATTERY,
        battery_percent=35.0,
    )
    mbp_state = thermal_guard.get_node_state("mbp-m5-max-128g", is_local=False)
    assert mbp_state.penalty_multiplier == 0.5

    # Mac mini remains cool on AC power
    mini_state = thermal_guard.get_node_state("mac-mini-m4-24g", is_local=False)
    assert mini_state.penalty_multiplier == 1.0

    planner = RoutePlanner(default_policies())
    snapshots = _create_cluster_placements(
        mbp_thermal_penalty=mbp_state.penalty_multiplier,
        mini_thermal_penalty=mini_state.penalty_multiplier,
    )

    req = RouteRequest(
        request_id="req-spillover-thermal",
        model_id="coding",
        profile=RouteProfile.INTERACTIVE,
        context_tokens=1000,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )

    decision = planner.plan(req, snapshots)
    # Mac mini wins because MBP is penalised by 0.5x thermal multiplier
    assert decision.selected_placement_id == "coding--mac-mini-m4"


def test_fabric_semantic_triage_routing() -> None:
    """Triage classifies prompts accurately into FAST vs REASONING tiers."""
    triage = TriageClassifier()

    # 1. Complex short prompt with deep concurrency/algorithm keywords
    msg_complex = (
        ChatMessage(
            role="user",
            content="Design a lock-free multi-producer queue to avoid ABA problem.",
        ),
    )
    res_complex = triage.classify(messages=msg_complex, context_tokens=40)
    assert res_complex.tier == ComplexityTier.REASONING

    # 2. Simple typo fix
    msg_simple = (ChatMessage(role="user", content="fix typo in variable name"),)
    res_simple = triage.classify(messages=msg_simple, context_tokens=15)
    assert res_simple.tier == ComplexityTier.FAST


@pytest.mark.asyncio
async def test_fabric_affinity_with_concurrency_spillover() -> None:
    """Session affinity locks turn-2 to MBP, and spills over when peak concurrency is hit."""
    affinity_reg = SessionAffinityRegistry(AffinityConfig(session_ttl_seconds=900.0))
    tracker = ConcurrencyTracker(default_max_concurrency=4)
    planner = RoutePlanner(default_policies())

    sys_msg = ChatMessage(role="system", content="You are a strict compiler architect.")
    user_msg1 = ChatMessage(role="user", content="Build a CFG visualizer.")
    p_hash = calculate_prefix_hash((sys_msg, user_msg1))

    session_id = "session-agent-42"
    # Turn 1
    snapshots_t1 = _create_cluster_placements()
    req1 = RouteRequest(
        request_id=session_id,
        model_id="coding",
        profile=RouteProfile.QUALITY,
        context_tokens=2000,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )
    decision1 = planner.plan(req1, snapshots_t1)
    assert decision1.selected_placement_id == "coding--mbp-m5-max"

    affinity_reg.record_session_placement(session_id, decision1.selected_placement_id)
    if p_hash:
        affinity_reg.record_prefix_placement(p_hash, decision1.selected_placement_id)

    # Turn 2: With affinity bonus (1.35x) under normal load
    snapshots_t2 = _create_cluster_placements(mbp_affinity_bonus=1.35)
    decision2 = planner.plan(req1, snapshots_t2)
    assert decision2.selected_placement_id == "coding--mbp-m5-max"

    # Turn 3: When MBP has 4 in-flight requests (maxed out)
    mbp_id = "coding--mbp-m5-max"
    async with (
        tracker.track(mbp_id),
        tracker.track(mbp_id),
        tracker.track(mbp_id),
        tracker.track(mbp_id),
    ):
        assert tracker.get_in_flight(mbp_id) == 4
        snapshots_maxed = _create_cluster_placements(
            mbp_affinity_bonus=1.35,
            mbp_in_flight=4,
            mini_in_flight=0,
        )
        decision_overflow = planner.plan(req1, snapshots_maxed)
        # Must overflow to Mac mini despite affinity bonus
        assert decision_overflow.selected_placement_id == "coding--mac-mini-m4"


def test_fabric_last_resort_probing_and_drift_detection() -> None:
    """Circuit breaker triggers probe on total outage, and drift detector flags drops."""
    cb_reg = CircuitBreakerRegistry()
    planner = RoutePlanner(default_policies())

    mbp_id = "coding--mbp-m5-max"
    mini_id = "coding--mac-mini-m4"

    # Trip both circuit breakers
    for pid in (mbp_id, mini_id):
        b = cb_reg.get_or_create(pid)
        for _ in range(3):
            b.record_failure(now=10.0)

    snapshots_broken = _create_cluster_placements(mbp_circuit_open=True, mini_circuit_open=True)
    req = RouteRequest(
        request_id="emergency-probe",
        model_id="coding",
        profile=RouteProfile.INTERACTIVE,
        context_tokens=500,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )
    decision = planner.plan(req, snapshots_broken)
    # Probe must succeed and select primary candidate
    assert decision.selected_placement_id == mbp_id
    assert "last_resort_probing=true" in decision.explanation

    # Test drift detector
    now = datetime.now(UTC)
    records = [
        BenchmarkRunRecord("r1", "qwen-27b", mbp_id, "mbp", 100.0, 20.0, 20.0, 58.0, None, now - timedelta(days=2)),
        BenchmarkRunRecord("r2", "qwen-27b", mbp_id, "mbp", 100.0, 20.0, 20.0, 56.0, None, now - timedelta(days=1)),
        BenchmarkRunRecord("r3", "qwen-27b", mbp_id, "mbp", 100.0, 20.0, 35.0, 35.0, None, now),
    ]
    detector = PerformanceDriftDetector(drift_threshold=0.25)
    reports = detector.detect(records)
    assert len(reports) == 1
    assert reports[0].is_drifted is True
    assert reports[0].drift_ratio > 0.35
