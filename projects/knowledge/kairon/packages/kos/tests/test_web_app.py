"""Tests for KOS FastAPI web app."""

from __future__ import annotations

import importlib
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _load_web_app(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("KOS_HOME", str(tmp_path))
    sys.modules.pop("kos.web.app", None)
    module = importlib.import_module("kos.web.app")
    return importlib.reload(module)


def _init_db(db_path: Path) -> None:
    """Create minimal schema so stats queries don't fail."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS kos_entities (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE IF NOT EXISTS kos_relations (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()


# ── existing tests ────────────────────────────────────────────


def test_health_endpoint_reports_workspace_and_database(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["workspace"]["name"] == "kos-default"
    assert payload["workspace"]["zones"] == 1
    assert payload["database"]["reachable"] is True
    assert payload["database"]["path"] == str(tmp_path / "kos-index.sqlite")


def test_stats_endpoint_reports_uninitialized_database(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    response = client.get("/api/v1/stats")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["data_quality"] == "unavailable"
    assert "documents" in payload["error"]


# ── /api/v1/stats with initialized DB ────────────────────────


def test_stats_endpoint_returns_counts(monkeypatch, tmp_path: Path):
    _init_db(tmp_path / "kos-index.sqlite")
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    response = client.get("/api/v1/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["documents"] == 0
    assert payload["entities"] == 0
    assert payload["relations"] == 0


# ── /api/v1/search ───────────────────────────────────────────


def test_search_returns_results(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_engine = MagicMock()
    mock_engine.search.return_value = {"count": 1, "results": [{"title": "test", "score": 0.9}]}
    mock_engine.close = MagicMock()

    with patch("kos.web.app.HybridSearchEngine", return_value=mock_engine, create=True):
        # Patch the lazy import inside the endpoint
        with patch.dict("sys.modules", {"kos.hybrid_search": MagicMock(HybridSearchEngine=lambda: mock_engine)}):
            response = client.get("/api/v1/search", params={"q": "test query"})

    assert response.status_code == 200
    payload = response.json()
    assert "count" in payload or "results" in payload or "error" in payload


def test_search_handles_engine_error(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_module = MagicMock()
    mock_module.HybridSearchEngine.side_effect = RuntimeError("engine broken")

    with patch.dict("sys.modules", {"kos.hybrid_search": mock_module}):
        response = client.get("/api/v1/search", params={"q": "test"})

    assert response.status_code == 500
    payload = response.json()
    assert "error" in payload


# ── /api/v1/suggest ──────────────────────────────────────────


def test_suggest_returns_list(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_features = MagicMock()
    mock_features.suggest.return_value = ["suggestion1", "suggestion2"]

    with patch.dict("sys.modules", {"kos.search_features": MagicMock(SearchFeatures=lambda: mock_features)}):
        response = client.get("/api/v1/suggest", params={"prefix": "test"})

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list) or "error" in payload


def test_suggest_handles_engine_error(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_module = MagicMock()
    mock_module.SearchFeatures.side_effect = RuntimeError("features broken")

    with patch.dict("sys.modules", {"kos.search_features": mock_module}):
        response = client.get("/api/v1/suggest", params={"prefix": "test"})

    assert response.status_code == 500
    payload = response.json()
    assert "error" in payload


# ── /api/v1/context ──────────────────────────────────────────


def test_context_returns_content(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_engine = MagicMock()
    mock_engine.build_context.return_value = {"context": "some context", "tokens": 100}
    mock_engine.close = MagicMock()

    with patch.dict("sys.modules", {"kos.context_engine": MagicMock(ContextEngine=lambda: mock_engine)}):
        response = client.get("/api/v1/context", params={"q": "test query"})

    assert response.status_code == 200
    payload = response.json()
    assert "context" in payload or "error" in payload


def test_context_handles_engine_error(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_module = MagicMock()
    mock_module.ContextEngine.side_effect = RuntimeError("context broken")

    with patch.dict("sys.modules", {"kos.context_engine": mock_module}):
        response = client.get("/api/v1/context", params={"q": "test"})

    assert response.status_code == 500
    payload = response.json()
    assert "error" in payload


# ── /api/v1/verify ───────────────────────────────────────────


def test_verify_returns_evidence(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_engine = MagicMock()
    mock_engine.search.return_value = {"count": 2, "results": [{"title": "evidence1"}]}
    mock_engine.close = MagicMock()

    with patch.dict("sys.modules", {"kos.hybrid_search": MagicMock(HybridSearchEngine=lambda: mock_engine)}):
        response = client.post("/api/v1/verify", json={"claim": "the sky is blue"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["claim"] == "the sky is blue"
    assert "evidence_count" in payload


def test_verify_handles_missing_claim(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_engine = MagicMock()
    mock_engine.search.return_value = {"count": 0, "results": []}
    mock_engine.close = MagicMock()

    with patch.dict("sys.modules", {"kos.hybrid_search": MagicMock(HybridSearchEngine=lambda: mock_engine)}):
        response = client.post("/api/v1/verify", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["claim"] == ""


# ── /api/v1/clusters ─────────────────────────────────────────


def test_clusters_returns_grouped_results(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_engine = MagicMock()
    mock_engine.search.return_value = {"count": 1, "results": [{"title": "r1"}]}
    mock_engine.close = MagicMock()

    mock_features = MagicMock()
    mock_features.cluster_by_topic.return_value = [{"topic": "general", "items": [{"title": "r1"}]}]

    modules = {
        "kos.hybrid_search": MagicMock(HybridSearchEngine=lambda: mock_engine),
        "kos.search_features": MagicMock(SearchFeatures=lambda: mock_features),
    }
    with patch.dict("sys.modules", modules):
        response = client.get("/api/v1/clusters", params={"q": "test"})

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list) or "error" in payload


# ── /api/v1/health (via KosMonitor) ─────────────────────────


def test_health_v1_returns_monitor_data(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_monitor = MagicMock()
    mock_monitor.index_health.return_value = {"status": "healthy", "index_size": 0}

    with patch.dict("sys.modules", {"kos.monitoring": MagicMock(KosMonitor=lambda: mock_monitor)}):
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload


# ── / (HTML root) ────────────────────────────────────────────


def test_root_returns_html(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "KOS Dashboard" in response.text


# ── /api/search (legacy) ─────────────────────────────────────


def test_legacy_search_returns_empty(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    response = client.get("/api/search", params={"q": "test"})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"results": []}


# ── /api/collab/callback ─────────────────────────────────────


def test_collab_callback_missing_task_id(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    response = client.post("/api/collab/callback", json={"status": "completed"})

    assert response.status_code == 400
    payload = response.json()
    assert "agentmesh_task_id" in payload["error"]


def test_collab_callback_success(monkeypatch, tmp_path: Path):
    web_app = _load_web_app(monkeypatch, tmp_path)
    client = TestClient(web_app.app)

    mock_update = MagicMock(return_value=True)
    with patch.dict("sys.modules", {"kos.collab.api": MagicMock(update_task_by_agentmesh_id=mock_update)}):
        response = client.post(
            "/api/collab/callback",
            json={"agentmesh_task_id": "am-123", "status": "completed", "output": "done"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["updated"] is True
