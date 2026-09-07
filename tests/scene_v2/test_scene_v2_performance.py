"""Performance tests for Scene v2 components."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENE_GRAPH = ROOT / "bin" / "ssot" / "scene-graph.py"
JOURNEY_ENGINE = ROOT / "bin" / "ssot" / "journey-engine.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(args[0]), *args[1:]],
        capture_output=True, text=True, cwd=str(ROOT),
    )


def test_scene_graph_build_performance():
    r = run(SCENE_GRAPH, "build")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert len(data["nodes"]) >= 3


def test_scene_graph_build_latency():
    start = time.perf_counter()
    r = run(SCENE_GRAPH, "build")
    elapsed = time.perf_counter() - start
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert len(data["nodes"]) >= 3
    assert elapsed < 2.0, f"scene-graph build took {elapsed:.3f}s, expected < 2.0s"


def test_journey_engine_dry_run_latency():
    start = time.perf_counter()
    r = run(JOURNEY_ENGINE, "execute", "scene-inbox-to-decision", "--dry-run")
    elapsed = time.perf_counter() - start
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["status"] == "succeeded"
    assert elapsed < 3.0, f"journey-engine dry-run took {elapsed:.3f}s, expected < 3.0s"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {name}")
            except Exception as e:
                print(f"  FAIL: {name}: {e}")
