"""FIB-02: independent clocks; copy provenance never proves artifact identity."""
from contextlib import contextmanager
from datetime import timedelta
from http.client import HTTPConnection
import json
import os
import threading

import pytest
from test_live_server_payload_freshness import live_module, NOW, _revision


@contextmanager
def endpoint(module, tmp_path, *, copy_path=None, age=0, failure=None):
    revision = _revision(module, {"generated_at": (NOW - timedelta(seconds=age)).isoformat()})

    class Store:
        def load(self, require_fresh=True):
            if failure and (require_fresh or failure != "STALE"):
                raise module.ProjectionStateError(failure, "projection_" + failure.lower())
            return revision

    server = module.make_server(
        port=0, page_path=tmp_path / "page", snapshot_path=tmp_path / "unused",
        sources={}, dashboard_code_oid="5" * 40, dashboard_tree_sha256="6" * 64,
        dashboard_code_sha256=module.CODE_BUNDLE_SHA256, materialized_brief_path=copy_path,
    )
    server.projection_store = Store()
    module.POLL_INTERVAL_SECONDS = 1
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        yield conn, server, revision
    finally:
        conn.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def health(conn):
    conn.request("GET", "/health")
    response = conn.getresponse()
    assert response.status == 200
    return json.loads(response.read())


def write_copy(tmp_path, **changes):
    provenance = dict(copied_at=NOW.isoformat(), data_generated_at=(NOW - timedelta(days=1)).isoformat(),
                      revision_id="a" * 64, manifest_sha256="4" * 64,
                      source_path="/private/do-not-expose/agent-brief.json")
    provenance.update(changes)
    path = tmp_path / "copy.json"
    path.write_text(json.dumps(dict(generated_at=provenance["data_generated_at"], provenance=provenance)))
    return path


def test_new_copy_and_lease_cannot_refresh_old_content(live_module, tmp_path):
    path = write_copy(tmp_path)
    with endpoint(live_module, tmp_path, copy_path=path, age=301) as (conn, _, revision):
        result = health(conn)
    assert result["projection_status"] == "STALE"
    clocks = result["projection_time_semantics"]
    assert clocks["state_revision"] == revision.revision_id
    assert clocks["content_generated_at"] == (NOW - timedelta(seconds=301)).isoformat()
    assert clocks["content_status"] == "STALE"
    assert clocks["lease_status"] == "VALID"
    assert clocks["lease_fresh_until"] == revision.fresh_until
    copy = result["materialized_brief"]
    assert copy["copied_at"] == NOW.isoformat()
    assert copy["data_status"] == "STALE"
    assert copy["provenance_comparison"] == "MATCH"
    assert copy["revision_match"] == "UNKNOWN"  # matching self-report is not proof
    assert copy["provenance_trust"] == "SELF_REPORTED"
    assert "/private/do-not-expose" not in json.dumps(result)
    assert result["projection_manifest_sha256"] == revision.manifest_sha256
    assert result["dashboard_code_sha256"] == revision.dashboard_code_bundle_sha256


@pytest.mark.parametrize("changes,comparison", [
    ({"revision_id": "b" * 64}, "MISMATCH"),
    ({"manifest_sha256": "7" * 64}, "MISMATCH"),
    ({"revision_id": None}, "UNKNOWN"),
    ({"manifest_sha256": "invalid"}, "UNKNOWN"),
])
def test_copy_revision_and_manifest_are_independent(live_module, tmp_path, changes, comparison):
    path = write_copy(tmp_path, **changes)
    with endpoint(live_module, tmp_path, copy_path=path) as (conn, _, _):
        result = health(conn)
    assert result["projection_status"] == "BOUND_FRESH"
    assert result["materialized_brief"]["provenance_comparison"] == comparison
    assert result["materialized_brief"]["revision_match"] == "UNKNOWN"


@pytest.mark.parametrize("field", ["copied_at", "data_generated_at"])
@pytest.mark.parametrize("value", [None, "bad", 0, "2026-10-13T02:00:00", "2026-10-13T02:00:01Z"])
def test_copy_invalid_times_are_unknown(live_module, tmp_path, field, value):
    path = write_copy(tmp_path, **{field: value})
    with endpoint(live_module, tmp_path, copy_path=path) as (conn, _, _):
        copy = health(conn)["materialized_brief"]
    assert copy[field] is None
    assert copy["copy_status" if field == "copied_at" else "data_status"] == "UNKNOWN"


