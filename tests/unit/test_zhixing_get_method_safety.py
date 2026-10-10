from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import shutil
import subprocess
import sys
import threading
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType

import pytest


ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = ROOT / "bin/panorama/assets/host"
EXECUTION_OPERATIONS = (
    "copilot/ask",
    "proposals/submit",
    "proposals/adjudicate",
    "health/auto-heal",
    "health/execute-heal",
    "bos/invoke",
    "loops/step",
)


def _load_asset(name: str, path: Path):
    loader = SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


class _SpyIndex:
    def __init__(self):
        self.queries = []
        self.executions = []

    def query(self, operation, params):
        self.queries.append((operation, params))
        return {"read_only": True, "operation": operation}

    def execute(self, operation, params):
        self.executions.append((operation, params))
        return {"read_only": True, "operation": operation}


@pytest.fixture
def dashboard_modules(monkeypatch, tmp_path):
    runtime_paths = ModuleType("runtime_paths")
    runtime_paths.CODE_ROOT = tmp_path
    runtime_paths.STATE_ROOT = tmp_path

    class ProjectionStateError(Exception):
        def __init__(self, status="ERROR", public_error="projection_error"):
            super().__init__(status)
            self.status = status
            self.public_error = public_error

    class ProjectionRevisionStore:
        def __init__(self, _root):
            pass

    runtime_paths.ProjectionStateError = ProjectionStateError
    runtime_paths.ProjectionRevisionStore = ProjectionRevisionStore
    monkeypatch.setitem(sys.modules, "runtime_paths", runtime_paths)

    collectors = ModuleType("collectors")
    collectors.__path__ = []
    personal_value = ModuleType("collectors.personal_value")
    personal_value.project_panel_value = lambda value: value
    monkeypatch.setitem(sys.modules, "collectors", collectors)
    monkeypatch.setitem(sys.modules, "collectors.personal_value", personal_value)

    test_host = tmp_path / "dashboard-code"
    test_host.mkdir()
    query_source = test_host / "observatory_query.py"
    live_source = test_host / "live_server.py"
    (test_host / "runtime_paths.py").write_text(
        "# isolated test runtime path contract\n", encoding="utf-8"
    )
    shutil.copyfile(HOST_DIR / "observatory_query.py.asset", query_source)
    shutil.copyfile(HOST_DIR / "live_server.py.asset", live_source)
    query_module = _load_asset("observatory_query", query_source)
    monkeypatch.setitem(sys.modules, "observatory_query", query_module)
    live_server = _load_asset("dcp20_live_server", live_source)
    return query_module, live_server


def _start_server(live_server, tmp_path, index, *, projection=False):
    page = tmp_path / "page.html"
    page.write_text("<!doctype html><title>fixture</title>", encoding="utf-8")
    snapshot = tmp_path / "current.json"
    snapshot.write_text("{}", encoding="utf-8")

    class SnapshotStore:
        def __init__(self, _path):
            pass

        def load(self):
            return index

    live_server.SnapshotStore = SnapshotStore
    server = live_server.make_server(
        port=0,
        page_path=page,
        sources={},
        snapshot_path=snapshot,
        document_root=tmp_path,
        projection_state_root=tmp_path if projection else None,
        dashboard_code_oid="a" * 40 if projection else None,
        dashboard_tree_sha256="b" * 64 if projection else None,
        dashboard_code_sha256="c" * 64 if projection else None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _request(server, path, method="GET", body=None):
    connection = http.client.HTTPConnection(
        "127.0.0.1", server.server_port, timeout=3
    )
    try:
        headers = {"Content-Type": "application/json"} if body is not None else {}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        return response.status, json.loads(raw) if raw else {}
    finally:
        connection.close()


@pytest.mark.parametrize("operation", EXECUTION_OPERATIONS)
def test_execution_operations_are_denied_on_get_without_query_or_side_effects(
    dashboard_modules, tmp_path, monkeypatch, operation
):
    _, live_server = dashboard_modules
    index = _SpyIndex()
    proposal_state = tmp_path / "proposals.json"
    loop_state = tmp_path / "loop.json"
    proposal_state.write_text('{"status":"before"}', encoding="utf-8")
    loop_state.write_text('{"cycle":0}', encoding="utf-8")
    before = {
        proposal_state: hashlib.sha256(proposal_state.read_bytes()).hexdigest(),
        loop_state: hashlib.sha256(loop_state.read_bytes()).hexdigest(),
    }
    subprocess_calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess_calls.append(a))
    server, thread = _start_server(live_server, tmp_path, index)
    try:
        status, payload = _request(server, f"/api/v1/{operation}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert status == 405
    assert payload["error"] == "GET_OPERATION_NOT_ALLOWED"
    assert index.queries == []
    assert index.executions == []
    assert subprocess_calls == []
    assert {
        path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before
    } == before


@pytest.mark.parametrize("operation", EXECUTION_OPERATIONS)
def test_projection_mode_denies_all_execution_posts_before_body_dispatch(
    dashboard_modules, tmp_path, operation
):
    _, live_server = dashboard_modules
    index = _SpyIndex()
    server, thread = _start_server(live_server, tmp_path, index, projection=True)
    try:
        status, payload = _request(
            server, f"/api/v1/{operation}", method="POST", body='{"id":"fixture"}'
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert status == 405
    assert payload["error"] == "read_only_get_only"
    assert index.executions == []
    assert index.queries == []


def test_unknown_get_is_denied_and_allowlisted_read_get_still_dispatches(
    dashboard_modules, tmp_path
):
    query_module, live_server = dashboard_modules
    assert live_server.GET_READ_OPERATIONS - {"document"} == query_module.READ_OPERATIONS
    assert not (live_server.GET_READ_OPERATIONS & set(EXECUTION_OPERATIONS))
    index = _SpyIndex()
    server, thread = _start_server(live_server, tmp_path, index)
    try:
        unknown_status, unknown = _request(server, "/api/v1/not-registered")
        read_status, read = _request(server, "/api/v1/summary")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert unknown_status == 405
    assert unknown["error"] == "GET_OPERATION_NOT_ALLOWED"
    assert read_status == 200
    assert read["operation"] == "summary"
    assert index.queries == [("summary", {})]


@pytest.mark.parametrize("operation", EXECUTION_OPERATIONS)
def test_query_layer_rejects_execution_operations(
    dashboard_modules, operation
):
    query_module, _ = dashboard_modules
    index = query_module.ObservationIndex.__new__(query_module.ObservationIndex)
    with pytest.raises(query_module.QueryError) as caught:
        index.query(operation, {})
    assert caught.value.status == 405
    assert caught.value.code == "READ_ONLY_OPERATION"


def test_post_execution_route_dispatches_to_explicit_executor(
    dashboard_modules, tmp_path
):
    _, live_server = dashboard_modules
    index = _SpyIndex()
    server, thread = _start_server(live_server, tmp_path, index)
    try:
        status, payload = _request(
            server,
            "/api/v1/loops/step",
            method="POST",
            body='{"loop_id":"fixture"}',
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    assert status == 200
    assert payload["operation"] == "loops/step"
    assert index.queries == []
    assert index.executions == [("loops/step", {"loop_id": "fixture"})]
