"""
Unit tests for SessionAffinityRegistry and calculate_prefix_hash.
"""

from __future__ import annotations

from omlxc.dataplane.affinity import (
    AffinityConfig,
    SessionAffinityRegistry,
    calculate_prefix_hash,
)
from omlxc.domain.protocols import ChatMessage


def test_session_affinity_binding_and_ttl() -> None:
    config = AffinityConfig(session_ttl_seconds=10.0, max_sessions=2)
    reg = SessionAffinityRegistry(config)

    # Initially empty
    assert reg.get_session_placement("sess-1", now=100.0) is None

    # Record affinity
    reg.record_session_placement("sess-1", "p-mbp", now=100.0)
    assert reg.get_session_placement("sess-1", now=105.0) == "p-mbp"

    # Expired after TTL
    assert reg.get_session_placement("sess-1", now=111.0) is None


def test_session_affinity_lru_eviction() -> None:
    config = AffinityConfig(session_ttl_seconds=100.0, max_sessions=2)
    reg = SessionAffinityRegistry(config)

    reg.record_session_placement("sess-1", "p-1", now=10.0)
    reg.record_session_placement("sess-2", "p-2", now=11.0)

    # Touch sess-1
    assert reg.get_session_placement("sess-1", now=12.0) == "p-1"

    # Insert sess-3 -> should evict sess-2 (since sess-1 was touched recently)
    reg.record_session_placement("sess-3", "p-3", now=13.0)

    assert reg.get_session_placement("sess-1", now=14.0) == "p-1"
    assert reg.get_session_placement("sess-2", now=14.0) is None
    assert reg.get_session_placement("sess-3", now=14.0) == "p-3"


def test_prefix_hash_calculation_and_affinity() -> None:
    reg = SessionAffinityRegistry()

    msgs = (
        ChatMessage(role="system", content="You are a helpful coding assistant."),
        ChatMessage(role="user", content="Write a python script."),
    )
    p_hash = calculate_prefix_hash(msgs)
    assert p_hash is not None
    assert len(p_hash) == 16

    reg.record_prefix_placement(p_hash, "p-mac-mini", now=50.0)
    assert reg.get_prefix_placement(p_hash, now=60.0) == "p-mac-mini"

    # Empty messages return None
    assert calculate_prefix_hash(()) is None
