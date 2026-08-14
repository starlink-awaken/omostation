"""Public-boundary tests for the read-only W2-04 episode projection endpoint.

The endpoint lives on the existing ``/api/workflow-mesh`` router as
``GET /episode-projections``.  It only resolves the existing Event Ledger
database path and delegates to OMO's
``omo.episode_projection.build_episode_projection_snapshot_from_path``; it
must never append, write scene cards, approve, execute, or reach out.
"""

from __future__ import annotations

import json
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

    response = TestClient(_make_app()).get("/api/workflow-mesh/episode-projections?principal_id=principal://alice")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "status": "live",
        "schema": "episode-projections/v1",
        "principal_id": "principal://alice",
        "projection": {
            **projection,
            "episodes": [{**projection["episodes"][0], "contains_event_refs": []}],
            "role_portfolio": {
                "active_assignments": [],
                "responsibilities": [],
                "episode_counts": {},
            },
            "inbox": [],
            "blocked": [],
            "controls": {"chain_before": {}, "chain_after": {}},
        },
        "read_only": True,
        "workflow_state_mutation": False,
        "provider_invocation": False,
        "automatic_promotion": False,
    }
    # The endpoint forwards the resolved Event Ledger path and the principal.
    assert calls == [(db_path, "principal://alice")]


def test_episode_projections_api_returns_privacy_safe_http_dto(monkeypatch, tmp_path):
    projection = {
        "schema_version": "episode-projection/v1",
        "status": "live",
        "principal_id": "principal://alice",
        "episodes": [
            {
                "episode_id": "episode:001",
                "schema_version": "episode/v1",
                "opened_at": "2026-08-13T00:00:00Z",
                "contains_event_refs": [
                    {
                        "event_id": "event:outcome",
                        "schema_version": "event-envelope/v1",
                        "source_ref": "/Users/alice/private/producer.py",
                        "emitted_at": "2026-08-13T00:01:00Z",
                        "payload": {
                            "episode_id": "episode:001",
                            "feedback_id": "feedback:001",
                            "verdict": "accept",
                            "review_duration_seconds": 15,
                            "estimated_time_saved_seconds": 90,
                            "evidence_uri": "file:///Users/alice/private/draft.json",
                            "source_uri": "iris://local-files/private-note",
                            "raw_payload": {"secret": "family note"},
                            "context": "private draft body",
                        },
                    }
                ],
            }
        ],
        "role_portfolio": {
            "principal_id": "principal://alice",
            "active_assignments": [{"role_id": "role:steward", "status": "active"}],
            "responsibilities": [{"responsibility_id": "responsibility:follow-up"}],
            "episode_counts": {"episode:001": 1},
        },
        "inbox": [
            {
                "card_type": "decision",
                "episode": "episode:001",
                "principal": "principal://alice",
                "role": "role:steward",
                "responsibility": "responsibility:follow-up",
                "request": "request:001",
                "summary": "Review follow-up",
                "why_now": "Due today",
                "deadline": "2026-08-13",
                "status": "pending",
                "confidence": "high",
                "source_uri": "file:///Users/alice/private/note.md",
            }
        ],
        "blocked": [],
        "controls": {
            "events_read": 1,
            "events_ignored": 0,
            "events_blocked": 0,
            "ledger_count_before": 1,
            "ledger_count_after": 1,
            "ledger_unchanged": True,
            "chain_before": {"ok": True, "total": 1},
            "chain_after": {"ok": True, "total": 1},
        },
    }
    _seed_event_ledger(tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        api_workflow_mesh_operations,
        "build_episode_projection_snapshot_from_path",
        lambda *_args, **_kwargs: projection,
    )

    response = TestClient(_make_app()).get("/api/workflow-mesh/episode-projections?principal_id=principal://alice")

    assert response.status_code == 200
    dto = response.json()["projection"]
    serialized = json.dumps(dto)
    assert "file://" not in serialized
    assert "/Users/alice" not in serialized
    assert "iris://" not in serialized
    assert "raw_payload" not in serialized
    assert "private draft body" not in serialized
    assert dto["episodes"][0]["episode_id"] == "episode:001"
    assert dto["episodes"][0]["contains_event_refs"][0]["payload"] == {
        "episode_id": "episode:001",
        "feedback_id": "feedback:001",
        "verdict": "accept",
        "review_duration_seconds": 15,
        "estimated_time_saved_seconds": 90,
    }
    assert dto["inbox"][0]["summary"] == "Review follow-up"
    assert dto["role_portfolio"]["active_assignments"][0]["role_id"] == "role:steward"


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

    response = TestClient(_make_app()).get("/api/workflow-mesh/episode-projections?principal_id=principal://alice")

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

    response = TestClient(_make_app()).get("/api/workflow-mesh/episode-projections?principal_id=principal://alice")

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["status"] == "unavailable"
    assert response.json()["error"] == "episode_projection_ledger_missing"
    assert "db_path" not in response.json()
    assert str(tmp_path) not in json.dumps(response.json())
    assert called is False


def test_episode_projections_api_reports_projection_failure(monkeypatch, tmp_path):
    def fail_build(_db_path, *, principal_id):
        raise ValueError("episode snapshot is not rebuildable from this ledger")

    _seed_event_ledger(tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_workflow_mesh_operations, "build_episode_projection_snapshot_from_path", fail_build)

    response = TestClient(_make_app()).get("/api/workflow-mesh/episode-projections?principal_id=principal://alice")

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

    response = TestClient(_make_app()).get("/api/workflow-mesh/episode-projections?principal_id=principal://alice")

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
