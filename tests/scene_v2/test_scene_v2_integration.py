"""End-to-end integration tests for Scene v2 pipeline.

Covered:
- scene-graph builds topology from real scene cards
- journey-engine executes a journey via BOS dispatch
- calibration-engine records execution and computes score
- Full pipeline: graph -> execute -> record -> calibrate
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENE_GRAPH = ROOT / "bin" / "ssot" / "scene-graph.py"
JOURNEY_ENGINE = ROOT / "bin" / "ssot" / "journey-engine.py"
CALIBRATION_ENGINE = ROOT / "bin" / "ssot" / "calibration-engine.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(args[0]), *args[1:]],
        capture_output=True, text=True, cwd=str(ROOT),
    )


def test_graph_builds_from_real_scenes():
    r = run(SCENE_GRAPH, "build")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert len(data["nodes"]) >= 3
    assert "scene-inbox-to-decision" in data["nodes"]
    assert "scene-document-review" in data["nodes"]


def test_graph_validate_has_no_cycles():
    r = run(SCENE_GRAPH, "validate")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["valid"] is True
    assert data["cycles_detected"] == 0


def test_journey_engine_executes_dry_run():
    r = run(JOURNEY_ENGINE, "execute", "scene-inbox-to-decision", "--dry-run")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["status"] == "succeeded"
    assert data["scene_id"] == "scene-inbox-to-decision"
    assert data["steps"] >= 1


def test_journey_engine_validates_real_journeys():
    for jid in ["journey-inbox-to-decision", "journey-document-review", "journey-knowledge-ingest"]:
        r = run(JOURNEY_ENGINE, "validate", jid)
        assert r.returncode == 0, f"stderr: {r.stderr} for {jid}"
        data = json.loads(r.stdout)
        assert data["valid"] is True
        assert data["backedges"] == []


def test_calibration_engine_records_execution():
    run_id = "integration-test-001"
    r = run(CALIBRATION_ENGINE, "record", "--scene-id", "integration-test-scene",
            "--run-id", run_id, "--result", '{"status":"succeeded","confidence":0.92}')
    assert r.returncode == 0, f"stderr: {r.stderr}"

    r = run(CALIBRATION_ENGINE, "compute", "--scene-id", "integration-test-scene")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["sample_count"] >= 1
    assert 0 <= data["calibration_score"] <= 1


def test_full_pipeline_graph_to_calibration():
    r = run(SCENE_GRAPH, "build")
    assert r.returncode == 0
    graph = json.loads(r.stdout)

    scene_id = "scene-knowledge-ingest"
    assert scene_id in graph["nodes"]

    r = run(JOURNEY_ENGINE, "execute", scene_id, "--dry-run")
    assert r.returncode == 0
    execution = json.loads(r.stdout)
    assert execution["status"] == "succeeded"

    run_id = f"pipeline-{execution['run_id']}"
    r = run(CALIBRATION_ENGINE, "record", "--scene-id", scene_id,
            "--run-id", run_id, "--result", json.dumps(execution))
    assert r.returncode == 0

    r = run(CALIBRATION_ENGINE, "compute", "--scene-id", scene_id)
    assert r.returncode == 0
    calibration = json.loads(r.stdout)
    assert calibration["sample_count"] >= 1
    assert calibration["scene_id"] == scene_id


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {name}")
            except Exception as e:
                print(f"  FAIL: {name}: {e}")
