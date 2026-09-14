"""Phase 5: fine ACL + graphiti bridge status."""

from mos.acl import filter_hits, hit_allowed
from mos.adapters.graphiti_bridge import backend_status, build_temporal_backend
from mos.service import MemoryOS


def test_acl_agent_profile_and_scene():
    hits = [
        {"id": "1", "principal_id": "u1", "agent_profile": "claude", "scene_id": "s1"},
        {"id": "2", "principal_id": "u1", "agent_profile": "codex", "scene_id": "s1"},
        {"id": "3", "principal_id": "u1", "agent_profile": "claude", "scene_id": "s2"},
        {"id": "4"},  # public
    ]
    scope = {"principal_id": "u1", "agent_profile": "claude", "scene_id": "s1"}
    out = filter_hits(hits, scope)
    ids = {h["id"] for h in out}
    assert ids == {"1", "4"}
    assert hit_allowed(hits[1], scope) is False


def test_graphiti_bridge_degrades_to_temporal(monkeypatch):
    monkeypatch.delenv("MOS_GRAPHITI", raising=False)
    b = build_temporal_backend()
    assert b.name in {"temporal", "graphiti_shadow"}
    st = backend_status()
    assert "graphiti_flag" in st


def test_write_propagates_agent_profile_acl():
    mos = MemoryOS()
    mos.write(
        {
            "type": "semantic",
            "content": "claude-only note about widgets",
            "principal_id": "u1",
            "agent_profile": "claude",
            "scene_id": "home",
            "confidence": 0.9,
        }
    )
    ok = mos.recall(
        "widgets",
        intent="preference_self",
        scope={"principal_id": "u1", "agent_profile": "claude", "scene_id": "home"},
    )
    bad = mos.recall(
        "widgets",
        intent="preference_self",
        scope={"principal_id": "u1", "agent_profile": "codex", "scene_id": "home"},
    )
    assert ok.count >= 1
    assert bad.count == 0 or all("widgets" not in str(h.get("snippet")).lower() for h in bad.hits)
