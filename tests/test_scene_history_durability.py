"""scene-history.py — 场景历史耐久性（导出/备份/暴跌检测/恢复）回归测试.

对应 2026-09-17 实证事故: data/scene-metrics.db 静默清空且无备份/无告警.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCHEMA = """
CREATE TABLE scene_execution (id TEXT PRIMARY KEY, scene_id TEXT NOT NULL,
  run_id TEXT NOT NULL, status TEXT NOT NULL, confidence REAL DEFAULT 0.0,
  success INTEGER DEFAULT 0, duration_ms INTEGER DEFAULT 0, token_usage INTEGER DEFAULT 0,
  tool_calls INTEGER DEFAULT 0, human_reviewed INTEGER DEFAULT 0, human_agreed INTEGER DEFAULT 0,
  created_at TEXT NOT NULL);
CREATE TABLE scene_calibration (id INTEGER PRIMARY KEY AUTOINCREMENT,
  scene_id TEXT NOT NULL, window_days INTEGER NOT NULL, sample_count INTEGER DEFAULT 0,
  calibration_score REAL DEFAULT 0.0, precision REAL DEFAULT 0.0, recall REAL DEFAULT 0.0,
  false_positive_rate REAL DEFAULT 0.0, avg_duration_ms REAL DEFAULT 0.0,
  avg_token_usage REAL DEFAULT 0.0, intervention_rate REAL DEFAULT 0.0,
  trend_14d REAL DEFAULT 0.0, computed_at TEXT NOT NULL);
CREATE TABLE scene_lifecycle_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
  scene_id TEXT NOT NULL, from_level TEXT, to_level TEXT NOT NULL, reason TEXT,
  calibration_score REAL DEFAULT 0.0, actor TEXT DEFAULT 'calibration-engine', created_at TEXT NOT NULL);
