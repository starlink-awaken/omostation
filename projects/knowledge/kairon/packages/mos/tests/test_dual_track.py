"""Dual-track: theta failure must not erase raw."""

from mos.backends import InMemoryRawBackend, InMemoryThetaBackend
from mos.dual_track import DualTrackWriter
from mos.envelope import validate_envelope


def test_dual_track_writes_raw_and_theta():
    raw = InMemoryRawBackend()
    theta = InMemoryThetaBackend()
    writer = DualTrackWriter(raw, theta)
    env = validate_envelope({"type": "semantic", "content": "allergic to nuts", "confidence": 0.9})
    result = writer.write(env)
    assert result.raw_ok is True
    assert result.theta_ok is True
    assert result.degraded is False
    assert len(raw.events) == 1
    assert raw.events[0]["event_type"] == "memory.write_raw"
    assert any(d.get("id") == env.id for d in theta.docs)


def test_theta_failure_keeps_raw():
    raw = InMemoryRawBackend()
    theta = InMemoryThetaBackend(fail_next=True)
    writer = DualTrackWriter(raw, theta)
    env = validate_envelope({"type": "episodic", "content": "session note", "confidence": 0.9})
    result = writer.write(env)
    assert result.raw_ok is True
    assert result.theta_ok is False
    assert result.degraded is True
    assert len(raw.events) == 1
    assert result.theta_error


def test_low_confidence_skips_theta_keeps_raw():
    raw = InMemoryRawBackend()
    theta = InMemoryThetaBackend()
    writer = DualTrackWriter(raw, theta, confidence_threshold=0.6)
    env = validate_envelope({"type": "working", "content": "temp", "confidence": 0.3})
    result = writer.write(env)
    assert result.raw_ok is True
    assert result.skipped_theta is True
    assert len(theta.docs) == 0
    assert len(raw.events) == 1
