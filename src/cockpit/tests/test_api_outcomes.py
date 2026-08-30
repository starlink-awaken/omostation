"""Tests for Outcomes & Calibration API endpoints (BET-Y1Q3-T4-07).

Covers the read-only projection layer that surfaces human adjudication
results: pending queue, adjudicated history, per-scene calibration and the
knowledge-to-action funnel.

T4-07 contract points exercised here:
- pending/history split on ``adjudication == "pending"``
- repeated reads are idempotent (replay does not double-count)
- history carries the full lineage needed to trace a durable decision_outcome
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_outcomes


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_outcomes.router)
    return app


def _patch_root(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(api_outcomes, "_workspace_root", lambda: tmp_path)


def _write_scene_outcomes(tmp_path: Path, records: list[dict]) -> Path:
    path = tmp_path / ".omo" / "_knowledge" / "workflow-mesh"
    path.mkdir(parents=True, exist_ok=True)
    target = path / "scene-outcomes.jsonl"
    target.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in records),
        encoding="utf-8",
    )
    return target


def _scene(scene_id: str, adjudication: str, ts: str) -> dict:
    return {
        "scene_id": scene_id,
        "run_id": f"run-{scene_id}",
        "ts": ts,
        "actor": "principal:xiamingxing",
        "adjudication": adjudication,
        "notes": f"notes-{scene_id}",
    }


# --------------------------------------------------------------------------- #
# Summary
# --------------------------------------------------------------------------- #


def test_outcomes_summary_returns_ok_with_zero_counts(monkeypatch, tmp_path):
    """Empty workspace: summary reports zero counts and does not fail."""
    _patch_root(monkeypatch, tmp_path)

    response = TestClient(_app()).get("/api/outcomes")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["pending_count"] == 0
    assert data["history_count"] == 0
    assert data["calibration_scenes"] == 0


def test_outcomes_summary_counts_pending_and_history(monkeypatch, tmp_path):
    """Summary splits records on adjudication == pending."""
    _patch_root(monkeypatch, tmp_path)
    _write_scene_outcomes(
        tmp_path,
        [
            _scene("s1", "pending", "2026-08-30T00:00:00Z"),
            _scene("s2", "adopt", "2026-08-30T01:00:00Z"),
            _scene("s3", "ignore", "2026-08-30T02:00:00Z"),
        ],
    )

    data = TestClient(_app()).get("/api/outcomes").json()

    assert data["pending_count"] == 1
    assert data["history_count"] == 2


def test_outcomes_summary_tolerates_malformed_jsonl(monkeypatch, tmp_path):
    """A corrupt line must not break the projection (fail-soft, not 500)."""
    _patch_root(monkeypatch, tmp_path)
    path = tmp_path / ".omo" / "_knowledge" / "workflow-mesh"
    path.mkdir(parents=True, exist_ok=True)
    (path / "scene-outcomes.jsonl").write_text(
        '{"scene_id": "s1", "adjudication": "pending", "ts": "2026-08-30T00:00:00Z"}\n'
        "not-json-at-all\n"
        "\n",
        encoding="utf-8",
    )

    response = TestClient(_app()).get("/api/outcomes")

    assert response.status_code == 200
    assert response.json()["pending_count"] == 1


# --------------------------------------------------------------------------- #
# Pending queue
# --------------------------------------------------------------------------- #


def test_outcomes_pending_lists_only_pending_adjudications(monkeypatch, tmp_path):
    """Pending endpoint returns only records awaiting human adjudication."""
    _patch_root(monkeypatch, tmp_path)
    _write_scene_outcomes(
        tmp_path,
        [
            _scene("s1", "pending", "2026-08-30T00:00:00Z"),
            _scene("s2", "adopt", "2026-08-30T01:00:00Z"),
        ],
    )

    data = TestClient(_app()).get("/api/outcomes/pending").json()

    assert data["ok"] is True
    assert [r["scene_id"] for r in data["items"]] == ["s1"]


def test_outcomes_pending_sorted_newest_first(monkeypatch, tmp_path):
    """Adjudicators see the oldest-waiting-last / newest first ordering."""
    _patch_root(monkeypatch, tmp_path)
    _write_scene_outcomes(
        tmp_path,
        [
            _scene("old", "pending", "2026-08-01T00:00:00Z"),
            _scene("new", "pending", "2026-08-29T00:00:00Z"),
        ],
    )

    data = TestClient(_app()).get("/api/outcomes/pending").json()

    assert [r["scene_id"] for r in data["items"]] == ["new", "old"]


# --------------------------------------------------------------------------- #
# History & durability
# --------------------------------------------------------------------------- #


def test_outcomes_history_excludes_pending(monkeypatch, tmp_path):
    """Adjudicated records only — pending must not leak into history."""
    _patch_root(monkeypatch, tmp_path)
    _write_scene_outcomes(
        tmp_path,
        [
            _scene("s1", "pending", "2026-08-30T00:00:00Z"),
            _scene("s2", "adopt", "2026-08-30T01:00:00Z"),
            _scene("s3", "edit", "2026-08-30T02:00:00Z"),
        ],
    )

    data = TestClient(_app()).get("/api/outcomes/history").json()

    assert data["ok"] is True
    assert [r["scene_id"] for r in data["items"]] == ["s3", "s2"]


def test_outcomes_history_replay_is_idempotent(monkeypatch, tmp_path):
    """T4-07: replaying the same read must not append or double-count."""
    _patch_root(monkeypatch, tmp_path)
    _write_scene_outcomes(tmp_path, [_scene("s1", "adopt", "2026-08-30T00:00:00Z")])

    client = TestClient(_app())
    first = client.get("/api/outcomes/history").json()
    second = client.get("/api/outcomes/history").json()
    third = client.get("/api/outcomes/history").json()

    assert first == second == third
    assert len(third["items"]) == 1


def test_outcomes_history_preserves_full_lineage(monkeypatch, tmp_path):
    """Each history item carries the fields needed to trace a durable outcome."""
    _patch_root(monkeypatch, tmp_path)
    _write_scene_outcomes(tmp_path, [_scene("s1", "adopt", "2026-08-30T00:00:00Z")])

    item = TestClient(_app()).get("/api/outcomes/history").json()["items"][0]

    for key in ("scene_id", "run_id", "adjudication", "actor", "adjudicated_at", "notes"):
        assert key in item
    assert item["adjudication"] == "adopt"
    assert item["run_id"] == "run-s1"


def test_outcomes_history_limit_is_enforced(monkeypatch, tmp_path):
    """limit is bounded by the endpoint contract (1..500)."""
    _patch_root(monkeypatch, tmp_path)
    _write_scene_outcomes(
        tmp_path,
        [_scene(f"s{i}", "adopt", f"2026-08-30T{i:02d}:00:00Z") for i in range(5)],
    )

    client = TestClient(_app())
    assert len(client.get("/api/outcomes/history?limit=2").json()["items"]) == 2
    assert client.get("/api/outcomes/history?limit=0").status_code == 422
    assert client.get("/api/outcomes/history?limit=501").status_code == 422


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


def test_outcomes_calibration_projects_scenes_and_capabilities(monkeypatch, tmp_path):
    """Calibration reads both the summary rollup and per-capability beliefs."""
    _patch_root(monkeypatch, tmp_path)

    summary_path = tmp_path / ".omo" / "_delivery" / "outcomes"
    summary_path.mkdir(parents=True, exist_ok=True)
    (summary_path / "capability_calibration_summary.yaml").write_text(
        yaml.safe_dump(
            {
                "scene-alpha": {
                    "accepted": 3,
                    "total": 4,
                    "calibration": 0.75,
                    "updated_at": "2026-08-30T00:00:00Z",
                }
            }
        ),
        encoding="utf-8",
    )

    beliefs_path = tmp_path / ".omo" / "state" / "agent-beliefs"
    beliefs_path.mkdir(parents=True, exist_ok=True)
    (beliefs_path / "index.yaml").write_text(
        yaml.safe_dump(
            {
                "capability_calibrations": [
                    {
                        "id": "cap-1",
                        "capability_ref": "capability:doc-draft",
                        "success_rate": 0.8,
                        "sample_size": 10,
                        "measured_at": "2026-08-30T00:00:00Z",
                    }
                ],
                "decision_outcomes": [{"scene_id": "scene-alpha", "verdict": "adopt"}],
            }
        ),
        encoding="utf-8",
    )

    data = TestClient(_app()).get("/api/outcomes/calibration").json()

    assert data["ok"] is True
    assert len(data["scenes"]) == 1
    assert data["scenes"][0]["scene_id"] == "scene-alpha"
    assert data["scenes"][0]["calibration"] == 0.75
    assert len(data["capabilities"]) == 1
    assert data["capabilities"][0]["capability_ref"] == "capability:doc-draft"


def test_outcomes_calibration_empty_when_absent(monkeypatch, tmp_path):
    """Missing calibration files degrade to empty lists, never 500."""
    _patch_root(monkeypatch, tmp_path)

    data = TestClient(_app()).get("/api/outcomes/calibration").json()

    assert data["ok"] is True
    assert data["scenes"] == []
    assert data["capabilities"] == []


# --------------------------------------------------------------------------- #
# Knowledge funnel
# --------------------------------------------------------------------------- #


def test_outcomes_knowledge_funnel_endpoint_returns_ok(monkeypatch, tmp_path):
    """Funnel endpoint flattens the funnel payload into the response body."""
    _patch_root(monkeypatch, tmp_path)
    monkeypatch.setattr(
        api_outcomes,
        "_read_knowledge_funnel",
        lambda root: {
            "retrieved": 10,
            "cited": 5,
            "citation_rate": 0.5,
            "task_created": 2,
            "status": "ok",
        },
    )

    data = TestClient(_app()).get("/api/outcomes/knowledge-funnel").json()

    assert data["ok"] is True
    assert data["citation_rate"] == 0.5
    assert data["task_created"] == 2


def test_outcomes_knowledge_funnel_degrades_when_unavailable(monkeypatch, tmp_path):
    """Unavailable funnel surfaces a safe zeroed payload rather than failing."""
    _patch_root(monkeypatch, tmp_path)
    monkeypatch.setattr(
        api_outcomes,
        "_read_knowledge_funnel",
        lambda root: {
            "retrieved": 0,
            "cited": 0,
            "citation_rate": None,
            "task_created": 0,
            "status": "unavailable",
        },
    )

    data = TestClient(_app()).get("/api/outcomes/knowledge-funnel").json()

    assert data["ok"] is True
    assert data["citation_rate"] is None
    assert data["status"] == "unavailable"
