"""Cockpit Memory OS HTTP gateway tests (Phase 5–6)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_memory_routes_use_injected_invoke():
    from cockpit.web import api_memory

    calls: list[tuple[str, dict]] = []

    def fake(cmd: str, kwargs: dict):
        calls.append((cmd, kwargs))
        if kwargs.get("role") == "guest" and cmd == "write":
            return {"ok": False, "error": "rbac_denied", "detail": "role=guest denied action=write"}
        if cmd == "status":
            return {"ok": True, "version": "0.6.0"}
        if cmd == "write":
            return {"ok": True, "envelope_id": "mem_x"}
        if cmd == "recall":
            return {"ok": True, "hits": [], "count": 0, "empty": True, "intent": "general"}
        if cmd == "knowledge-ref":
            return {"ref_id": "kref_1", "hit_ids": [], "schema": "knowledge-action/v1"}
        return {"ok": True}

    prev = api_memory.invoke_mos
    api_memory.invoke_mos = fake
    try:
        app = FastAPI()
        app.include_router(api_memory.router)
        client = TestClient(app)
        assert client.get("/api/memory/status").json()["ok"] is True
        assert client.post("/api/memory/write", json={"type": "semantic", "content": "x"}).json()["ok"]
        rec = client.post(
            "/api/memory/recall",
            json={"query": "x", "principal_id": "u1", "agent_profile": "claude"},
        ).json()
        assert rec["empty"] is True
        # scope folded
        assert calls[-1][0] == "recall"
        assert calls[-1][1].get("scope", {}).get("principal_id") == "u1"
        kref = client.post("/api/memory/knowledge-ref", json={"query": "x"}).json()
        assert kref["schema"] == "knowledge-action/v1"
        # Phase 6: header RBAC injection
        denied = client.post(
            "/api/memory/write",
            json={"type": "semantic", "content": "nope"},
            headers={"X-Mos-Role": "guest"},
        )
        assert denied.status_code == 403
        assert denied.json()["error"] == "rbac_denied"
        assert any(c[0] == "write" and c[1].get("role") == "guest" for c in calls)
    finally:
        api_memory.invoke_mos = prev


def test_memory_dashboard_html_exported():
    from cockpit.dashboard.constants import MEMORY_DASHBOARD_HTML

    assert "Memory OS" in MEMORY_DASHBOARD_HTML
    assert "/api/memory/status" in MEMORY_DASHBOARD_HTML
