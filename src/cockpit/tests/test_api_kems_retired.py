"""KEMS naked dispatch endpoint is retired (Task 6 step 2)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_kems


def test_kems_direct_dispatch_returns_410_and_writes_nothing(tmp_path):
    app = FastAPI()
    app.include_router(api_kems.router)
    client = TestClient(app)

    omo_dir = tmp_path / ".omo"
    omo_dir.mkdir()
    before = sorted(str(p.relative_to(omo_dir)) for p in omo_dir.rglob("*") if p.is_file())

    response = client.post(
        "/api/kems/tasks/TASK-1/dispatch",
        json={"worker_id": "pi", "allowed_write_paths": ["docs/"]},
    )

    assert response.status_code == 410
    assert "retired" in response.json()["detail"]
    after = sorted(str(p.relative_to(omo_dir)) for p in omo_dir.rglob("*") if p.is_file())
    assert after == before
