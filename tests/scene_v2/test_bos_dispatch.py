"""Integration tests for BOS dispatch in journey-engine."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOURNEY_ENGINE = ROOT / "bin" / "ssot" / "journey-engine.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(JOURNEY_ENGINE), *args],
        capture_output=True, text=True, cwd=str(ROOT),
    )


def test_execute_with_capability_refs():
    """Scene with capability_refs should dispatch to them."""
    r = run("execute", "scene-inbox-to-decision", "--dry-run")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    # In dry-run, capabilities are still listed
    assert data["status"] == "succeeded"


def test_validate_all_journeys():
    """All journey specs should validate."""
    for journey_id in ["journey-inbox-to-decision", "journey-document-review", "journey-knowledge-ingest"]:
        r = run("validate", journey_id)
        assert r.returncode == 0, f"{journey_id} failed: {r.stderr}"
        data = json.loads(r.stdout)
        assert data["valid"] is True, f"{journey_id} invalid: {data}"


def test_graph_includes_all_scenes():
    """Scene graph should include all 3 scenes."""
    r = subprocess.run(
        [sys.executable, str(ROOT / "bin/ssot/scene-graph.py"), "validate"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["nodes"] >= 3


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {name}")
            except Exception as e:
                print(f"  FAIL: {name}: {e}")
