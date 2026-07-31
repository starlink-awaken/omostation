"""Tests for the Cockpit KEMS workbench API boundary."""

import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_kems


def client():
    app = FastAPI()
    app.include_router(api_kems.router)
    return TestClient(app)


def test_kems_status_is_review_only_and_contains_no_private_content():
    result = client().get("/api/kems/status")
    assert result.status_code == 200
    assert result.json()["mode"] == "review_only"
    assert result.json()["dispatch"] == "omo_only"


def test_kems_draft_requires_evidence():
    result = client().post(
        "/api/kems/tasks/draft",
        json={
            "task_id": "task-1",
            "source_run_id": "run-1",
            "title": "x",
            "owner": "y",
            "due_at": "tomorrow",
            "acceptance_criteria": "done",
            "evidence_refs": [],
        },
    )
    assert result.status_code == 422


def test_kems_draft_calls_omo_ingress(monkeypatch):
    seen = {}

    def fake_ingress(omo_dir, *, task_payload, source_ref, now=None):
        seen.update(task_payload=task_payload, source_ref=source_ref)
        return {"id": task_payload["id"], "status": "candidate"}

    fake_module = types.ModuleType("omo.omo_ingress_kems")
    fake_module.create_kems_planned_task = fake_ingress
    monkeypatch.setitem(sys.modules, "omo.omo_ingress_kems", fake_module)
    result = client().post(
        "/api/kems/tasks/draft",
        json={
            "task_id": "task-1",
            "source_run_id": "run-1",
            "title": "x",
            "owner": "y",
            "due_at": "tomorrow",
            "acceptance_criteria": "done",
            "evidence_refs": ["doc-1#page=1"],
        },
    )
    assert result.status_code == 200
    assert seen["source_ref"] == "kems:run-1:task-1"
    assert seen["task_payload"]["assigned_to"] is None
