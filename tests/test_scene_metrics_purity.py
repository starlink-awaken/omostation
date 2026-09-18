"""校准库纯度守卫 + 引擎 DB 隔离 回归测试.

对应 2026-09-18 事故: 测试夹具写进生产校准库, gate-test-scene 35 samples
使 check-gates 返回 eligible:true —— 夹具伪装成晋升证据.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CALIBRATION_ENGINE = ROOT / "bin" / "ssot" / "calibration-engine.py"


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


SCHEMA = """
CREATE TABLE scene_execution (id TEXT PRIMARY KEY, scene_id TEXT NOT NULL,
  run_id TEXT NOT NULL, status TEXT NOT NULL, confidence REAL DEFAULT 0.0,
  success INTEGER DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE scene_calibration (id INTEGER PRIMARY KEY AUTOINCREMENT,
  scene_id TEXT NOT NULL, window_days INTEGER NOT NULL, sample_count INTEGER DEFAULT 0);
"""


def _db(path: Path, scene_ids: dict[str, int]) -> Path:
    conn = sqlite3.connect(str(path))
    conn.executescript(SCHEMA)
    for sid, n in scene_ids.items():
        for i in range(n):
            conn.execute(
                "INSERT INTO scene_execution VALUES (?,?,?,?,?,?,?)",
                (f"{sid}-{i}", sid, f"run-{i}", "succeeded", 0.9, 1, "2026-09-18T00:00:00+00:00"),
            )
        conn.execute(
            "INSERT INTO scene_calibration (scene_id, window_days, sample_count) VALUES (?,?,?)",
            (sid, 30, n),
        )
    conn.commit()
    conn.close()
    return path


# ── 纯度检查 ─────────────────────────────────────────────


def test_detects_fixture_rows(tmp_path):
    purity = _load("purity", "bin/gac/check-scene-metrics-purity.py")
    db = _db(tmp_path / "m.db", {"gate-test-scene": 35, "scene-knowledge-ingest": 2})
    r = purity.audit(db)
    assert r["status"] == "polluted"
    ids = {f["scene_id"] for f in r["fixtures"]}
    assert "gate-test-scene" in ids
    assert "scene-knowledge-ingest" not in ids, "真实场景不得被误判为夹具"
    # 跨 scene_execution(35) + scene_calibration(1) 求和
    assert r["fixture_rows"] == 36
    assert r["fixtures"][0]["tables"]["scene_execution"] == 35


def test_clean_db_status(tmp_path):
    purity = _load("purity", "bin/gac/check-scene-metrics-purity.py")
    db = _db(tmp_path / "m.db", {"scene-knowledge-ingest": 3})
    r = purity.audit(db)
    assert r["fixtures"] == []
    # scene-knowledge-ingest 在注册表中 → 不应出现在 unregistered
    assert all(u["scene_id"] != "scene-knowledge-ingest" for u in r["unregistered"])


def test_missing_db_is_not_failure(tmp_path):
    purity = _load("purity", "bin/gac/check-scene-metrics-purity.py")
    r = purity.audit(tmp_path / "nope.db")
    assert r["exists"] is False and r["status"] == "no_db"
    assert purity.main(["--db", str(tmp_path / "nope.db"), "--json"]) == 0


def test_exit_code_1_on_fixtures(tmp_path):
    purity = _load("purity", "bin/gac/check-scene-metrics-purity.py")
    db = _db(tmp_path / "m.db", {"test-scene": 5})
    assert purity.main(["--db", str(db), "--json"]) == 1


def test_is_fixture_matches_patterns():
    purity = _load("purity", "bin/gac/check-scene-metrics-purity.py")
    for sid in ("test-scene", "gate-test-scene", "empty-scene-xyz",
                "integration-test-scene", "fixture-scene", "dummy-scene", "test-foo"):
        assert purity.is_fixture(sid), f"{sid} 应判为夹具"
    for sid in ("scene-knowledge-ingest", "scene-inbox-to-decision",
                "document-review", "scene-agora-bos-gateway"):
        assert not purity.is_fixture(sid), f"{sid} 不应判为夹具"


def test_purge_removes_only_fixtures(tmp_path, monkeypatch):
    purity = _load("purity", "bin/gac/check-scene-metrics-purity.py")
    # 隔离 purge 内的自动备份, 避免写真实 runtime/backups/
    monkeypatch.setenv("SCENE_METRICS_DB", str(tmp_path / "m.db"))
    monkeypatch.setenv("SCENE_HISTORY_BACKUP_DIR", str(tmp_path / "backups"))
    db = _db(tmp_path / "m.db", {"gate-test-scene": 35, "test-scene": 1,
                                 "scene-knowledge-ingest": 2})
    r = purity.purge(db, purity.audit(db), yes=True)
    assert r["ok"] is True
    assert set(r["purged_ids"]) == {"gate-test-scene", "test-scene"}
    assert r["backup"]["ok"] is True, "清理前必须成功备份"
    assert (tmp_path / "backups").is_dir(), "备份应落在隔离目录"

    after = purity.audit(db)
    assert after["fixtures"] == []
    remaining = {sid for sid, n in _scene_rows(db).items() if n}
    assert "scene-knowledge-ingest" in remaining, "真实场景不得被删除"


def test_purge_requires_confirmation(tmp_path):
    purity = _load("purity", "bin/gac/check-scene-metrics-purity.py")
    db = _db(tmp_path / "m.db", {"test-scene": 3})
    r = purity.purge(db, purity.audit(db), yes=False)
    assert r["ok"] is False and r["reason"] == "confirmation_required"
    assert purity.audit(db)["fixtures"], "未确认时不得删除任何行"


def _scene_rows(db: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db))
    try:
        return {r[0]: r[1] for r in conn.execute(
            "SELECT scene_id, COUNT(*) FROM scene_execution GROUP BY scene_id")}
    finally:
        conn.close()


# ── 引擎 DB 路径注入 ─────────────────────────────────────


def test_engine_honors_env_db(tmp_path):
    """SCENE_METRICS_DB 必须改变引擎实际写入的库."""
    tmp_db = tmp_path / "isolated.db"
    env = {**__import__("os").environ, "SCENE_METRICS_DB": str(tmp_db)}
    r = subprocess.run(
        [sys.executable, str(CALIBRATION_ENGINE), "record",
         "--scene-id", "scene-env-probe", "--run-id", "env-1",
         "--result", '{"status":"succeeded","confidence":0.9}'],
        capture_output=True, text=True, cwd=str(ROOT), env=env,
    )
    assert r.returncode == 0, r.stderr
    assert tmp_db.is_file(), "引擎未使用 SCENE_METRICS_DB 指向的库"
    assert "scene-env-probe" in _scene_rows(tmp_db)


def test_engine_default_path_unchanged(tmp_path, monkeypatch):
    """非 pytest 上下文 + 未设 env 时, 默认仍是 <root>/data/scene-metrics.db.

    (pytest 上下文下的行为已被 tests/test_scene_metrics_pytest_fallback.py 覆盖:
     自动改写为临时库以保护生产库。)
    """
    mod = _load("cal_engine", "bin/ssot/calibration-engine.py")
    monkeypatch.delenv("SCENE_METRICS_DB", raising=False)
    # 模拟非 pytest 的生产调用环境
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    assert mod._default_db_path().as_posix().endswith("data/scene-metrics.db")


def test_scene_v2_tests_do_not_touch_production_db(tmp_path):
    """端到端: 跑 scene_v2 用例后生产库 mtime 不变 (防回归到事故状态)."""
    prod = ROOT / "data" / "scene-metrics.db"
    before = prod.stat().st_mtime_ns if prod.is_file() else None
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/scene_v2/test_calibration_engine.py",
         "-q", "--no-header", "-p", "no:cacheprovider"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    after = prod.stat().st_mtime_ns if prod.is_file() else None
    assert before == after, (
        "tests/scene_v2 再次写入了生产校准库 —— 隔离已回退\n"
        f"{r.stdout[-500:]}"
    )
