#!/usr/bin/env python3
"""Scene History 耐久性 — 信任回路命脉数据（校准/生命周期/执行）的备份与恢复.

背景（2026-09-17 实证事故）: `data/scene-metrics.db` 三张表在无人察觉时被清空
（2026-09-13 尚有 4 条场景数据，09-17 全表 0 行）；该 DB 被 data/.gitignore 忽略
（`*.db`），因此本地丢失即永久丢失，且没有任何告警。

三层防护:
  L1 持久导出  .omo/_knowledge/scene-history/{calibration,lifecycle,execution-daily}.json
               （git 跟踪 → 跨机器/跨分支/误删均存活）
  L2 本地快照  runtime/backups/scene-metrics-<YYYYMMDD>.db（保留 14 份，快速回滚）
  L3 基线      .omo/_knowledge/scene-history/baseline.json（暴跌检测对照）
  恢复         由 L1 重建 DB（DB 为空/缺失时自愈）

DB 仍是唯一写入口；导出是单向派生。

用法:
    python3 bin/ssot/scene-history.py export
    python3 bin/ssot/scene-history.py backup
    python3 bin/ssot/scene-history.py verify      # 暴跌 → exit 1
    python3 bin/ssot/scene-history.py restore     # 仅在 DB 空/缺失时动作
    python3 bin/ssot/scene-history.py status
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
try:
    from datetime import UTC
except ImportError:  # cron 下 python3 可能是 3.9 (<3.11 无 datetime.UTC)
    from datetime import timezone as _timezone
    UTC = _timezone.utc
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    """环境变量覆盖路径（测试隔离 / ops 迁移用）."""
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


DB_PATH = _env_path("SCENE_METRICS_DB", _ROOT / "data" / "scene-metrics.db")
EXPORT_DIR = _env_path("SCENE_HISTORY_EXPORT_DIR",
                       _ROOT / ".omo" / "_knowledge" / "scene-history")
BACKUP_DIR = _env_path("SCENE_HISTORY_BACKUP_DIR", _ROOT / "runtime" / "backups")
BASELINE_PATH = EXPORT_DIR / "baseline.json"
BACKUP_KEEP = 14
# 下跌告警阈值: 行数低于基线的该比例即视为异常
DROP_RATIO = 0.5

EXPORT_SCHEMA = "scene-history-export/v1"
DERIVED_NOTE = "derived from data/scene-metrics.db — DB 是唯一写入口, 勿手编"

TABLES = {
    "execution": "scene_execution",
    "calibration": "scene_calibration",
    "lifecycle": "scene_lifecycle_log",
}


# ── 基础 ────────────────────────────────────────────────────────────────


def _rel(path: Path) -> str:
    """相对 ROOT 展示；注入/外部路径时回退为绝对路径."""
    try:
        return str(path.relative_to(_ROOT))
    except ValueError:
        return str(path)


def _connect(path: Path | None = None) -> sqlite3.Connection:
    # path 在调用时解析 (而非默认参数绑定), 便于测试注入与后续路径迁移
    conn = sqlite3.connect(str(path or DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for key, table in TABLES.items():
        if not _table_exists(conn, table):
            counts[key] = 0
            continue
        counts[key] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return counts


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


def _dump(rows: list[dict[str, Any]]) -> bytes:
    """确定性导出: 不含时间戳 (git 记录变更时间), 内容不变则字节不变."""
    doc = {
        "schema": EXPORT_SCHEMA,
        "note": DERIVED_NOTE,
        "rows": rows,
    }
    return (json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode()


# ── L1 export ───────────────────────────────────────────────────────────


def export() -> dict[str, Any]:
    """DB → L1 确定性导出（幂等；execution 按日聚合防膨胀）."""
    if not DB_PATH.is_file():
        print(f"❌ DB 不存在: {DB_PATH}")
        return {"ok": False, "reason": "db_missing"}
    conn = _connect()
    try:
        summary: dict[str, Any] = {}
        if _table_exists(conn, TABLES["calibration"]):
            rows = [dict(r) for r in conn.execute(
                f"SELECT * FROM {TABLES['calibration']} ORDER BY scene_id, window_days, id"
            )]
            _atomic_write(EXPORT_DIR / "calibration.json", _dump(rows))
            summary["calibration"] = len(rows)
        if _table_exists(conn, TABLES["lifecycle"]):
            rows = [dict(r) for r in conn.execute(
                f"SELECT * FROM {TABLES['lifecycle']} ORDER BY created_at, id"
            )]
            _atomic_write(EXPORT_DIR / "lifecycle.json", _dump(rows))
            summary["lifecycle"] = len(rows)
        if _table_exists(conn, TABLES["execution"]):
            rows = [dict(r) for r in conn.execute(
                f"""SELECT substr(created_at,1,10) AS day, scene_id,
                           COUNT(*) AS runs,
                           SUM(success) AS successes,
                           ROUND(AVG(confidence), 4) AS avg_confidence,
                           SUM(duration_ms) AS total_duration_ms
                    FROM {TABLES['execution']}
                    GROUP BY day, scene_id ORDER BY day, scene_id"""
            )]
            _atomic_write(EXPORT_DIR / "execution-daily.json", _dump(rows))
            summary["execution_daily"] = len(rows)
        return {"ok": True, "exported": summary, "dir": _rel(EXPORT_DIR)}
    finally:
        conn.close()


# ── L2 backup ───────────────────────────────────────────────────────────


def backup(keep: int = BACKUP_KEEP) -> dict[str, Any]:
    """sqlite3 在线备份 → runtime/backups/，保留最近 keep 份."""
    if not DB_PATH.is_file():
        print(f"❌ DB 不存在: {DB_PATH}")
        return {"ok": False, "reason": "db_missing"}
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    target = BACKUP_DIR / f"scene-metrics-{stamp}.db"
    src = _connect()
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)  # 在线备份 API, WAL 安全 (不用 cp)
        finally:
            dst.close()
    finally:
        src.close()
    # 保留策略: 按名字排序 (YYYYMMDD) 只留最近 keep 份
    existing = sorted(BACKUP_DIR.glob("scene-metrics-*.db"))
    pruned = []
    for old in existing[:-keep] if len(existing) > keep else []:
        old.unlink()
        pruned.append(old.name)
    return {"ok": True, "backup": target.name, "kept": len(existing) - len(pruned),
            "pruned": pruned}


# ── L3 verify ───────────────────────────────────────────────────────────


def _load_baseline() -> dict[str, Any]:
    try:
        return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def verify() -> dict[str, Any]:
    """行数对比基线；显著下跌 → exit 1；否则刷新基线.

    首次运行（无基线）不告警, 只建立基线.
    检测到下跌时**保留旧基线** (避免污染后续判定).
    """
    if not DB_PATH.is_file():
        print(f"❌ scene history 缺失: {DB_PATH} 不存在")
        return {"ok": False, "reason": "db_missing"}
    conn = _connect()
    try:
        current = _counts(conn)
    finally:
        conn.close()

    baseline = _load_baseline()
    prev = baseline.get("row_counts")
    if not isinstance(prev, dict):
        _atomic_write(BASELINE_PATH, (json.dumps({
            "schema": "scene-history-baseline/v1",
            "note": DERIVED_NOTE,
            "checked_at": datetime.now(UTC).isoformat(),
            "row_counts": current,
        }, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode())
        return {"ok": True, "first_run": True, "baseline": current}

    drops = []
    for key, now in current.items():
        was = int(prev.get(key, 0))
        if was > 0 and now <= was * DROP_RATIO:
            drops.append({"table": key, "was": was, "now": now})
    if drops:
        print("❌ scene history 行数异常下跌 (静默丢失已变为显式失败):")
        for d in drops:
            print(f"   - {d['table']}: {d['was']} → {d['now']}")
        print("   恢复: python3 bin/ssot/scene-history.py restore")
        return {"ok": False, "reason": "row_count_drop", "drops": drops, "baseline": prev}

    _atomic_write(BASELINE_PATH, (json.dumps({
        "schema": "scene-history-baseline/v1",
        "note": DERIVED_NOTE,
        "checked_at": datetime.now(UTC).isoformat(),
        "row_counts": current,
    }, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode())
    return {"ok": True, "row_counts": current, "baseline_before": prev}


# ── restore ─────────────────────────────────────────────────────────────


def _load_export(name: str) -> list[dict[str, Any]]:
    path = EXPORT_DIR / name
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = doc.get("rows")
    return rows if isinstance(rows, list) else []


def restore(force: bool = False) -> dict[str, Any]:
    """L1 导出 → 补齐 DB 中缺失的行（部分丢失也恢复；force 则先清空目标表）.

    判定为"需要恢复": 任一表的当前行数 < 导出行数（含 0 行为空的场景）。
    INSERT OR IGNORE 保证幂等与不覆盖现有行。
    """
    if not EXPORT_DIR.is_dir():
        print(f"❌ 无导出可恢复: {EXPORT_DIR} 不存在")
        return {"ok": False, "reason": "export_missing"}

    exports = {
        "calibration": _load_export("calibration.json"),
        "lifecycle": _load_export("lifecycle.json"),
    }
    if not any(exports.values()):
        print("❌ 导出为空, 无可恢复内容")
        return {"ok": False, "reason": "export_empty"}

    if DB_PATH.is_file() and not force:
        conn = _connect()
        try:
            current = _counts(conn)
        finally:
            conn.close()
        missing = {k: len(v) - current.get(k, 0) for k, v in exports.items() if v}
        if all(delta <= 0 for delta in missing.values()):
            print(f"ℹ️  DB 无缺失, 无需恢复 (当前 {current}; 强制: --force)")
            return {"ok": True, "skipped": True, "row_counts": current}

    conn = _connect()
    restored: dict[str, int] = {}
    try:
        if force:
            for table in TABLES.values():
                if _table_exists(conn, table):
                    conn.execute(f"DELETE FROM {table}")
        for key, rows in exports.items():
            if not rows:
                continue
            table = TABLES[key]
            if not _table_exists(conn, table):
                continue
            cols = [d[1] for d in conn.execute(f"PRAGMA table_info({table})")]
            keys = [c for c in rows[0].keys() if c in cols and c != "id"]
            sql = (f"INSERT OR IGNORE INTO {table} "
                   f"({','.join(keys)}) VALUES ({','.join('?' * len(keys))})")
            conn.executemany(sql, [[r.get(k) for k in keys] for r in rows])
            restored[key] = len(rows)
        conn.commit()
        counts = _counts(conn)
    finally:
        conn.close()
    return {"ok": True, "restored": restored, "row_counts": counts}


# ── status ──────────────────────────────────────────────────────────────


def status() -> dict[str, Any]:
    counts = {}
    if DB_PATH.is_file():
        conn = _connect()
        try:
            counts = _counts(conn)
        finally:
            conn.close()
    exports = sorted(p.name for p in EXPORT_DIR.glob("*.json")) if EXPORT_DIR.is_dir() else []
    backups = sorted((p.name, p.stat().st_size) for p in BACKUP_DIR.glob("scene-metrics-*.db")) \
        if BACKUP_DIR.is_dir() else []
    baseline = _load_baseline().get("row_counts", {})
    return {"db": _rel(DB_PATH) if DB_PATH.is_file() else None,
            "row_counts": counts, "baseline": baseline,
            "export_dir": _rel(EXPORT_DIR), "exports": exports,
            "backups": [{"name": n, "bytes": s} for n, s in backups[-3:]],
            "backup_count": len(backups)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("export", help="DB → L1 持久导出 (git 跟踪)")
    sub.add_parser("backup", help="DB → L2 本地快照 (保留 14)")
    sub.add_parser("verify", help="行数暴跌检测 (失败 exit 1)")
    rp = sub.add_parser("restore", help="L1 导出 → 重建 DB")
    rp.add_argument("--force", action="store_true", help="清空目标表后恢复")
    sub.add_parser("status", help="人读摘要")
    args = parser.parse_args(argv)
    command = args.command or "status"

    if command == "export":
        result = export()
    elif command == "backup":
        result = backup()
    elif command == "verify":
        result = verify()
    elif command == "restore":
        result = restore(force=args.force)
    else:
        result = status()
    print(json.dumps(result, ensure_ascii=False, indent=1, default=str))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
