"""End-to-end MemoryOS write → recall via shipped service API."""

from mos.backends import InMemorySearchBackend
from mos.service import MemoryOS


def test_write_then_recall_preference_path():
    mos = MemoryOS()
    mos.register_search_backend(
        "kos",
        InMemorySearchBackend(
            name="kos",
            docs=[{"id": "kos1", "title": "unrelated ADR", "snippet": "governance only"}],
        ),
    )
    w = mos.write({"type": "semantic", "content": "user is vegetarian and allergic to nuts", "confidence": 0.9})
    assert w.ok is True
    assert w.dual_track.theta_ok is True
    assert w.dual_track.raw_ok is True

    # preference intent should hit gbrain_facts/theta store
    r = mos.recall("dietary restrictions vegetarian nuts", intent="preference_self")
    assert r.intent == "preference_self"
    assert r.empty is False
    assert any(
        "vegetarian" in (h.get("snippet") or "").lower() or "nuts" in (h.get("snippet") or "").lower() for h in r.hits
    )
    assert r.backend_status.get("gbrain_facts") == "ok" or r.backend_status.get("gbrain") == "ok"


def test_recall_general_fuses_kos_and_gbrain():
    mos = MemoryOS()
    mos.register_search_backend(
        "kos",
        InMemorySearchBackend(
            name="kos",
            docs=[
                {
                    "id": "kos-adr",
                    "title": "ADR-0372 Memory OS",
                    "snippet": "control plane write recall",
                    "path": "decisions/0372.md",
                }
            ],
        ),
    )
    mos.write({"type": "institutional", "content": "Memory OS dual-track architecture notes", "confidence": 0.9})
    r = mos.recall("Memory OS control plane", intent="general")
    assert r.intent == "general"
    assert "kos" in r.backend_status
    # At least one hit from kos or theta/gbrain
    assert r.count >= 1
    backends_seen = {b for h in r.hits for b in (h.get("backends") or [h.get("backend")])}
    assert backends_seen & {"kos", "gbrain", "theta", "gbrain_facts"}


def test_recall_code_structure_does_not_require_kos():
    mos = MemoryOS()
    mos.register_search_backend(
        "codebase_memory",
        InMemorySearchBackend(
            name="codebase_memory",
            docs=[{"id": "fn1", "title": "foo callers", "snippet": "bar calls foo"}],
        ),
    )
    mos.register_search_backend(
        "kos",
        InMemorySearchBackend(
            name="kos",
            docs=[{"id": "noise", "title": "foo poem", "snippet": "foo is a poem about memory"}],
        ),
    )
    r = mos.recall("who calls function foo", intent="code_structure")
    assert r.intent == "code_structure"
    assert "codebase_memory" in r.backend_status
    assert "kos" not in r.backend_status  # not routed
    assert any(h.get("backend") == "codebase_memory" for h in r.hits)


def test_degraded_backend_does_not_crash():
    mos = MemoryOS()
    mos.register_search_backend("kos", InMemorySearchBackend(name="kos", fail=True))
    r = mos.recall("anything", intent="file_note")
    assert r.backend_status["kos"].startswith("degraded")
    assert r.empty is True


def test_status_reports_control_plane():
    mos = MemoryOS()
    st = mos.status()
    assert st["ok"] is True
    assert "bos://memory/mos" in st["control_plane"]
