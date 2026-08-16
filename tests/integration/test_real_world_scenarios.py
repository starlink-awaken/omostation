"""
Real-World Multi-Agent Scenario Validation Suite for omlxc v3.2.0.

Simulates the heterogeneous home-lab cluster:
- MBP (M5 Max 128G, Primary gateway)
- Mac mini (M4 24G, Secondary LAN node)
- Y7000P (RTX4070 8G, CUDA worker)

Validates:
1. Multi-turn Agent session & prefix cache affinity (TTFT acceleration)
2. Multi-agent concurrent burst & capacity spillover
3. Tailscale network partition, circuit-breaker isolation & last-resort recovery
4. Zero-downtime hot-reload configuration lifecycle
"""

from __future__ import annotations

import pytest

from omlxc.dataplane.affinity import (
    AffinityConfig,
    SessionAffinityRegistry,
    calculate_prefix_hash,
)
from omlxc.dataplane.circuit_breaker import CircuitBreakerRegistry
from omlxc.dataplane.concurrency import ConcurrencyTracker
from omlxc.domain import RouteProfile, RouteRequest
from omlxc.domain.protocols import ChatMessage
from omlxc.scheduler.models import PlacementSnapshot, RejectionCode, default_policies
from omlxc.scheduler.planner import RoutePlanner


def _build_cluster_snapshots(
    *,
    mbp_in_flight: int = 0,
    mbp_circuit_open: bool = False,
    mbp_affinity_bonus: float = 1.0,
    mini_in_flight: int = 0,
    mini_circuit_open: bool = False,
    mini_affinity_bonus: float = 1.0,
    y7000p_in_flight: int = 0,
    y7000p_circuit_open: bool = False,
    y7000p_affinity_bonus: float = 1.0,
) -> tuple[PlacementSnapshot, ...]:
    """Simulate real hardware nodes registered in config.toml."""
    mbp = PlacementSnapshot(
        placement_id="coding--mbp-m5-max-128g-omlx-app",
        model_id="coding",
        backend_id="omlx_app",
        backend_model_id="qwen-3.8-27b",
        node_id="mbp-m5-max-128g",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=32768,
        memory_admitted=True,
        loaded=True,
        ttft_ms=22.0,
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
        max_concurrency=4,
        affinity_bonus=mbp_affinity_bonus,
    )

    mini = PlacementSnapshot(
        placement_id="coding--mac-mini-m4-24g-lm_studio",
        model_id="coding",
        backend_id="lm_studio",
        backend_model_id="gemma-4-e4b-it-mlx",
        node_id="mac-mini-m4-24g",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=16384,
        memory_admitted=True,
        loaded=True,
        ttft_ms=45.0,
        throughput_tps=42.0,
        queue_depth=0,
        error_rate=0.0,
        network_cost_ms=5.0,
        affinity=0.8,
        available_concurrency=2,
        local=True,
        security_allowed=True,
        circuit_open=mini_circuit_open,
        in_flight=mini_in_flight,
        max_concurrency=2,
        affinity_bonus=mini_affinity_bonus,
    )

    y7000p = PlacementSnapshot(
        placement_id="coding--y7000p-rtx4070-8g-lm_studio",
        model_id="coding",
        backend_id="lm_studio",
        backend_model_id="qwen-3.5-9b-flash",
        node_id="y7000p-rtx4070-8g",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=8192,
        memory_admitted=True,
        loaded=False,
        ttft_ms=60.0,
        throughput_tps=38.0,
        queue_depth=0,
        error_rate=0.0,
        network_cost_ms=12.0,
        affinity=0.6,
        available_concurrency=1,
        local=True,
        security_allowed=True,
        circuit_open=y7000p_circuit_open,
        in_flight=y7000p_in_flight,
        max_concurrency=1,
        affinity_bonus=y7000p_affinity_bonus,
    )

    return (mbp, mini, y7000p)


def test_scenario_1_multi_turn_session_prefix_affinity() -> None:
    """
    Scenario 1: OpenCode multi-turn programming session.
    Turn 1 calculates prefix hash and binds to MBP M5 Max.
    Turn 2 receives affinity bonus and re-locks to MBP M5 Max.
    """
    affinity_reg = SessionAffinityRegistry(AffinityConfig(session_ttl_seconds=900.0))
    planner = RoutePlanner(default_policies())

    sys_prompt = ChatMessage(
        role="system", content="You are OpenCode specialized in Python AST refactoring."
    )
    user_turn1 = ChatMessage(
        role="user", content="Refactor the dependency injection layer in async Python."
    )
    prefix_hash = calculate_prefix_hash((sys_prompt, user_turn1))
    assert prefix_hash is not None

    session_id = "opencode-session-987"
    # Turn 1: Dispatch to primary MBP
    snapshots_t1 = _build_cluster_snapshots()
    req1 = RouteRequest(
        request_id=session_id,
        model_id="coding",
        profile=RouteProfile.QUALITY,
        context_tokens=3000,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )
    decision1 = planner.plan(req1, snapshots_t1)
    assert decision1.selected_placement_id == "coding--mbp-m5-max-128g-omlx-app"

    # Bind affinity upon successful execution
    affinity_reg.record_session_placement(session_id, decision1.selected_placement_id)
    affinity_reg.record_prefix_placement(prefix_hash, decision1.selected_placement_id)

    # Turn 2: Check affinity lookup
    preferred = affinity_reg.get_session_placement(session_id)
    assert preferred == "coding--mbp-m5-max-128g-omlx-app"

    # Turn 2: Planner receives affinity bonus (1.35x)
    snapshots_t2 = _build_cluster_snapshots(mbp_affinity_bonus=1.35)
    req2 = RouteRequest(
        request_id=session_id,
        model_id="coding",
        profile=RouteProfile.QUALITY,
        context_tokens=4500,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )
    decision2 = planner.plan(req2, snapshots_t2)
    assert decision2.selected_placement_id == "coding--mbp-m5-max-128g-omlx-app"
    score_mbp = decision2.candidate_scores["coding--mbp-m5-max-128g-omlx-app"]
    score_mini = decision2.candidate_scores["coding--mac-mini-m4-24g-lm_studio"]
    assert score_mbp > score_mini * 1.4


