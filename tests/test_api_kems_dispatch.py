import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_kems


def client():
    app = FastAPI()
    app.include_router(api_kems.router)
    return TestClient(app)


def test_dispatch_requires_worker_and_write_scope():
    result = client().post("/api/kems/tasks/task-1/dispatch", json={"worker_id": "worker-1"})
    assert result.status_code == 422


def test_dispatch_rejects_private_content():
    result = client().post(
        "/api/kems/tasks/task-1/dispatch",
        json={
            "worker_id": "worker-1",
            "allowed_write_paths": ["projects/kairon"],
            "raw_text": "private source",
        },
    )
    assert result.status_code == 422


def test_dispatch_calls_omo_broker(monkeypatch):
    seen = {}

    def fake_dispatch(root, task_id, worker_id, allowed_write_paths, **kwargs):
        seen.update(
            root=root,
            task_id=task_id,
            worker_id=worker_id,
            allowed_write_paths=allowed_write_paths,
            kwargs=kwargs,
        )
        return {"dispatch_id": "dispatch-1", "run_ref": ".omo/workers/runs/dispatch-1.yaml"}

    fake_module = types.ModuleType("omo.omo_worker_dispatch")
    fake_module.dispatch_task = fake_dispatch
    monkeypatch.setitem(sys.modules, "omo.omo_worker_dispatch", fake_module)

    result = client().post(
        "/api/kems/tasks/task-1/dispatch",
        json={
            "worker_id": "worker-1",
            "allowed_write_paths": ["projects/kairon"],
            "transport": "cli_prompt",
            "prior_evidence": ["evidence-1"],
            "prompt_addendum": ["Run targeted tests"],
        },
    )

    assert result.status_code == 200
    assert result.json() == {
        "task_id": "task-1",
        "status": "dispatched",
        "dispatch": {"dispatch_id": "dispatch-1", "run_ref": ".omo/workers/runs/dispatch-1.yaml"},
        "authority": "omo",
    }
    assert seen["task_id"] == "task-1"
    assert seen["worker_id"] == "worker-1"
    assert seen["allowed_write_paths"] == ["projects/kairon"]
    assert seen["kwargs"]["transport"] == "cli_prompt"
    assert seen["kwargs"]["prior_evidence"] == ["evidence-1"]