"""


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "scene_history", ROOT / "bin/ssot/scene-history.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["scene_history"] = module
    spec.loader.exec_module(module)
    return module


def _seed(db: Path, *, executions: int = 5, calibrations: int = 3, lifecycles: int = 2) -> None:
    conn = sqlite3.connect(str(db))
    conn.executescript(SCHEMA)
    for i in range(executions):
        conn.execute(
            "INSERT INTO scene_execution VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"e{i}", "scene-a", f"run{i}", "succeeded", 0.8, 1, 100, 0, 0, 0, 0,
             f"2026-09-1{i % 3}T00:00:00+00:00"),
        )
    for i in range(calibrations):
        conn.execute(
            "INSERT INTO scene_calibration (scene_id, window_days, sample_count, "
            "calibration_score, computed_at) VALUES (?,?,?,?,?)",
            ("scene-a", 30, 10, 0.72, f"2026-09-1{i}T00:00:00+00:00"),
        )
    for i in range(lifecycles):
        conn.execute(
            "INSERT INTO scene_lifecycle_log (scene_id, from_level, to_level, reason, "
            "calibration_score, actor, created_at) VALUES (?,?,?,?,?,?,?)",
            ("scene-a", "shadow", "assisted", "calibration>=0.6", 0.72, "calibration-engine",
             f"2026-09-1{i}T01:00:00+00:00"),
        )
    conn.commit()
    conn.close()


def _wire(mod, tmp_path):
    db = tmp_path / "data" / "scene-metrics.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    mod.DB_PATH = db
    mod.EXPORT_DIR = tmp_path / ".omo" / "_knowledge" / "scene-history"
    mod.BACKUP_DIR = tmp_path / "runtime" / "backups"
    mod.BASELINE_PATH = mod.EXPORT_DIR / "baseline.json"
    return db


def test_export_is_idempotent(tmp_path):
    mod = _load_module()
    db = _wire(mod, tmp_path)
    _seed(db)

    assert mod.export()["ok"] is True
    first = {p.name: p.read_bytes() for p in mod.EXPORT_DIR.glob("*.json")}
    assert first

    assert mod.export()["ok"] is True
    second = {p.name: p.read_bytes() for p in mod.EXPORT_DIR.glob("*.json")}
    assert first == second, "导出必须确定性（内容不变则字节不变）"


def test_export_aggregates_execution_by_day(tmp_path):
    mod = _load_module()
    db = _wire(mod, tmp_path)
    _seed(db, executions=6)
    mod.export()
    doc = json.loads((mod.EXPORT_DIR / "execution-daily.json").read_text())
    rows = doc["rows"]
    # 6 条执行落在 3 个不同日期 → 3 行聚合
    assert len(rows) == 3
    assert all({"day", "scene_id", "runs", "successes", "avg_confidence"} <= set(r) for r in rows)
    assert sum(r["runs"] for r in rows) == 6
    assert all(r["successes"] == r["runs"] for r in rows)


def test_backup_retention_keeps_14(tmp_path):
    mod = _load_module()
    db = _wire(mod, tmp_path)
    _seed(db)
    mod.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    # 造 15 份历史备份
    for i in range(15):
        (mod.BACKUP_DIR / f"scene-metrics-2026080{i % 10}{(i // 10)}.db").write_bytes(b"x")
    names_before = sorted(p.name for p in mod.BACKUP_DIR.glob("scene-metrics-*.db"))
    assert len(names_before) == 15

    result = mod.backup(keep=14)
    assert result["ok"] is True
    remaining = sorted(p.name for p in mod.BACKUP_DIR.glob("scene-metrics-*.db"))
    assert len(remaining) == 14
    assert names_before[0] not in remaining, "最旧一份应被删除"
    assert result["pruned"]


def test_verify_detects_row_drop(tmp_path):
    mod = _load_module()
    db = _wire(mod, tmp_path)
    _seed(db)
    assert mod.verify()["ok"] is True          # 首次建立基线

    conn = sqlite3.connect(str(db))
    conn.execute("DELETE FROM scene_calibration")
    conn.execute("DELETE FROM scene_lifecycle_log")
    conn.commit()
    conn.close()

    result = mod.verify()
    assert result["ok"] is False
    assert result["reason"] == "row_count_drop"
    tables = {d["table"] for d in result["drops"]}
    assert {"calibration", "lifecycle"} <= tables
    # 下跌时保留旧基线（不被污染）
    baseline = json.loads(mod.BASELINE_PATH.read_text())["row_counts"]
    assert baseline.get("calibration", 0) > 0


def test_verify_first_run_builds_baseline(tmp_path):
    mod = _load_module()
    db = _wire(mod, tmp_path)
    _seed(db)
    assert not mod.BASELINE_PATH.exists()
    result = mod.verify()
    assert result["ok"] is True and result.get("first_run") is True
    assert mod.BASELINE_PATH.exists()


def test_restore_recovers_from_export(tmp_path):
    """端到端: 导出 → 清空 DB → restore → 行数与导出一致."""
    mod = _load_module()
    db = _wire(mod, tmp_path)
    _seed(db, executions=5, calibrations=3, lifecycles=2)
    mod.export()
    export_doc = json.loads((mod.EXPORT_DIR / "calibration.json").read_text())
    assert len(export_doc["rows"]) == 3

    conn = sqlite3.connect(str(db))
    conn.execute("DELETE FROM scene_calibration")
    conn.execute("DELETE FROM scene_lifecycle_log")
    conn.commit()
    conn.close()

    result = mod.restore()
    assert result["ok"] is True
    assert result["row_counts"]["calibration"] == 3
    assert result["row_counts"]["lifecycle"] == 2


def test_restore_skips_when_db_nonempty(tmp_path):
    mod = _load_module()
    db = _wire(mod, tmp_path)
    _seed(db)
    mod.export()
    result = mod.restore()
    assert result["ok"] is True and result.get("skipped") is True


def test_verify_missing_db_is_failure(tmp_path):
    mod = _load_module()
    _wire(mod, tmp_path)  # 不创建 DB
    result = mod.verify()
    assert result["ok"] is False and result["reason"] == "db_missing"
