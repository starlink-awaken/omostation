"""Forget propagation: raw audit + theta hide + optional mem0."""

from mos.service import MemoryOS


def test_forget_hides_from_recall():
    mos = MemoryOS()
    w = mos.write({"type": "semantic", "content": "forget-me-unique-token-xyz", "confidence": 0.9})
    assert w.ok
    mid = w.envelope_id
    r1 = mos.recall("forget-me-unique-token-xyz", intent="preference_self")
    assert r1.count >= 1
    fr = mos.forget(mid, reason="test")
    assert fr.ok and fr.dual_track.raw_ok and fr.dual_track.theta_ok
    r2 = mos.recall("forget-me-unique-token-xyz", intent="preference_self")
    assert all(h.get("id") != mid for h in r2.hits)
    # raw still has forget event
    types = [e["event_type"] for e in mos.raw_backend.events]
    assert "memory.forget" in types


def test_forget_idempotent():
    mos = MemoryOS()
    w = mos.write({"type": "episodic", "content": "twice forget", "confidence": 0.9})
    mos.forget(w.envelope_id)
    fr2 = mos.forget(w.envelope_id)
    assert fr2.ok
