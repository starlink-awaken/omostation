"""Integration tests for journey-engine.py."""

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


def test_execute_dry_run():
    """Dry-run execution should succeed."""
    r = run("execute", "scene-inbox-to-decision", "--dry-run")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["status"] == "succeeded"
    assert data["scene_id"] == "scene-inbox-to-decision"
    assert data["steps"] > 0


def test_validate_journey():
    """Journey validation should pass for valid spec."""
    r = run("validate", "journey-inbox-to-decision")
    assert r.returncode == 0, f"stderr: {r.stderr}"
    data = json.loads(r.stdout)
    assert data["valid"] is True
    assert data["states"] == 10
    assert data["transitions"] == 11
    assert len(data["backedges"]) == 0


def test_validate_nonexistent_journey():
    """Validation should fail for non-existent journey."""
    r = run("validate", "journey-nonexistent")
    assert r.returncode != 0


def test_execute_nonexistent_scene():
    """Execution should fail for non-existent scene."""
    r = run("execute", "scene-nonexistent", "--dry-run")
    assert r.returncode != 0


def test_execute_with_signal():
    """Execution with custom signal should work."""
    r = run("execute", "scene-inbox-to-decision", "--signal", '{"source":"test","content":"hello"}', "--dry-run")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["status"] == "succeeded"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {name}")
            except Exception as e:
                print(f"  FAIL: {name}: {e}")
