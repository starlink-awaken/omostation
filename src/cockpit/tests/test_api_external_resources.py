from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from cockpit.web import api_external_resources


def _app() -> FastAPI:
    app = FastAPI()
    app.include_router(api_external_resources.router)
    return app


def _projection() -> dict:
    return {
        "schema": "external-resource-catalog/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "observed_at": "2026-08-03T00:00:00Z",
        "health_ttl_seconds": 900,
        "policy_digest": "external-connection-fabric/v1",
        "resources": [],
        "errors": [],
        "summary": {
            "resource_count": 0,
            "unavailable_count": 0,
            "error_count": 0,
            "by_kind": {},
            "by_availability": {},
        },
    }


def test_external_resources_prefers_latest_omo_observation(monkeypatch, tmp_path):
    projection = _projection()
    calls: list[object] = []

    def fake_latest(omo_dir):
        calls.append(omo_dir)
        return {"schema": "external-resource-observation/v1", "catalog": projection}

    def fail_discovery(*_args, **_kwargs):
        raise AssertionError("latest governed observation should win")

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", fake_latest)
    monkeypatch.setattr(api_external_resources, "collect_external_resources", fail_discovery)

    response = TestClient(_app()).get("/api/external-resources")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["source"] == "omo.external_resource_observation"
    assert response.json()["projection"] == projection
    assert response.json()["external_side_effects"] == "disabled"
    assert calls == [tmp_path / ".omo"]


def test_external_resources_falls_back_to_safe_discovery(monkeypatch, tmp_path):
    projection = _projection()
    calls: list[tuple[object, bool]] = []

    def fake_discovery(root, *, probe):
        calls.append((root, probe))
        return projection

    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", lambda _path: None)
    monkeypatch.setattr(api_external_resources, "collect_external_resources", fake_discovery)

    response = TestClient(_app()).get("/api/external-resources")

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["source"] == "agora.external_resource_discovery"
    assert calls == [(tmp_path, True)]


def test_external_resources_fails_closed_when_discovery_is_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(api_external_resources, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(api_external_resources, "read_latest_external_resource_observation", lambda _path: None)

    def fail_discovery(*_args, **_kwargs):
        raise RuntimeError("provider boundary unavailable")

    monkeypatch.setattr(api_external_resources, "collect_external_resources", fail_discovery)

    response = TestClient(_app()).get("/api/external-resources")
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is False
    assert body["status"] == "unavailable"
    assert body["projection"]["activation"] == "forbidden"
    assert body["external_side_effects"] == "disabled"
    assert body["worker_launch"] is False
