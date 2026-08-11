"""Public-boundary tests for the read-only W2-04 episode projection endpoint.

The endpoint lives on the existing ``/api/workflow-mesh`` router as
``GET /episode-projections``.  It only resolves the existing Event Ledger
database path and delegates to OMO's
``omo.episode_projection.build_episode_projection_snapshot_from_path``; it
must never append, write scene cards, approve, execute, or reach out.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_workflow_mesh_operations


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    return app


def _seed_event_ledger(root: Path) -> Path:
    """Create an existing (valid) Event Ledger SQLite file under ``root``."""
    db_path = root / "runtime" / "omo" / "event-ledger.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(str(db_path)).close()
    return db_path


def test_episode_projections_api_returns_read_only_projection(monkeypatch, tmp_path):
    projection = {
        "schema_version": "episode-projections/v1",
        "status": "live",
        "principal_id": "principal://alice",
        "episodes": [
            {
                "episode_id": "ep_001",
                "name": "Review and merge docs PR",
                "status": "active",
                "event_count": 4,
            }
        ],
    }
    calls: list[tuple[Path, str]] = []

    def fake_build(db_path, *, principal_id):
        calls.append((Path(db_path), principal_id))
        return projection

    db_path = _seed_event_ledger(tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "build_episode_projection_snapshot_from_path", fake_build)

    response = TestClient(_make_app()).get(
        "/api/workflow-mesh/episode-projections?principal_id=principal://alice"
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "status": "live",
        "schema": "episode-projections/v1",
        "principal_id": "principal://alice",
        "projection": projection,
        "read_only": True,
        "workflow_state_mutation": False,
        "provider_invocation": False,
        "automatic_promotion": False,
    }
    # The endpoint forwards the resolved Event Ledger path and the principal.
    assert calls == [(db_path, "principal://alice")]


def test_episode_projections_api_requires_principal_id():
    response = TestClient(_make_app()).get("/api/workflow-mesh/episode-projections")

    assert response.status_code == 422


def test_episode_projections_api_degrades_without_omo(monkeypatch, tmp_path):
    _seed_event_ledger(tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "build_episode_projection_snapshot_from_path", None)
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "_EPISODE_PROJECTION_IMPORT_ERROR",
        ImportError("missing omo.episode_projection"),
    )

    response = TestClient(_make_app()).get(
        "/api/workflow-mesh/episode-projections?principal_id=principal://alice"
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "unavailable"
    assert response.json()["error"] == "episode_projection_unavailable"
    assert response.json()["read_only"] is True


def test_episode_projections_api_reports_missing_ledger_without_calling_omo(monkeypatch, tmp_path):
    called = False

    def unexpected_build(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("OMO projection must not be called for a missing ledger")

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "build_episode_projection_snapshot_from_path", unexpected_build)

    response = TestClient(_make_app()).get(
        "/api/workflow-mesh/episode-projections?principal_id=principal://alice"
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "unavailable"
    assert response.json()["error"] == "episode_projection_ledger_missing"
    assert response.json()["db_path"] == str(tmp_path / "runtime" / "omo" / "event-ledger.sqlite3")
    assert called is False


def test_episode_projections_api_reports_projection_failure(monkeypatch, tmp_path):
    def fail_build(_db_path, *, principal_id):
        raise ValueError("episode snapshot is not rebuildable from this ledger")

    _seed_event_ledger(tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "build_episode_projection_snapshot_from_path", fail_build)

    response = TestClient(_make_app()).get(
        "/api/workflow-mesh/episode-projections?principal_id=principal://alice"
    )

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "unavailable"
    assert response.json()["error"] == "episode_projection_failed"
    assert response.json()["read_only"] is True


def test_episode_projections_api_honors_event_ledger_db_env_override(monkeypatch, tmp_path):
    calls: list[tuple[Path, str]] = []
    ledger_path = _seed_event_ledger(tmp_path / "elsewhere")

    def fake_build(db_path, *, principal_id):
        calls.append((Path(db_path), principal_id))
        return {"schema_version": "episode-projections/v1", "status": "live", "principal_id": principal_id}

    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "build_episode_projection_snapshot_from_path", fake_build)
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(ledger_path))

    response = TestClient(_make_app()).get(
        "/api/workflow-mesh/episode-projections?principal_id=principal://alice"
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert calls == [(ledger_path, "principal://alice")]


def test_episode_projections_api_is_get_only(monkeypatch, tmp_path):
    _seed_event_ledger(tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "build_episode_projection_snapshot_from_path", lambda *a, **k: {})

    client = TestClient(_make_app())

    post_response = client.post("/api/workflow-mesh/episode-projections", json={"principal_id": "principal://alice"})
    assert post_response.status_code == 405

    put_response = client.put("/api/workflow-mesh/episode-projections", json={"principal_id": "principal://alice"})
    assert put_response.status_code == 405
