"""Exercise the managed revision reader and HTTP response using real large files."""

from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import threading
from types import ModuleType

import pytest


HOST = Path(__file__).resolve().parents[1] / "bin/panorama/assets/host"
MIB = 1024 * 1024


def _load(name, path, monkeypatch):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def modules(tmp_path, monkeypatch):
    code = tmp_path / "code"
    code.mkdir()
    for name in ("runtime_paths", "live_server", "observatory_query"):
        asset = HOST / f"{name}.py.asset"
        assert asset.is_file(), f"missing managed asset: {asset.name}"
        shutil.copyfile(asset, code / f"{name}.py")
    runtime = _load("runtime_paths", code / "runtime_paths.py", monkeypatch)
    collectors = ModuleType("collectors")
    collectors.__path__ = []
    personal_value = ModuleType("collectors.personal_value")
    personal_value.project_panel_value = lambda value: value
    monkeypatch.setitem(sys.modules, "collectors", collectors)
    monkeypatch.setitem(sys.modules, "collectors.personal_value", personal_value)
    _load("observatory_query", code / "observatory_query.py", monkeypatch)
    live = _load("size_contract_live_server", code / "live_server.py", monkeypatch)
    return runtime, live


def _revision(root, runtime, live, size):
    root.mkdir()
    revision_id = "a" * 64
    revision = root / "revisions" / revision_id
    revision.mkdir(parents=True)
    ledger_hash = "e" * 64
    envelope = {
        "available": True,
        "event_ledger_sha256": ledger_hash,
        "value_truth": {"schema": "value-truth-snapshot/v1"},
    }
    data = json.dumps({"personal_value_truth": envelope}).encode()
    data += b" " * (size - len(data))
    bodies = {
        "data": ("data.json", data),
        "page": ("index.html", b"<!doctype html><title>isolated fixture</title>"),
        "agent_brief": (
            "agent-brief.json",
            json.dumps({"authority": {
                "value_proof_readiness": runtime._ledger_bound_value_readiness(envelope)
            }}).encode(),
        ),
    }
    artifacts = {}
    for name, (filename, body) in bodies.items():
        (revision / filename).write_bytes(body)
        artifacts[name] = {"filename": filename, "sha256": hashlib.sha256(body).hexdigest()}
    now = datetime.now(timezone.utc)
    manifest = {
        "schema_version": "zhixing-projection-manifest/v1",
        "revision_id": revision_id,
        "generated_at": now.isoformat(),
        "fresh_until": (now + timedelta(minutes=10)).isoformat(),
        "producer": {
            "root_oid": "b" * 40,
            "root_tree_sha256": "b" * 64,
            "omo_gitlink_oid": "c" * 40,
            "ecos_gitlink_oid": "d" * 40,
            "collector_sha256": "c" * 64,
            "value_meter_sha256": "d" * 64,
            "process_identity": "sha256:" + "f" * 64,
        },
        "dashboard": {
            "code_oid": "1" * 40,
            "tree_sha256": "2" * 64,
            "code_bundle_sha256": live.CODE_BUNDLE_SHA256,
        },
        "state_root": {"identity": "sha256:" + hashlib.sha256(str(root).encode()).hexdigest()},
        "contracts": {
            "pointer": "zhixing-projection-pointer/v1",
            "manifest": "zhixing-projection-manifest/v1",
            "reader": "zhixing-dashboard-revision-reader/v1",
        },
        "source_hashes": {
            "claims_store_sha256": "3" * 64,
            "claims_high_water_sha256": "4" * 64,
            "claims_witness_sha256": "5" * 64,
            "event_ledger_sha256": ledger_hash,
        },
        "claims": {
            "sequence": 0,
            "last_receipt": "sha256:" + "6" * 64,
            "activation": "isolated-fixture",
            "effective_authority": "unactivated",
            "instruction_capable": False,
        },
        "artifacts": artifacts,
    }
    manifest_body = json.dumps(manifest).encode()
    (revision / "manifest.json").write_bytes(manifest_body)
    (root / "current-revision.json").write_text(json.dumps({
        "schema_version": "zhixing-projection-pointer/v1",
        "revision_id": revision_id,
        "manifest_sha256": hashlib.sha256(manifest_body).hexdigest(),
    }))
    return data


@pytest.mark.parametrize("size, accepted", [(16 * MIB + 1, True), (32 * MIB + 1, False)])
def test_real_revision_read_and_http_response_are_bounded(modules, tmp_path, size, accepted):
    runtime, live = modules
    state = tmp_path / "state"
    original = _revision(state, runtime, live, size)
    store = runtime.ProjectionRevisionStore(state)
    if accepted:
        assert 16 * MIB < size < 32 * MIB
        assert store.load().artifact_bodies["data"] == original
    else:
        with pytest.raises(runtime.ProjectionStateError) as error:
            store.load()
        assert error.value.status == "ARTIFACT_UNAVAILABLE"
    server = live.make_server(
        port=0, sources={}, document_root=state,
        projection_state_root=state, dashboard_code_oid="1" * 40,
        dashboard_tree_sha256="2" * 64, dashboard_code_sha256=live.CODE_BUNDLE_SHA256,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request("GET", "/data.json")
        response = connection.getresponse()
        body = response.read()
        if accepted:
            assert response.status == 200
            assert body == original
        else:
            assert response.status == 503
            assert json.loads(body)["error"] == "projection_artifact_unavailable"
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_artifact_caps_align_without_relaxing_control_or_document_limits(modules):
    runtime, live = modules
    assert runtime._MAX_ARTIFACT_BYTES == live.MAX_PROJECTION_ARTIFACT_BYTES == 32 * MIB
    assert runtime._MAX_CONTROL_BYTES == 256 * 1024
    assert live.MAX_DOCUMENT_BYTES == MIB
