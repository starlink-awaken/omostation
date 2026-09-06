"""Integration tests for scene-graph.py."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENE_GRAPH = ROOT / "bin" / "ssot" / "scene-graph.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCENE_GRAPH), *args],
        capture_output=True, text=True, cwd=str(ROOT),
    )


def test_validate():
    """Graph validation should pass (no cycles)."""
    r = run("validate")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["valid"] is True
    assert data["cycles_detected"] == 0
    assert data["nodes"] >= 3


def test_build():
    """Graph build should produce valid DAG."""
    r = run("build")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "entry_point" in data
    assert "topological_order" in data
    assert "nodes" in data
    assert len(data["topological_order"]) == len(data["nodes"])


def test_execute_dry_run():
    """Graph execution should traverse all reachable nodes."""
    r = run("execute", "--dry-run")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["scenes_executed"] >= 1
    assert "results" in data
    assert "correlation_id" in data


def test_entry_point_is_root():
    """Entry point should be a root node (no inbound edges)."""
    r = run("build")
    data = json.loads(r.stdout)
    entry = data["entry_point"]
    # Entry should be first in topological order
    assert data["topological_order"][0] == entry


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {name}")
            except Exception as e:
                print(f"  FAIL: {name}: {e}")
