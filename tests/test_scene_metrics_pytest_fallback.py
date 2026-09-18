"""pytest 上下文下校准库兜底 —— 生产库永不被测试写.

对应 2026-09-18 二次实证: 首次修复只给 tests/scene_v2/* 加 SCENE_METRICS_DB
隔离, 但基于旧提交的 worktree / 未更新的调用方仍污染生产库 (清理后当天又出现
gate-test-scene 夹具行)。故在解析层兜底: pytest 上下文 + 未显式指定 →
自动改写为临时库。
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_shared():
    spec = importlib.util.spec_from_file_location("_shared_probe", ROOT / "bin/ssot/_shared.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_shared_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_explicit_env_wins():
    """SCENE_METRICS_DB 显式指定 → 优先级最高（测试隔离靠它）."""
    shared = _load_shared()
    target = Path("/tmp/explicit-target.db")
    os.environ["SCENE_METRICS_DB"] = str(target)
    try:
        # macOS /tmp -> /private/tmp 符号链接, 比较 resolve() 后的规范路径
        assert shared.scene_metrics_db_path() == target.resolve()
    finally:
        del os.environ["SCENE_METRICS_DB"]


def test_pytest_context_never_uses_production():
    """关键: 本测试本身就在 pytest 下运行, 且**没有**设 SCENE_METRICS_DB.

    兜底必须生效 —— 解析结果不得是生产库。
    """
    prod = (ROOT / "data" / "scene-metrics.db").resolve()
    os.environ.pop("SCENE_METRICS_DB", None)
    assert os.environ.get("PYTEST_CURRENT_TEST"), "应在 pytest 上下文中"
    shared = _load_shared()
    resolved = shared.scene_metrics_db_path().resolve()
    assert resolved != prod, (
        "pytest 上下文下解析到了生产库 —— 兜底失效, 测试会污染信任平面证据"
    )
    assert "scene-metrics-pytest" in str(resolved)


def test_engine_helper_delegates_to_shared():
    """calibration-engine 的 _default_db_path 必须与 _shared 同源."""
    os.environ.pop("SCENE_METRICS_DB", None)
    spec = importlib.util.spec_from_file_location(
        "cal_engine_probe", ROOT / "bin/ssot/calibration-engine.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cal_engine_probe"] = mod
    spec.loader.exec_module(mod)
    assert "scene-metrics-pytest" in str(mod._default_db_path())
    assert mod._DB_PATH.resolve() != (ROOT / "data" / "scene-metrics.db").resolve()


def test_unpatched_subprocess_style_call_cannot_pollute(tmp_path):
    """端到端: 像旧测试那样直接 subprocess 跑生产引擎 (不设 env), 在生产库上无效.

    模拟事故调用方式: cwd=ROOT, 不带 SCENE_METRICS_DB, 结果取 pytest 兜底。
    """
    prod = ROOT / "data" / "scene-metrics.db"
    before = prod.stat().st_mtime_ns if prod.is_file() else None

    env = {k: v for k, v in os.environ.items() if k != "SCENE_METRICS_DB"}
    r = subprocess.run(
        [sys.executable, str(ROOT / "bin/ssot/calibration-engine.py"), "record",
         "--scene-id", "gate-test-scene", "--run-id", "unpatched-probe",
         "--result", '{"status":"succeeded","confidence":0.85}'],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "pytest" in r.stderr, "应打印兜底改写提示"

    after = prod.stat().st_mtime_ns if prod.is_file() else None
    assert before == after, (
        "未设 SCENE_METRICS_DB 的 subprocess 调用仍写到了生产库 —— 兜底失效"
    )
