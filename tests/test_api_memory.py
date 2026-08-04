"""Cockpit Memory OS HTTP gateway tests (Phase 5)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_memory_routes_use_injected_invoke():
    from cockpit.web import api_memory

    calls: list[tuple[str, dict]] = []

    def fake(cmd: str, kwargs: dict):
        calls.append((cmd, kwargs))
        if cmd == "status":
            return {"ok": True, "version": "0.5.0"}
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
    finally:
        api_memory.invoke_mos = prev
