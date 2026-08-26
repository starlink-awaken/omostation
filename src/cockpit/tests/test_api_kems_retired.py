"""KEMS naked dispatch endpoint is retired (Task 6 step 2)."""

from __future__ import annotations

import asyncio

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


def test_kems_direct_dispatch_returns_410_without_reading_asgi_body() -> None:
    app = FastAPI()
    app.include_router(api_kems.router)
    sent: list[dict[str, object]] = []

    async def poison_receive() -> dict[str, object]:
        raise AssertionError("retired KEMS dispatch must not read the ASGI request body")

    async def capture_send(message: dict[str, object]) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/kems/tasks/TASK-1/dispatch",
        "raw_path": b"/api/kems/tasks/TASK-1/dispatch",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    asyncio.run(app(scope, poison_receive, capture_send))

    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 410