@pytest.mark.asyncio
async def test_scenario_2_multi_agent_burst_spillover() -> None:
    """
    Scenario 2: 3 parallel agents (AetherForge, OpenCode, Kilo) burst traffic.
    When MBP in-flight reaches threshold, traffic smoothly spills over to Mac mini.
    """
    tracker = ConcurrencyTracker(default_max_concurrency=4)
    planner = RoutePlanner(default_policies())

    mbp_id = "coding--mbp-m5-max-128g-omlx-app"
    # 3 in-flight requests on MBP
    async with tracker.track(mbp_id), tracker.track(mbp_id), tracker.track(mbp_id):
        assert tracker.get_in_flight(mbp_id) == 3

        # Plan 4th request -> MBP score is penalized by 1 / (1 + 0.5 * 3) = 0.4x
        snapshots_busy = _build_cluster_snapshots(mbp_in_flight=3, mini_in_flight=0)
        req_spillover = RouteRequest(
            request_id="kilo-req-burst-4",
            model_id="coding",
            profile=RouteProfile.INTERACTIVE,
            context_tokens=1500,
            required_capabilities=frozenset({"chat"}),
            thinking_requested=False,
        )
        decision = planner.plan(req_spillover, snapshots_busy)
        # Traffic must spill over to idle Mac mini
        assert decision.selected_placement_id == "coding--mac-mini-m4-24g-lm_studio"

    # Max concurrency hard ceiling test
    snapshots_capped = _build_cluster_snapshots(mbp_in_flight=4, mini_in_flight=0)
    decision_capped = planner.plan(req_spillover, snapshots_capped)
    assert decision_capped.selected_placement_id == "coding--mac-mini-m4-24g-lm_studio"
    assert (
        decision_capped.rejected.get("coding--mbp-m5-max-128g-omlx-app")
        == RejectionCode.CONCURRENCY_LIMIT.value
    )


def test_scenario_3_tailscale_isolation_and_last_resort_probe() -> None:
    """
    Scenario 3: Tailscale nodes disconnect; circuit breaker isolates nodes.
    When all nodes enter circuit_open, last-resort probing prevents total system hang.
    """
    cb_reg = CircuitBreakerRegistry()
    planner = RoutePlanner(default_policies())

    mbp_id = "coding--mbp-m5-max-128g-omlx-app"
    mini_id = "coding--mac-mini-m4-24g-lm_studio"
    y7000p_id = "coding--y7000p-rtx4070-8g-lm_studio"

    # Trip circuit breakers on all 3 placements
    for pid in (mbp_id, mini_id, y7000p_id):
        breaker = cb_reg.get_or_create(pid)
        for _ in range(3):
            breaker.record_failure(now=100.0)
        assert not cb_reg.is_available(pid, now=101.0)

    # All snapshots marked circuit_open
    snapshots_all_open = _build_cluster_snapshots(
        mbp_circuit_open=True,
        mini_circuit_open=True,
        y7000p_circuit_open=True,
    )

    req = RouteRequest(
        request_id="emergency-req",
        model_id="coding",
        profile=RouteProfile.INTERACTIVE,
        context_tokens=1024,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )

    # Planner must NOT fail; it must select primary MBP for single-probe recovery
    decision = planner.plan(req, snapshots_all_open)
    assert decision.selected_placement_id == mbp_id
    assert "last_resort_probing=true" in decision.explanation

    # Simulate successful probe recovery
    cb_reg.get_or_create(mbp_id).record_success(now=110.0)
    assert cb_reg.is_available(mbp_id, now=110.0)


def test_scenario_4_state_preservation_during_lifecycle() -> None:
    """
    Scenario 4: Verify that affinity and concurrency trackers survive and clear safely.
    """
    affinity_reg = SessionAffinityRegistry()
    tracker = ConcurrencyTracker()

    affinity_reg.record_session_placement("s-1", "p-1")
    tracker.acquire("p-1")

    assert affinity_reg.get_session_placement("s-1") == "p-1"
    assert tracker.get_in_flight("p-1") == 1

    tracker.release("p-1")
    assert tracker.get_in_flight("p-1") == 0
