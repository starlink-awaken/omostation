"""Integration tests for calibration-engine.py.

所有用例必须指向**隔离的临时校准库**（SCENE_METRICS_DB），绝不写生产
`data/scene-metrics.db`。历史事故：本文件曾直接跑生产库，把夹具 scene_id
(test-scene / gate-test-scene / empty-scene-xyz / integration-test-scene)
写进生产校准表；其中 gate-test-scene 累积 35 条夹具样本，`check-gates`
直接返回 `eligible: true` —— 测试夹具伪装成晋升证据。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CALIBRATION_ENGINE = ROOT / "bin" / "ssot" / "calibration-engine.py"


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """把校准库指向临时文件，并断言测试期间不触碰生产库."""
    prod = ROOT / "data" / "scene-metrics.db"
    before = prod.stat().st_mtime_ns if prod.is_file() else None
    monkeypatch.setenv("SCENE_METRICS_DB", str(tmp_path / "scene-metrics.db"))
    yield tmp_path / "scene-metrics.db"
    after = prod.stat().st_mtime_ns if prod.is_file() else None
    assert before == after, (
        "测试修改了生产校准库 data/scene-metrics.db —— 用例必须通过 "
        "SCENE_METRICS_DB 隔离（见 test_calibration_engine.py 顶部说明）"
    )


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
    # 直跑时同样隔离: 绝不写生产校准库
    import tempfile
    os.environ.setdefault(
        "SCENE_METRICS_DB", str(Path(tempfile.mkdtemp()) / "scene-metrics.db")
    )
    _fail = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS: {name}")
            except Exception as e:
                _fail += 1
                print(f"  FAIL: {name}: {e}")
    raise SystemExit(1 if _fail else 0)
