"""Integration tests for BOS dispatch in journey-engine."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOURNEY_ENGINE = ROOT / "bin" / "ssot" / "journey-engine.py"

# Load journey-engine via importlib (hyphen in filename)
_spec = importlib.util.spec_from_file_location("journey_engine", str(JOURNEY_ENGINE))
_je = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_je)


def test_execute_dry_run():
    r = subprocess.run([sys.executable, str(JOURNEY_ENGINE), "execute", "inbox-to-decision", "--dry-run"],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode in (0, 1)
    import json
    data = json.loads(r.stdout)
    assert data["status"] in ("succeeded", "escalated")


def test_validate_all_journeys():
    import json
    for jid in ["journey-inbox-to-decision", "journey-document-review", "journey-knowledge-ingest"]:
        r = subprocess.run([sys.executable, str(JOURNEY_ENGINE), "validate", jid],
                           capture_output=True, text=True, cwd=str(ROOT))
        assert r.returncode in (0, 1)
        assert json.loads(r.stdout)["valid"] is True


def test_graph_includes_all_scenes():
    import json
    r = subprocess.run([sys.executable, str(ROOT / "bin/ssot/scene-graph.py"), "validate"],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode in (0, 1)
    assert json.loads(r.stdout)["nodes"] >= 3


def test_dispatch_kos_search():
    ctx = _je.ExecutionContext("test", "test", {"query": "test"})
    result = _je._dispatch_bos_uri("bos://memory/kos/search", ctx)
    assert result["status"] == "succeeded"


def test_dispatch_kos_ingest():
    ctx = _je.ExecutionContext("test", "test", {"content": "test ingest content"})
    result = _je._dispatch_bos_uri("bos://memory/kos/ingest", ctx)
    assert result["status"] in ("succeeded", "skipped")


def test_dispatch_gbrain():
    ctx = _je.ExecutionContext("test", "test", {})
    result = _je._dispatch_bos_uri("bos://memory/gbrain/sync", ctx)
    assert result["status"] == "succeeded"


def test_dispatch_codeanalyze():
    ctx = _je.ExecutionContext("test", "test", {})
    result = _je._dispatch_bos_uri("bos://analysis/codeanalyze/scan", ctx)
    assert result["status"] == "succeeded"


def test_dispatch_scene_invoke():
    ctx = _je.ExecutionContext("test", "test", {}, dry_run=True)
    result = _je._dispatch_bos_uri("bos://scene/document-review/execute", ctx)
    assert result["status"] in ("succeeded", "escalated")


def test_dispatch_unknown():
    ctx = _je.ExecutionContext("test", "test", {})
    result = _je._dispatch_bos_uri("bos://unknown/domain/action", ctx)
    assert result["status"] == "unresolved"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {name}")
            except Exception as e:
                print(f"  FAIL: {name}: {e}")
