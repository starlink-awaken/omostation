"""Integration tests for calibration-engine.py."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CALIBRATION_ENGINE = ROOT / "bin" / "ssot" / "calibration-engine.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(CALIBRATION_ENGINE), *args],
        capture_output=True, text=True, cwd=str(ROOT),
    )


def test_record_and_compute():
    """Recording executions should update calibration score."""
    r = run("record", "--scene-id", "test-scene", "--run-id", "test-001",
            "--result", '{"status":"succeeded","confidence":0.9}')
    assert r.returncode == 0

    r = run("compute", "--scene-id", "test-scene")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["scene_id"] == "test-scene"
    assert data["sample_count"] >= 1
    assert 0 <= data["calibration_score"] <= 1


def test_compute_empty():
    """Computing calibration for scene with no data should return 0."""
    r = run("compute", "--scene-id", "empty-scene-xyz")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["sample_count"] == 0


def test_check_gates():
    """Gate checking should work for various levels."""
    # Record enough samples to pass assisted gates
    for i in range(35):
        run("record", "--scene-id", "gate-test-scene", "--run-id", f"gate-{i}",
            "--result", '{"status":"succeeded","confidence":0.85}')

    r = run("check-gates", "--scene-id", "gate-test-scene", "--target-level", "supervised")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "eligible" in data
    assert "gates" in data


def test_check_demotion():
    """Demotion check should work."""
    r = run("check-demotion", "--scene-id", "test-scene")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert "demote" in data
    assert "triggers" in data


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {name}")
            except Exception as e:
                print(f"  FAIL: {name}: {e}")
