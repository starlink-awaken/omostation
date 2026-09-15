"""Mem0 shadow adapter — default off; on without Qdrant."""

from mos.adapters.mem0_shadow import mem0_enabled
from mos.service import MemoryOS


def test_mem0_default_off(monkeypatch):
    monkeypatch.delenv("MOS_MEM0", raising=False)
    assert mem0_enabled() is False
    mos = MemoryOS()
    w = mos.write({"type": "semantic", "content": "prefers tea", "confidence": 0.9})
    assert w.mem0 is None or w.mem0.get("skipped") or not w.mem0.get("ok")


def test_mem0_on_dual_writes(monkeypatch):
    monkeypatch.setenv("MOS_MEM0", "1")
    assert mem0_enabled() is True
    mos = MemoryOS()
    w = mos.write({"type": "semantic", "content": "prefers oolong tea", "confidence": 0.95})
    assert w.ok
    assert w.mem0 and w.mem0.get("ok") is True
    r = mos.recall("oolong tea", intent="preference_self")
    # theta and/or mem0 should hit
    assert r.count >= 1
    backends = {b for h in r.hits for b in (h.get("backends") or [h.get("backend")])}
    assert backends & {"gbrain_facts", "gbrain", "mem0", "theta"}
