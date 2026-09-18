#!/usr/bin/env python3
"""生产校准库纯度检查 — 拒绝测试夹具伪装成晋升证据.

事故背景 (2026-09-18 实证):
  tests/scene_v2/test_calibration_engine.py 用 subprocess 跑**生产**
  calibration-engine.py, cwd=ROOT, 零隔离 → 夹具 scene_id 被写进生产
  `data/scene-metrics.db`:
      gate-test-scene        35 samples  → check-gates 返回 eligible:true
      test-scene / empty-scene-xyz / integration-test-scene
  48 条 execution 中 37 条是夹具。校准库是信任平面的证据源, 夹具样本满足
  "30 samples" 晋升门禁 = 伪造证据 (违反真实性红线)。

两个信号 (不另立规则集, 复用既有真值源):
  1. 夹具 ID       — 显式 denylist + 通用夹具模式 (确定性, 零漏报已知项)
  2. 未注册 ID     — 不在 .omo/_truth/scenarios/v3/ 的 scene_id 集合内
                     (真值源 = 场景注册表, 与 scene-v3-registry 同源)

退出码: 发现夹具 → 1 (硬失败); 仅有未注册 ID → 0 (报告, 需人工判定是
夹具还是改名遗留). CI 无 data/ (gitignored) → 天然跳过, 本检查面向本地/ops.

用法:
    python3 bin/gac/check-scene-metrics-purity.py            # 报告
    python3 bin/gac/check-scene-metrics-purity.py --json
    python3 bin/gac/check-scene-metrics-purity.py --purge --yes   # 清理夹具行
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_DIR = _ROOT / ".omo" / "_truth" / "scenarios" / "v3"

# 夹具 ID 显式清单 (实证来源: tests/scene_v2/, 2026-09-18)
FIXTURE_IDS = {
    "test-scene", "gate-test-scene", "empty-scene-xyz",
    "integration-test-scene", "dummy-scene", "fixture-scene",
}

# 通用夹具模式 (保守: 只匹配明显非生产 naming)
FIXTURE_PATTERNS = [
    re.compile(r"^test[-_]"),
    re.compile(r"[-_]test[-_]?scene$"),
    re.compile(r"^empty[-_]"),
    re.compile(r"^gate[-_]test"),
    re.compile(r"^fixture[-_]"),
    re.compile(r"^dummy[-_]"),
]

TABLES = ("scene_execution", "scene_calibration")


def _resolve_db() -> Path:
    import os
    override = os.environ.get("SCENE_METRICS_DB")
    if override:
        return Path(override).expanduser().resolve()
    return _ROOT / "data" / "scene-metrics.db"


def load_registered_ids() -> set[str]:
    """场景注册表的 scene_id 集合 (真值源)."""
    ids: set[str] = set()
    if not REGISTRY_DIR.is_dir():
        return ids
    for path in REGISTRY_DIR.glob("*.yaml"):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in re.finditer(r"^\s*(?:scene_)?id:\s*(\S+)\s*$", text, re.M):
            value = m.group(1).strip().strip("'\"")
            if value.startswith("scene-") or value.startswith("scene_"):
                ids.add(value)
    return ids


def is_fixture(scene_id: str) -> bool:
    if scene_id in FIXTURE_IDS:
        return True
    return any(p.search(scene_id) for p in FIXTURE_PATTERNS)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def audit(db: Path | None = None) -> dict:
    db = db or _resolve_db()
    if not db.is_file():
        return {"db": str(db), "exists": False, "status": "no_db",
                "fixtures": [], "unregistered": []}

    registered = load_registered_ids()
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        per_table: dict[str, dict[str, int]] = {}
        for table in TABLES:
            if not _table_exists(conn, table):
                continue
            rows = conn.execute(
                f"SELECT scene_id, COUNT(*) AS n FROM {table} GROUP BY scene_id"
            ).fetchall()
            per_table[table] = {r["scene_id"]: r["n"] for r in rows}
    finally:
        conn.close()

    all_ids = sorted({sid for counts in per_table.values() for sid in counts})
    fixtures = []
    unregistered = []
    for sid in all_ids:
        detail = {t: per_table.get(t, {}).get(sid, 0) for t in per_table}
        total = sum(detail.values())
        if is_fixture(sid):
            fixtures.append({"scene_id": sid, "rows": total, "tables": detail})
        elif registered and sid not in registered:
            unregistered.append({"scene_id": sid, "rows": total, "tables": detail})

    total_rows = sum(sum(c.values()) for c in per_table.values())
    fixture_rows = sum(f["rows"] for f in fixtures)
    return {
        "db": str(db),
        "exists": True,
        "status": "polluted" if fixtures else ("unregistered" if unregistered else "clean"),
        "total_rows": total_rows,
        "fixture_rows": fixture_rows,
        "fixture_ratio": round(fixture_rows / total_rows, 4) if total_rows else 0.0,
        "fixtures": fixtures,
        "unregistered": unregistered,
        "registered_ids": len(registered),
    }


def purge(db: Path, result: dict, *, yes: bool) -> dict:
    """删除夹具行。先备份（复用 scene-history backup），需 --yes 确认."""
    if not result["fixtures"]:
        return {"ok": True, "purged": [], "reason": "nothing_to_purge"}
    if not yes:
        return {"ok": False, "reason": "confirmation_required",
                "hint": "加 --yes 才会删除; 另会先自动备份"}

    ids = [f["scene_id"] for f in result["fixtures"]]
    backup_result: dict = {"ok": False, "reason": "skipped"}
    history = _ROOT / "bin" / "ssot" / "scene-history.py"
    if history.is_file():
        proc = subprocess.run(
            [sys.executable, str(history), "backup"],
            capture_output=True, text=True, cwd=str(_ROOT),
        )
        backup_result = {"ok": proc.returncode == 0, "stdout": proc.stdout.strip()[:200]}

    conn = sqlite3.connect(str(db), timeout=10)
    removed: dict[str, int] = {}
    try:
        for table in TABLES:
            if not _table_exists(conn, table):
                continue
            n = 0
            for sid in ids:
                cur = conn.execute(f"DELETE FROM {table} WHERE scene_id = ?", (sid,))
                n += cur.rowcount or 0
            removed[table] = n
        conn.commit()
    finally:
        conn.close()
    return {"ok": True, "backup": backup_result, "purged_ids": ids, "removed": removed}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--purge", action="store_true", help="删除夹具行 (需 --yes)")
    ap.add_argument("--yes", action="store_true", help="确认执行破坏性清理")
    ap.add_argument("--db", type=str, help="覆盖校准库路径")
    args = ap.parse_args(argv)

    db = Path(args.db).expanduser().resolve() if args.db else _resolve_db()
    result = audit(db)

    if args.purge:
        purge_result = purge(db, result, yes=args.yes)
        result = {**result, "purge": purge_result}
        if purge_result.get("ok"):
            result = {**result, **audit(db), "purge": purge_result}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        if not result["exists"]:
            print(f"ℹ️  无校准库 ({result['db']}) — 跳过 (CI 无 data/, 属预期)")
        elif result["status"] == "clean":
            print(f"✅ 校准库纯净: {result['total_rows']} 行, 无夹具/未注册 scene_id")
        else:
            print(f"⚠️  校准库 {result['db']}")
            print(f"   总行数 {result['total_rows']}, 夹具行 {result['fixture_rows']} "
                  f"({result['fixture_ratio']:.1%})")
            for f in result["fixtures"]:
                print(f"   ❌ 夹具 {f['scene_id']}: {f['rows']} 行 {f['tables']}")
            for u in result["unregistered"]:
                print(f"   ⚠️  未注册 {u['scene_id']}: {u['rows']} 行 "
                      f"(夹具? 还是改名遗留?)")
            if result["fixtures"]:
                print("\n   清理: python3 bin/gac/check-scene-metrics-purity.py --purge --yes")

    # 夹具 → 硬失败; 仅未注册 → 报告但不失败
    return 1 if result.get("fixtures") else 0


if __name__ == "__main__":
    raise SystemExit(main())
