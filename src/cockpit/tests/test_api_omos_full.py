"""Tests for cockpit API omos — error paths and simple endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestOmosQuests:
    def test_get_quests_with_db(self, client, tmp_path, monkeypatch):
        import sqlite3
        db_path = tmp_path / "projects" / "family-hub"
        db_path.mkdir(parents=True)
        db = db_path / "family_hub.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE quests (id INTEGER, title TEXT)")
        conn.execute("INSERT INTO quests VALUES (1, 'Test')")
        conn.execute("CREATE TABLE profiles (role TEXT, name TEXT, level INTEGER, wisdomPoints INTEGER, responsibilityPoints INTEGER, inventory TEXT)")
        conn.execute("CREATE TABLE logs (id INTEGER, message TEXT, timestamp TEXT)")
        conn.commit()
        conn.close()
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)
        resp = client.get("/api/omos/quests")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestOmosThoughts:
    def test_get_thoughts(self, client):
        resp = client.get("/api/omos/thoughts")
        assert resp.status_code == 200


class TestOmosViolations:
    def test_get_violations_cached(self, client, monkeypatch):
        cached = {"status": "ok", "passed": True, "violations": []}
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE", cached, raising=False)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE_TIME", __import__("time").time(), raising=False)
        resp = client.get("/api/omos/violations")
        assert resp.status_code == 200
        assert resp.json() == cached


class TestOmosGovernance:
    def test_circuit_break(self, client):
        with patch("cockpit.adapters.omo.update_provider_plane_settings", return_value={"status": "ok"}):
            resp = client.post("/api/omos/circuit-break", json={"broken": True})
        assert resp.status_code == 200

    def test_budget(self, client):
        with patch("cockpit.adapters.omo.update_provider_plane_settings", return_value={"status": "ok"}):
            resp = client.post("/api/omos/budget", json={"amount": 100})
        assert resp.status_code == 200
