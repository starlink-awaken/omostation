"""scene-calibration-fallback — T7 校准熔断链回归测试.

覆盖 SSOT 对账后的三条线:
1. record 路径落盘即填充 scene_calibration (真实行, 无伪造, 不依赖 cron).
2. demote 只走人类门: _propose_demotion 写 scene_lifecycle_log 提议行,
   一级一级降, 且永不触碰场景卡文件.
3. panorama verifier: 阈值对账 + 人类门完整性 PASS.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    mod = _load("calibration_engine_ut", "bin/ssot/calibration-engine.py")
    monkeypatch.setattr(mod, "_DB_PATH", tmp_path / "data" / "scene-metrics.db")
    monkeypatch.setattr(mod, "_ROOT", tmp_path)
    monkeypatch.setenv("RUNTIME_HOME", str(tmp_path / "runtime"))
    return mod


def _counts(engine, db: Path) -> tuple[int, int]:
    conn = sqlite3.connect(str(db))
    cal = conn.execute("SELECT COUNT(*) FROM scene_calibration").fetchone()[0]
    log = conn.execute("SELECT COUNT(*) FROM scene_lifecycle_log").fetchone()[0]
    conn.close()
    return cal, log


def test_record_populates_calibration_store(engine, tmp_path) -> None:
    """record 落盘 → scene_calibration 出现真实行 (sample_count=1)."""
    engine.record_execution(
        "s-fallback-1",
        "run-1",
        {"status": "succeeded", "confidence": 0.8, "duration_ms": 10,
         "token_usage": 0, "tool_calls": 1},
    )
    db = tmp_path / "data" / "scene-metrics.db"
    cal_n, _ = _counts(engine, db)
    assert cal_n == 1
    conn = sqlite3.connect(str(db))
    row = conn.execute(
        "SELECT sample_count, calibration_score FROM scene_calibration WHERE scene_id=?",
        ("s-fallback-1",),
    ).fetchone()
    conn.close()
    assert row[0] == 1
    assert row[1] > 0.0  # 真实计算值, 非伪造


def test_propose_demotion_one_level_and_log_only(engine, tmp_path) -> None:
    """supervised 低校准 → 提议 assisted, 写 log 行, 不碰卡文件."""
    card_dir = tmp_path / ".omo" / "_truth" / "scenarios" / "v3"
    card_dir.mkdir(parents=True)
    card = card_dir / "s-fallback-2.yaml"
    card.write_text("scene_id: s-fallback-2\nlifecycle: supervised\n", encoding="utf-8")
    for i in range(10):
        engine.record_execution(
            "s-fallback-2", f"run-{i}",
            {"status": "failed", "confidence": 0.1, "duration_ms": 5,
             "token_usage": 0, "tool_calls": 0},
        )
    before = card.read_text(encoding="utf-8")
    demo = engine.check_demotion_triggers("s-fallback-2")
    assert demo["demote"]  # 10 失败样本 → calibration < 0.5 触发
    target = engine._propose_demotion(
        "s-fallback-2", demo["triggers"], demo["calibration"]
    )
    assert target == "assisted"  # 只降一级, 不是直降 shadow
    assert card.read_text(encoding="utf-8") == before  # 卡文件零触碰
    conn = sqlite3.connect(str(tmp_path / "data" / "scene-metrics.db"))
    rows = conn.execute(
        "SELECT from_level, to_level, actor, reason FROM scene_lifecycle_log WHERE scene_id=?",
        ("s-fallback-2",),
    ).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0][0] == "supervised" and rows[0][1] == "assisted"
    assert rows[0][2] == "calibration-engine"
    assert "needs_human" in rows[0][3]


def test_propose_demotion_hold_below_assisted(engine, tmp_path) -> None:
    """shadow 档不提议 (无执行风险), 亦不写 log."""
    card_dir = tmp_path / ".omo" / "_truth" / "scenarios" / "v3"
    card_dir.mkdir(parents=True)
    (card_dir / "s-fallback-3.yaml").write_text(
        "scene_id: s-fallback-3\nlifecycle: shadow\n", encoding="utf-8"
    )
    target = engine._propose_demotion(
        "s-fallback-3", [{"condition": "calibration < 0.5", "action": "demote_to_shadow"}],
        {"calibration_score": 0.1},
    )
    assert target is None
    engine._get_db().close()  # 建表以便断言 log 为空
    _, log_n = _counts(engine, tmp_path / "data" / "scene-metrics.db")
    assert log_n == 0


def test_panorama_passes_on_worktree() -> None:
    """verifier 在本仓 PASS (阈值对账 + 人类门); 数据项仅作信息上报."""
    pano = _load("scene_calibration_panorama_ut", "bin/ssot/scene-calibration-panorama.py")
    result = pano.run_all(ROOT)
    by_name = {c["name"]: c for c in result["checks"]}
    assert by_name["threshold-agreement"]["status"] == "PASS"
    assert by_name["human-gate"]["status"] == "PASS"
    assert by_name["consumption-proof"]["status"] in ("PRESENT", "EMPTY", "ERROR")
    assert result["overall"] == "PASS"
