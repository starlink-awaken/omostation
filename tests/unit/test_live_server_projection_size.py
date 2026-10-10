"""Projection downloads follow the revision artifact bound, not document bound."""

from __future__ import annotations

import hashlib
import importlib.util
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

HOST_DIR = Path(__file__).resolve().parents[2] / "bin/panorama/assets/host"
PROJECTION_ARTIFACT_LIMIT = 16 * 1024 * 1024
DOCUMENT_LIMIT = 1024 * 1024


def _module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    deployed = tmp_path / "deployed"
    deployed.mkdir()
    shutil.copy2(HOST_DIR / "observatory_query.py.asset", deployed / "observatory_query.py")
    (deployed / "runtime_paths.py").write_text("# test runtime path module\n", encoding="utf-8")

    # The server imports these deployment modules; this route test does not
    # exercise projection-store loading or value collection.
    runtime_paths = ModuleType("runtime_paths")
    runtime_paths.CODE_ROOT = deployed
    runtime_paths.STATE_ROOT = deployed
    runtime_paths.ProjectionRevisionStore = type("ProjectionRevisionStore", (), {})

    class ProjectionStateError(Exception):
        def __init__(self, status="UNAVAILABLE", public_error="projection_unavailable"):
            super().__init__(status)
            self.status = status
            self.public_error = public_error

    runtime_paths.ProjectionStateError = ProjectionStateError
    collectors = ModuleType("collectors")
    personal_value = ModuleType("collectors.personal_value")
    personal_value.project_panel_value = lambda *_args, **_kwargs: {}
    collectors.personal_value = personal_value
    monkeypatch.setitem(sys.modules, "runtime_paths", runtime_paths)
    monkeypatch.setitem(sys.modules, "collectors", collectors)
    monkeypatch.setitem(sys.modules, "collectors.personal_value", personal_value)

    query_loader = SourceFileLoader(
        "zhixing_projection_size_query_test", str(deployed / "observatory_query.py")
    )
    query_spec = importlib.util.spec_from_loader(query_loader.name, query_loader)
    assert query_spec is not None and query_spec.loader is not None
    query_module = importlib.util.module_from_spec(query_spec)
    monkeypatch.setitem(sys.modules, query_spec.name, query_module)
    query_loader.exec_module(query_module)
    monkeypatch.setitem(sys.modules, "observatory_query", query_module)

    server_path = deployed / "live_server.py"
    shutil.copy2(HOST_DIR / "live_server.py.asset", server_path)
    loader = SourceFileLoader("zhixing_live_server_projection_size_test", str(server_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    loader.exec_module(module)
    return module


def _serve(module, tmp_path: Path):
    page = tmp_path / "index.html"
    page.write_bytes(b"<html></html>")
    data = tmp_path / "data.json"
    data.write_bytes(b"{}")
    server = module.make_server(
        port=0,
        page_path=page,
        snapshot_path=data,
        document_root=tmp_path / "documents",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _get(server, path: str):
    return _request(server, "GET", path)


def _request(server, method: str, path: str):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=10)
    connection.request(method, path)
    response = connection.getresponse()
    result = response.status, response.read()
    connection.close()
    return result


def test_revision_json_routes_accept_bounded_artifacts_and_reject_oversize(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    server, thread = _serve(module, tmp_path)
    body = b"x" * PROJECTION_ARTIFACT_LIMIT
    revision = SimpleNamespace(artifact_bodies={"data": body, "agent_brief": body})
    server.projection_store = object()
    server.projection_revision = lambda: revision
    try:
        status, response_body = _get(server, "/data.json")
        assert status == 200
        assert response_body == body

        status, response_body = _get(server, "/agent-brief.json")
        assert status == 200
        assert response_body == body

        revision.artifact_bodies["data"] = b"x" * (PROJECTION_ARTIFACT_LIMIT + 1)
        status, response_body = _get(server, "/data.json")
        assert status == 503
        assert b"agent_projection_unavailable" in response_body

        revision.artifact_bodies["agent_brief"] = b"x" * (PROJECTION_ARTIFACT_LIMIT + 1)
        status, response_body = _get(server, "/agent-brief.json")
        assert status == 503
        assert b"agent_projection_unavailable" in response_body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("route, path_attribute", [
    ("/data.json", "data_path"),
    ("/agent-brief.json", "agent_brief_path"),
])
def test_legacy_json_routes_keep_one_mib_document_limit(
    tmp_path, monkeypatch, route, path_attribute
):
    module = _module(tmp_path, monkeypatch)
    server, thread = _serve(module, tmp_path)
    body = b"x" * (DOCUMENT_LIMIT + 1)
    if path_attribute == "agent_brief_path":
        # Normal legacy mode intentionally has no Agent Brief identity.  This
        # test injects its only fallback source so the shared JSON-route branch
        # itself proves that it keeps the legacy 1 MiB boundary.
        path = tmp_path / "agent-brief.json"
        monkeypatch.setattr(
            module.DashboardServer,
            "agent_brief_path",
            property(lambda _server: path),
        )
    else:
        path = getattr(server, path_attribute)
    path.write_bytes(body)
    try:
        status, response_body = _get(server, route)
        assert status == 503
        assert b"agent_projection_unavailable" in response_body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_registered_observation_documents_keep_one_mib_limit_and_digest_check(
    tmp_path, monkeypatch
):
    module = _module(tmp_path, monkeypatch)
    document_root = tmp_path / "documents"
    document_root.mkdir()
    document = document_root / "note.md"
    body = b"x" * DOCUMENT_LIMIT
    document.write_bytes(body)
    record = {"document_id": "note", "path": str(document), "sha256": hashlib.sha256(body).hexdigest()}
    assert module.document_from_registry(
        {"documents": [record]}, document_root, "note", require_digest=True
    ) == body

    document.write_bytes(body + b"x")
    with pytest.raises(module.DocumentError) as error:
        module.document_from_registry(
            {"documents": [record]}, document_root, "note", require_digest=False
        )
    assert error.value.status == 413

    document.write_bytes(body)
    record["sha256"] = "0" * 64
    with pytest.raises(module.DocumentError) as error:
        module.document_from_registry(
            {"documents": [record]}, document_root, "note", require_digest=True
        )
    assert error.value.reason == "document_digest_mismatch"


def test_code_identity_probe_does_not_serialize_concurrent_requests(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    workers = 50
    barrier = threading.Barrier(workers)
    counter_lock = threading.Lock()
    calls = {"probe": 0, "resolver": 0}
    code_oid = "a" * 40
    identity = {
        "code_oid": code_oid,
        "tree_sha256": "b" * 64,
        "code_bundle_sha256": "c" * 64,
    }

    def probe():
        with counter_lock:
            calls["probe"] += 1
        time.sleep(0.05)
        return {"code_oid": code_oid}

    def resolve():
        with counter_lock:
            calls["resolver"] += 1
        # Exceeds the former 2-second waiter limit. Concurrent requests must
        # share the in-flight proof instead of returning validation-busy 503s.
        time.sleep(2.1)
        return identity

    cache = module.DashboardCodeIdentityCache(resolver=resolve, probe=probe)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        def resolve_concurrently(_index):
            barrier.wait(timeout=3)
            return cache.resolve(("revision", code_oid))

        results = list(pool.map(resolve_concurrently, range(workers)))

    assert results == [identity] * workers
    assert calls == {"probe": 1, "resolver": 1}


def test_code_identity_failure_is_shared_by_concurrent_requests(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    workers = 50
    barrier = threading.Barrier(workers)
    counter_lock = threading.Lock()
    calls = {"probe": 0, "resolver": 0}

    def probe():
        with counter_lock:
            calls["probe"] += 1
        time.sleep(0.1)
        raise module.ProjectionStateError("IDENTITY_UNBOUND", "projection_identity_unbound")

    def resolve():
        with counter_lock:
            calls["resolver"] += 1
        raise AssertionError("resolver must not run after a failed identity probe")

    cache = module.DashboardCodeIdentityCache(resolver=resolve, probe=probe)

    def resolve_concurrently(_index):
        barrier.wait(timeout=3)
        try:
            cache.resolve(("revision", "a" * 40))
        except module.ProjectionStateError as error:
            return error.status, error.public_error
        raise AssertionError("identity probe failure must be propagated")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(resolve_concurrently, range(workers)))

    assert results == [
        ("IDENTITY_UNBOUND", "projection_identity_unbound")
    ] * workers
    assert calls == {"probe": 1, "resolver": 0}


def test_code_identity_cache_hit_rejects_changed_dashboard_file(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    code_oid = "a" * 40
    identity = {
        "code_oid": code_oid,
        "tree_sha256": "b" * 64,
        "code_bundle_sha256": "c" * 64,
    }
    cache = module.DashboardCodeIdentityCache(
        resolver=lambda: identity,
        probe=lambda: {"code_oid": code_oid},
    )
    binding = ("revision", code_oid)
    assert cache.resolve(binding) == identity

    code_file = tmp_path / "deployed" / "live_server.py"
    original_fingerprints = cache._fingerprints
    fingerprint_calls = 0

    def change_after_probe():
        nonlocal fingerprint_calls
        fingerprint_calls += 1
        if fingerprint_calls == 3:
            code_file.write_bytes(
                code_file.read_bytes() + b"# changed during cache hit\n"
            )
        return original_fingerprints()

    cache._fingerprints = change_after_probe

    with pytest.raises(module.ProjectionStateError) as error:
        cache.resolve(binding)

    assert error.value.status == "CODE_DRIFT"
    assert error.value.public_error == "projection_code_drift"


def test_get_operation_method_classification_is_explicit_and_complete(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    query_module = sys.modules["observatory_query"]
    expected_disabled = {
        "copilot/ask",
        "proposals/submit",
        "proposals/adjudicate",
        "health/auto-heal",
        "health/execute-heal",
        "bos/invoke",
        "loops/step",
        "preflight",
        "agent/preflight",
    }
    assert module.DISABLED_OPERATIONS == expected_disabled
    assert module.READ_ONLY_GET_OPERATIONS.isdisjoint(module.DISABLED_OPERATIONS)
    assert module.READ_ONLY_GET_OPERATIONS | module.DISABLED_OPERATIONS == set(
        query_module.OPERATIONS
    )
    assert module.READ_ONLY_GET_ROUTES == {
        "/api/v1/document",
        "/api/v1/events/stream",
        "/api/v1/value/metrics",
        "/api/v1/agent/objective-coverage",
        "/api/v1/agent/strategic-gaps",
        "/api/v1/agent/brief",
        "/api/v1/agent/reconciliation-candidates",
        "/api/v1/agent/value-proof-readiness",
        "/api/v1/agent/authorization-desk",
        "/api/v1/agent/pending-authorizations",
        "/api/v1/harness/runs",
        "/api/v1/resident",
    }
    assert module.DISABLED_GET_ROUTES == {
        "/api/v1/compute/live",
        "/api/v1/compute/infer",
    }


def test_disabled_and_unknown_get_operations_never_reach_query(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    server, thread = _serve(module, tmp_path)
    calls = []
    monkeypatch.setattr(
        module.DashboardHandler,
        "_snapshot_index",
        lambda _handler: SimpleNamespace(
            query=lambda operation, params: calls.append((operation, params)) or {}
        ),
    )
    monkeypatch.setattr(
        module.DashboardHandler,
        "_handle_compute_live",
        lambda _handler: pytest.fail("compute GET must be disabled"),
    )
    try:
        for operation in sorted(module.DISABLED_OPERATIONS):
            status, body = _request(server, "GET", f"/api/v1/{operation}")
            assert status == 405
            assert b'"error":"operation_disabled"' in body

        for path in ("/api/v1/compute/live", "/api/v1/compute/infer"):
            status, body = _request(server, "GET", path)
            assert status == 405
            assert b'"error":"operation_disabled"' in body

        status, body = _request(server, "GET", "/api/v1/not-registered")
        assert status == 404
        assert b'"error":"unknown_operation"' in body

        status, _body = _request(server, "GET", "/api/v1/summary")
        assert status == 200
        assert calls == [("summary", {})]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_all_api_post_operations_are_rejected_before_query(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    query_module = sys.modules["observatory_query"]
    server, thread = _serve(module, tmp_path)
    monkeypatch.setattr(
        module.DashboardHandler,
        "_snapshot_index",
        lambda _handler: pytest.fail("POST must not query or execute operations"),
    )
    try:
        for path in [
            *(f"/api/v1/{operation}" for operation in sorted(query_module.OPERATIONS)),
            "/api/v1/compute/infer",
            "/api/v1/not-registered",
        ]:
            status, body = _request(server, "POST", path)
            assert status == 405
            assert b'"error":"operation_disabled"' in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_static_javascript_routes_are_allowlisted(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    asset_root = Path(module.__file__).parent
    (asset_root / "data_access.js").write_text("window.ready = true;", encoding="utf-8")
    (asset_root / "unlisted.js").write_text("window.unsafe = true;", encoding="utf-8")
    server, thread = _serve(module, tmp_path)
    try:
        status, body = _request(server, "GET", "/data_access.js")
        assert status == 200
        assert body == b"window.ready = true;"

        for path in ("/unlisted.js", "/data_access.js?cache_bust=1"):
            status, _body = _request(server, "GET", path)
            assert status == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_static_javascript_route_rejects_symlink_target(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    asset_root = Path(module.__file__).parent
    outside_target = tmp_path / "private.js"
    secret = b"private target content"
    outside_target.write_bytes(secret)
    (asset_root / "data_access.js").symlink_to(outside_target)
    server, thread = _serve(module, tmp_path)
    try:
        status, body = _request(server, "GET", "/data_access.js")
        assert status == 404
        assert secret not in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_static_javascript_route_rejects_oversize_asset(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    module.MAX_STATIC_JS_BYTES = 4
    asset_root = Path(module.__file__).parent
    (asset_root / "data_access.js").write_bytes(b"12345")
    server, thread = _serve(module, tmp_path)
    try:
        status, body = _request(server, "GET", "/data_access.js")
        assert status == 413
        assert b"js_too_large" in body
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_observation_query_direct_calls_reject_disabled_operations(tmp_path, monkeypatch):
    module = _module(tmp_path, monkeypatch)
    index = module.ObservationIndex.__new__(module.ObservationIndex)
    for operation in module.DISABLED_OPERATIONS:
        with pytest.raises(module.QueryError) as error:
            index.query(operation, {})
        assert error.value.status == 405
        assert error.value.code == "OPERATION_DISABLED"

    manifest_index = module.ObservationIndex(
        {"generation_id": "manifest-test", "strategic": {"trace": {"nodes": [], "edges": []}}},
        observed_now="2026-10-08T00:00:00Z",
    )
    result = manifest_index.query("manifest", {})
    payload = result["data"]
    assert payload["operations"] == sorted(module.READ_ONLY_GET_OPERATIONS)
    assert payload["disabled_operations"] == [
        {"operation": operation, "callable": False}
        for operation in sorted(module.DISABLED_OPERATIONS)
    ]