@pytest.mark.parametrize("kind", ["missing", "symlink", "parent_symlink", "directory", "fifo", "large", "invalid", "no_provenance"])
def test_unsafe_or_unusable_copy_does_not_affect_main_path(live_module, tmp_path, kind):
    path = tmp_path / "copy.json"
    if kind == "symlink":
        path.symlink_to(tmp_path / "absent")
    elif kind == "parent_symlink":
        folder = tmp_path / "real"
        folder.mkdir()
        (folder / "copy.json").write_text('{}')
        (tmp_path / "link").symlink_to(folder)
        path = tmp_path / "link/copy.json"
    elif kind == "directory":
        path.mkdir()
    elif kind == "fifo":
        os.mkfifo(path)
    elif kind == "large":
        path.write_bytes(b" " * (1024 * 1024 + 1))
    elif kind == "invalid":
        path.write_text('{')
    elif kind == "no_provenance":
        path.write_text(json.dumps({"generated_at": NOW.isoformat()}))
    with endpoint(live_module, tmp_path, copy_path=path) as (conn, _, _):
        result = health(conn)
    assert result["projection_status"] == "BOUND_FRESH"
    assert result["materialized_brief"]["status"] == "UNKNOWN"
    assert result["materialized_brief"]["copied_at"] is None


def test_config_requires_explicit_state_root(live_module, tmp_path, monkeypatch):
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    with endpoint(live_module, tmp_path) as (conn, _, _):
        assert health(conn)["materialized_brief"]["status"] == "UNCONFIGURED"
    path = tmp_path / "runtime/dashboard"
    path.mkdir(parents=True)
    (path / "agent-brief.json").write_bytes(write_copy(tmp_path).read_bytes())
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tmp_path))
    with endpoint(live_module, tmp_path) as (conn, _, _):
        copy = health(conn)["materialized_brief"]
    assert copy["status"] == "AVAILABLE"
    assert copy["configuration_source"] == "OMOSTATION_STATE_ROOT"


@pytest.mark.parametrize("age,status", [(300, "FRESH"), (300.1, "STALE")])
def test_copy_age_boundary_is_not_a_bound_artifact_claim(live_module, tmp_path, age, status):
    path = write_copy(tmp_path, data_generated_at=(NOW - timedelta(seconds=age)).isoformat())
    original = path.read_bytes()
    with endpoint(live_module, tmp_path, copy_path=path) as (conn, _, revision):
        bound_bytes = revision.artifact_bodies["data"]
        copy = health(conn)["materialized_brief"]
        assert revision.artifact_bodies["data"] == bound_bytes
        conn.request("GET", "/health?path=/private/not-a-client-option")
        response = conn.getresponse()
        assert response.status != 200
        response.read()
    assert path.read_bytes() == original
    assert copy["data_status"] == status
    assert copy["revision_match"] == "UNKNOWN"


@pytest.mark.parametrize("failure", ["STALE", "CODE_DRIFT", "ARTIFACT_MISMATCH"])
def test_main_failure_never_uses_copy_as_content(live_module, tmp_path, failure):
    with endpoint(live_module, tmp_path, copy_path=write_copy(tmp_path), failure=failure) as (conn, _, _):
        result = health(conn)
    assert result["projection_status"] == failure
    assert result["payload_generated_at"] is None
    assert result["projection_time_semantics"]["content_generated_at"] is None
    assert result["projection_time_semantics"]["content_status"] == "UNKNOWN"
    assert result["materialized_brief"]["revision_match"] == "UNKNOWN"


def test_sse_clocks_refresh_and_clear_on_revision_error(live_module, tmp_path):
    with endpoint(live_module, tmp_path, copy_path=write_copy(tmp_path)) as (conn, server, revision):
        conn.request("GET", "/events/stream")
        response = conn.getresponse()

        def event():
            name = response.fp.readline().decode().strip()
            data = json.loads(response.fp.readline().decode().removeprefix("data: "))
            assert response.fp.readline().strip() == b""
            return name, data

        name, connected = event()
        assert name == "event: connected"
        assert connected["projection_time_semantics"]["lease_fresh_until"] == revision.fresh_until
        assert connected["projection_manifest_sha256"] == revision.manifest_sha256
        assert connected["materialized_brief"]["provenance_comparison"] == "MATCH"
        revision.revision_id = "b" * 64
        revision.manifest_sha256 = "c" * 64
        name, updated = event()
        assert name == "event: snapshot_updated"
        assert updated["projection_time_semantics"]["state_revision"] == "b" * 64
        assert updated["materialized_brief"]["provenance_comparison"] == "MISMATCH"
        event()  # pulse after update

        def expired(**kwargs):
            raise live_module.ProjectionStateError("STALE", "projection_stale")

        server.projection_store.load = expired
        name, pulse = event()
        assert name == "event: pulse"
        assert pulse["status"] == "STALE"
        assert pulse["projection_time_semantics"]["state_revision"] is None
        assert pulse["projection_time_semantics"]["content_generated_at"] is None
        assert pulse["projection_manifest_sha256"] is None
        assert pulse["materialized_brief"]["provenance_comparison"] == "UNKNOWN"
