"""Standalone CI coverage for personal feedback public boundaries."""

from __future__ import annotations

import argparse
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.commands import workflow_mesh
from cockpit.web import api_workflow_mesh_operations


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_workflow_mesh_operations.router)  # type: ignore[arg-type]
    return app


def test_feedback_http_threads_optional_id_and_rejects_blank(monkeypatch):
    calls: list[tuple[str, dict[str, object]]] = []
    sequences: dict[str, int] = {}

    class FakeService:
        def reload_execution_context(self, episode_id: str, principal_id: str) -> object:
            assert episode_id == "episode:test"
            assert principal_id == "principal:alice"
            return object()

        def record_outcome(self, _context: object, verdict: str, **kwargs: object) -> int:
            calls.append((verdict, kwargs))
            identity = str(kwargs.get("feedback_id") or f"legacy:{verdict}")
            return sequences.setdefault(identity, len(sequences) + 1)

    @contextmanager
    def fake_service():
        yield FakeService()

    monkeypatch.setattr(api_workflow_mesh_operations, "PersonalEpisodeService", FakeService)
    monkeypatch.setattr(api_workflow_mesh_operations, "_personal_episode_service", fake_service)
    client = TestClient(_app())
    base = {
        "episode_id": "episode:test",
        "principal_id": "principal:alice",
        "verdict": "accept",
    }

    first = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={**base, "feedback_id": "feedback:001"},
    )
    replay = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={**base, "feedback_id": "feedback:001"},
    )
    legacy = client.post("/api/workflow-mesh/personal-episode/feedback", json=base)
    invalid = client.post(
        "/api/workflow-mesh/personal-episode/feedback",
        json={**base, "feedback_id": "   "},
    )

    assert first.status_code == replay.status_code == legacy.status_code == 200
    assert replay.json()["sequence"] == first.json()["sequence"]
    assert invalid.status_code == 409
    assert calls == [
        (
            "accept",
            {
                "feedback_id": "feedback:001",
                "review_duration_seconds": None,
                "estimated_time_saved_seconds": None,
            },
        ),
        (
            "accept",
            {
                "feedback_id": "feedback:001",
                "review_duration_seconds": None,
                "estimated_time_saved_seconds": None,
            },
        ),
        (
            "accept",
            {
                "feedback_id": None,
                "review_duration_seconds": None,
                "estimated_time_saved_seconds": None,
            },
        ),
    ]


def test_feedback_cli_threads_optional_id_and_preserves_legacy(monkeypatch):
    payloads: list[dict[str, object]] = []

    def fake_post(_path: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        payloads.append(payload)
        return 200, {"ok": True, "status": "recorded", "sequence": len(payloads)}

    monkeypatch.setattr(workflow_mesh, "_api_post", fake_post)

    with_id = workflow_mesh.cmd_personal(
        argparse.Namespace(
            personal_command="feedback",
            rest=[
                "--episode-id",
                "episode:test",
                "--feedback-id",
                "feedback:cli-001",
                "--verdict",
                "accept",
            ],
        )
    )
    legacy = workflow_mesh.cmd_personal(
        argparse.Namespace(
            personal_command="feedback",
            rest=["--episode-id", "episode:test", "--verdict", "accept"],
        )
    )

    assert with_id == legacy == 0
    assert payloads[0]["feedback_id"] == "feedback:cli-001"
    assert "feedback_id" not in payloads[1]
