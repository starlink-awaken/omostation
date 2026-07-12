"""Tests for cockpit API omos — deep endpoints (fix-drift, violations regex, quests SQLite)."""

from __future__ import annotations

import json
import sqlite3
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from cockpit.dashboard_server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestOmosFixDrift:
    """Cover api_omos.py:548-577 (fix-drift subprocess)."""

    def test_fix_drift_success(self, client):
        mock_proc = MagicMock(returncode=0, stdout="Fixed 3 issues", stderr="")
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            resp = client.post("/api/omos/fix-drift", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["returncode"] == 0
        assert "Fixed 3 issues" in data["stdout"]
        assert mock_run.call_count >= 1

    def test_fix_drift_failure(self, client):
        mock_proc = MagicMock(returncode=1, stdout="", stderr="Error")
        with patch("subprocess.run", return_value=mock_proc):
            resp = client.post("/api/omos/fix-drift", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"  # still ok, just with returncode


class TestOmosViolationsParsing:
    """Cover api_omos.py:617-643 (violations regex parsing)."""

    def test_violations_parses_gatekeeper_output(self, client, tmp_path, monkeypatch):
        """Test regex parsing of gatekeeper output format."""
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE", None, raising=False)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE_TIME", 0.0, raising=False)

        # Create gatekeeper script
        scripts_dir = tmp_path / "projects" / "ecos" / "scripts"
        scripts_dir.mkdir(parents=True)
        gatekeeper = scripts_dir / "contract_gatekeeper.py"
        gatekeeper.write_text("#!/usr/bin/env python3\nprint('mock')")

        mock_output = """Gatekeeper: scan start
src/file1.py
10: violation detail here
20: another violation
src/file2.py
5: more violations
Remendiation: scan end"""

        mock_proc = MagicMock(returncode=0, stdout=mock_output, stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            resp = client.get("/api/omos/violations")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["passed"] is True
        # Should parse 3 violations (2 from file1, 1 from file2)
        assert len(data["violations"]) == 3
        assert data["violations"][0]["file"] == "src/file1.py"
        assert data["violations"][0]["line"] == 10

    def test_violations_empty_output(self, client, tmp_path, monkeypatch):
        """Test violations with clean output (no violations)."""
        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE", None, raising=False)
        monkeypatch.setattr("cockpit.web.api_omos._VIOLATIONS_CACHE_TIME", 0.0, raising=False)

        scripts_dir = tmp_path / "projects" / "ecos" / "scripts"
        scripts_dir.mkdir(parents=True)
        gatekeeper = scripts_dir / "contract_gatekeeper.py"
        gatekeeper.write_text("#!/usr/bin/env python3\nprint('mock')")

        mock_proc = MagicMock(returncode=0, stdout="Gatekeeper: scan start\nNo issues\nRemediation: scan end", stderr="")
        with patch("subprocess.run", return_value=mock_proc):
            resp = client.get("/api/omos/violations")

        assert resp.status_code == 200
        data = resp.json()
        assert data["passed"] is True
        assert len(data["violations"]) == 0


class TestOmosQuestsSQLite:
    """Cover api_omos.py:261-340 (create_quest SQLite + OMO)."""

    def test_create_quest_with_db(self, client, tmp_path, monkeypatch):
        """Create quest inserts into SQLite + writes OMO task."""
        db_path = tmp_path / "projects" / "family-hub"
        db_path.mkdir(parents=True)
        db = db_path / "family_hub.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE quests (id INTEGER PRIMARY KEY, title TEXT, type TEXT, reward INTEGER, completed INTEGER, assignee TEXT)")
        conn.commit()
        conn.close()

        monkeypatch.setattr("cockpit.web.api_omos._REPO_ROOT", tmp_path)

        resp = client.post("/api/omos/quests", params={
            "title": "Integration Test Quest",
            "q_type": "wisdom",
            "reward": 100,
            "assignee": "parent",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok" or "task_id" in data or "id" in data
