"""Phase 4: temporal facts, scope ACL, knowledge_ref (ADR-0315)."""

from mos.routing import classify_intent
from mos.service import MemoryOS


def test_temporal_fact_write_and_current_state_recall():
    mos = MemoryOS()
    w = mos.write(
        {
            "type": "semantic",
            "subject": "Policy-A",
            "predicate": "effective_until",
            "object": "2026-12-31",
            "content": "Policy-A is effective until 2026-12-31",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2026-12-31T23:59:59Z",
            "principal_id": "user-a",
            "confidence": 0.95,
        }
    )
    assert w.ok
    assert w.temporal and w.temporal.get("ok")
    r = mos.recall("Policy-A effective", intent="temporal_fact", scope={"principal_id": "user-a"})
    assert r.count >= 1
    assert any(h.get("backend") == "temporal" for h in r.hits)


def test_temporal_invalidation_hides_current():
    mos = MemoryOS()
    w = mos.write(
        {
            "type": "semantic",
            "subject": "Clause-X",
            "predicate": "status",
            "object": "active",
            "content": "Clause-X is active",
            "confidence": 0.9,
        }
    )
    mid = w.envelope_id
    mos._temporal.invalidate(mid)
    r = mos.recall("Clause-X", intent="temporal_fact")
    # Theta may still hold text; temporal current-state must not surface the edge
    temporal_hits = [h for h in r.hits if h.get("backend") == "temporal"]
    assert all(h.get("id") != mid for h in temporal_hits)


def test_scope_acl_principal_isolation():
    mos = MemoryOS()
    mos.write(
        {
            "type": "semantic",
            "content": "alice secret preference blue widgets",
            "principal_id": "alice",
            "confidence": 0.9,
        }
    )
    mos.write(
        {
            "type": "semantic",
            "content": "bob secret preference red gadgets",
            "principal_id": "bob",
            "confidence": 0.9,
        }
    )
    alice = mos.recall("preference", intent="preference_self", scope={"principal_id": "alice"})
    bob = mos.recall("preference", intent="preference_self", scope={"principal_id": "bob"})
    alice_blob = " ".join(str(h.get("snippet")) for h in alice.hits).lower()
    bob_blob = " ".join(str(h.get("snippet")) for h in bob.hits).lower()
    assert "blue" in alice_blob
    assert "red" not in alice_blob
    assert "red" in bob_blob
    assert "blue" not in bob_blob


def test_knowledge_ref_metadata_only():
    mos = MemoryOS()
    mos.write({"type": "institutional", "content": "ADR-0372 Memory OS control plane", "confidence": 0.9})
    ref = mos.create_knowledge_ref("Memory OS control", intent="general")
    d = ref.to_dict()
    assert d["schema"] == "knowledge-action/v1"
    assert d["query_hash"]
    assert "hit_ids" in d
    # raw audit without body
    types = [e["event_type"] for e in mos.raw_backend.events]
    assert "memory.knowledge_ref" in types
    payload = next(e["payload"] for e in mos.raw_backend.events if e["event_type"] == "memory.knowledge_ref")
    assert "content" not in payload
    assert "ADR-0372" not in str(payload) or "hit_ids" in payload


def test_classify_temporal_intent():
    assert classify_intent("is this policy still effective as of 2026") == "temporal_fact"
    assert classify_intent("条款有效期到什么时候") == "temporal_fact"
