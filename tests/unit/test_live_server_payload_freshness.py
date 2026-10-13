"""Bound data age, rather than a renewed lease, determines HTTP health freshness."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from importlib.machinery import SourceFileLoader
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import threading
from types import ModuleType, SimpleNamespace

import pytest
from test_zhixing_release_identity import release_env, publish, load

HOST_DIR = Path(__file__).resolve().parents[2] / "bin/panorama/assets/host"
NOW = datetime(2026, 10, 13, 2, 0, tzinfo=timezone.utc)


def test_live_http_uses_actual_managed_release_identity(live_module, release_env, tmp_path):
    root = publish(release_env)
    actual = load("http_release_identity", root / "release_identity.py").managed_release_identity(root)
    revision = _revision(live_module, {"generated_at": NOW.isoformat()})
    revision.dashboard_code_oid = actual["code_oid"]
    revision.dashboard_tree_sha256 = actual["tree_sha256"]
    revision.dashboard_code_bundle_sha256 = actual["code_bundle_sha256"]
    assert live_module.CODE_BUNDLE_SHA256 == actual["code_bundle_sha256"]
    server = live_module.make_server(
        port=0, page_path=tmp_path / "page.html", snapshot_path=tmp_path / "unused.json",
        sources={}, dashboard_code_oid=actual["code_oid"],
        dashboard_tree_sha256=actual["tree_sha256"], dashboard_code_sha256=actual["code_bundle_sha256"])
    server.projection_store = SimpleNamespace(load=lambda **kwargs: revision)
    server.dashboard_identity_resolver = lambda: live_module.resolve_dashboard_code_identity(root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        health = json.loads(response.read())
        assert response.status == 200
        assert health["projection_status"] == "BOUND_FRESH"
        assert health["code_drift"] is False
        (root / "runtime_paths.py").write_text("tampered dependency")
        connection.request("GET", "/health")
        assert json.loads(connection.getresponse().read())["projection_status"] == "CODE_DRIFT"
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _load(name, path, monkeypatch):
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    loader.exec_module(module)
    return module


@pytest.fixture
def live_module(tmp_path, monkeypatch):
    deployed = tmp_path / "host"
    deployed.mkdir()
    for filename in ("observatory_query.py", "live_server.py"):
        shutil.copyfile(HOST_DIR / (filename + ".asset"), deployed / filename)
    (deployed / "runtime_paths.py").write_text("# isolated revision-reader seam\n")
    runtime = ModuleType("runtime_paths")
    runtime.CODE_ROOT = tmp_path
    runtime.STATE_ROOT = tmp_path

    class ProjectionStateError(Exception):
        def __init__(self, status, public_error):
            self.status = status
            self.public_error = public_error

    runtime.ProjectionStateError = ProjectionStateError
    runtime.ProjectionRevisionStore = lambda root: None
    monkeypatch.setitem(sys.modules, "runtime_paths", runtime)
    collectors = ModuleType("collectors")
    collectors.__path__ = []
    personal = ModuleType("collectors.personal_value")
    personal.project_panel_value = lambda value: value
    monkeypatch.setitem(sys.modules, "collectors", collectors)
    monkeypatch.setitem(sys.modules, "collectors.personal_value", personal)
    _load("observatory_query", deployed / "observatory_query.py", monkeypatch)
    module = _load("mvp_payload_freshness_live_server", deployed / "live_server.py", monkeypatch)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is not None else NOW.replace(tzinfo=None)

    monkeypatch.setattr(module, "datetime", FrozenDatetime)
    return module


def _revision(module, payload):
    return SimpleNamespace(
        revision_id="a" * 64,
        producer_root_oid="b" * 40,
        producer_root_tree_sha256="c" * 64,
        omo_gitlink_oid="d" * 40,
        ecos_gitlink_oid="e" * 40,
        collector_sha256="f" * 64,
        value_meter_sha256="1" * 64,
        source_hashes={"event_ledger_sha256": "2" * 64},
        claims_sequence=1,
        claims_last_receipt="3" * 64,
        claims_activation="shadow-active",
        claims_effective_authority="v1",
        claims_instruction_capable=False,
        generated_at=NOW.isoformat(),
        fresh_until=(NOW + timedelta(minutes=10)).isoformat(),
        manifest_sha256="4" * 64,
        dashboard_code_oid="5" * 40,
        dashboard_tree_sha256="6" * 64,
        dashboard_code_bundle_sha256=module.CODE_BUNDLE_SHA256,
        artifact_bodies={"data": payload if isinstance(payload, bytes) else json.dumps(payload).encode()},
    )


def _http_health(module, tmp_path, payload, *, expired=False, drift=False, integrity_error=None):
    revision = _revision(module, payload)
    lease = tmp_path / "lease.json"
    lease.write_text(json.dumps({"fresh_until": (NOW + timedelta(seconds=-1 if expired else 600)).isoformat()}))

    class RevisionStore:
        def load(self, require_fresh=True):
            if integrity_error:
                raise module.ProjectionStateError("ARTIFACT_MISMATCH", integrity_error)
            deadline = datetime.fromisoformat(json.loads(lease.read_text())["fresh_until"])
            if require_fresh and NOW > deadline:
                raise module.ProjectionStateError("STALE", "projection_stale")
            return revision

    server = module.make_server(
        port=0, page_path=tmp_path / "page.html", snapshot_path=tmp_path / "fallback.json",
        sources={}, dashboard_code_oid=("7" if drift else "5") * 40,
        dashboard_tree_sha256="6" * 64, dashboard_code_sha256=module.CODE_BUNDLE_SHA256,
    )
    server.projection_store = RevisionStore()
    # A fresh legacy snapshot cannot launder old or invalid bound artifact data.
    (tmp_path / "fallback.json").write_text(json.dumps({"generated_at": NOW.isoformat()}))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        assert response.status == 200
        return json.loads(response.read()), revision
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _http_stream_status(module, tmp_path, payload):
    revision = _revision(module, payload)

    class RevisionStore:
        def load(self, require_fresh=True):
            return revision

    server = module.make_server(
        port=0, page_path=tmp_path / "page.html", snapshot_path=tmp_path / "fallback.json",
        sources={}, dashboard_code_oid="5" * 40,
        dashboard_tree_sha256="6" * 64, dashboard_code_sha256=module.CODE_BUNDLE_SHA256,
    )
    server.projection_store = RevisionStore()
    module.POLL_INTERVAL_SECONDS = 1
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request("GET", "/events/stream")
        response = connection.getresponse()
        assert response.status == 200

        def read_event():
            event_name = response.fp.readline().decode("utf-8").strip()
            data_line = response.fp.readline().decode("utf-8").strip()
            assert response.fp.readline().strip() == b""
            assert event_name.startswith("event: ")
            assert data_line.startswith("data: ")
            return event_name.removeprefix("event: "), json.loads(data_line.removeprefix("data: "))

        connected = read_event()
        pulse = read_event()
        return connected, pulse
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize("age,status", [(0, "BOUND_FRESH"), (299.9, "BOUND_FRESH"), (300, "BOUND_FRESH"), (300.1, "STALE"), (900, "STALE")])
def test_http_health_uses_bound_payload_age_despite_new_lease(live_module, tmp_path, age, status):
    timestamp = (NOW - timedelta(seconds=age)).isoformat()
    health, revision = _http_health(live_module, tmp_path, {"generated_at": timestamp})
    assert health["projection_status"] == status
    assert health["payload_generated_at"] == timestamp
    assert health["payload_age_seconds"] == pytest.approx(age)
    assert health["code_drift"] is False
    assert health["projection_error"] == ("projection_payload_stale" if status == "STALE" else None)
    assert health["state_revision"] == revision.revision_id
    assert health["source_hashes"] == revision.source_hashes
    assert health["projection_generated_at"] == NOW.isoformat()


@pytest.mark.parametrize("payload,error", [
    ({}, "projection_payload_timestamp_missing"),
    ({"generated_at": None}, "projection_payload_timestamp_missing"),
    ({"generated_at": "bad"}, "projection_payload_timestamp_invalid"),
    ({"generated_at": "2026-10-13T02:00:00"}, "projection_payload_timestamp_invalid"),
    ({"generated_at": 123}, "projection_payload_timestamp_invalid"),
    ({"generated_at": (NOW + timedelta(seconds=1)).isoformat()}, "projection_payload_timestamp_future"),
    (b"not-json", "projection_payload_timestamp_invalid"),
    ([], "projection_payload_timestamp_invalid"),
])
def test_http_health_invalid_or_future_data_cannot_be_green(live_module, tmp_path, payload, error):
    health, _ = _http_health(live_module, tmp_path, payload)
    assert health["projection_status"] == "UNKNOWN"
    assert health["projection_error"] == error
    assert health["code_drift"] is False


def test_http_health_timezone_offset_is_valid(live_module, tmp_path):
    health, _ = _http_health(live_module, tmp_path, {"generated_at": "2026-10-13T10:00:00+08:00"})
    assert health["projection_status"] == "BOUND_FRESH"
    assert health["payload_age_seconds"] == 0


def test_http_health_expired_lease_has_priority_and_is_not_code_drift(live_module, tmp_path):
    health, _ = _http_health(live_module, tmp_path, {"generated_at": "bad"}, expired=True)
    assert health["projection_status"] == "STALE"
    assert health["projection_error"] == "projection_stale"
    assert health["payload_generated_at"] is None
    assert health["code_drift"] is False


def test_http_health_bound_code_mismatch_still_reports_code_drift(live_module, tmp_path):
    health, _ = _http_health(live_module, tmp_path, {"generated_at": "bad"}, drift=True)
    assert health["projection_status"] == "CODE_DRIFT"
    assert health["projection_error"] == "projection_code_drift"
    assert health["code_drift"] is True


def test_http_health_integrity_error_has_priority_without_false_code_drift(live_module, tmp_path):
    health, _ = _http_health(live_module, tmp_path, {"generated_at": NOW.isoformat()}, integrity_error="projection_artifact_mismatch")
    assert health["projection_status"] == "ARTIFACT_MISMATCH"
    assert health["projection_error"] == "projection_artifact_mismatch"
    assert health["payload_generated_at"] is None
    assert health["code_drift"] is False


@pytest.mark.parametrize("payload,status,error", [
    ({"generated_at": (NOW - timedelta(seconds=301)).isoformat()}, "STALE", "projection_payload_stale"),
    ({"generated_at": "bad"}, "UNKNOWN", "projection_payload_timestamp_invalid"),
    ({"generated_at": (NOW + timedelta(seconds=1)).isoformat()}, "UNKNOWN", "projection_payload_timestamp_future"),
    ({"generated_at": NOW.isoformat()}, "BOUND_FRESH", None),
])
def test_event_stream_uses_bound_payload_freshness_for_connected_and_pulse(
    live_module, tmp_path, payload, status, error
):
    connected, pulse = _http_stream_status(live_module, tmp_path, payload)

    assert connected[0] == "connected"
    assert connected[1]["status"] == status
    assert connected[1].get("error") == error
    assert pulse[0] == "pulse"
    assert pulse[1]["status"] == status
    assert pulse[1].get("error") == error
