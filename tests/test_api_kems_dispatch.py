# mock-heavy test file: monkeypatch assigns untyped attrs, so the attribute rule is disabled here.
# pyright: reportAttributeAccessIssue=false

import asyncio
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
    assert result.status_code == 410


def test_dispatch_rejects_private_content():
    result = client().post(
        "/api/kems/tasks/task-1/dispatch",
        json={
            "worker_id": "worker-1",
            "allowed_write_paths": ["projects/knowledge/kairon"],
            "raw_text": "private source",
        },
    )
    assert result.status_code == 410


def test_dispatch_endpoint_is_retired(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("naked KEMS dispatch must not reach the OMO broker")

    fake_module = types.ModuleType("omo.omo_worker_dispatch")
    fake_module.dispatch_task = forbidden
    monkeypatch.setitem(sys.modules, "omo.omo_worker_dispatch", fake_module)

    result = client().post(
        "/api/kems/tasks/task-1/dispatch",
        json={
            "worker_id": "worker-1",
            "allowed_write_paths": ["projects/knowledge/kairon"],
        },
    )

    assert result.status_code == 410
    assert "retired" in result.json()["detail"]


def test_dispatch_endpoint_rejects_before_request_json_is_read():
    class PoisonRequest:
        async def json(self):
            raise AssertionError("retired dispatch must not consume private request bytes")

    try:
        asyncio.run(api_kems.dispatch_kems_task("task-1", PoisonRequest()))  # type: ignore[arg-type]
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 410
    else:
        raise AssertionError("retired dispatch must reject")
