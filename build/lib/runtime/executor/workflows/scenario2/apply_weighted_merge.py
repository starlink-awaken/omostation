# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""加权合并 — 将 Council 决议（权重/置信度）写回 FactGraph metadata。"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[6]
DB_PATH = str(PROJECT_ROOT / "data" / "db" / "organs" / "memory" / "fact_graph.db")
REPORT_DIR = PROJECT_ROOT / "data" / "scenario2"


def load_and_weight(db_path: str | None = None) -> list[dict[str, Any]]:
    """从 FactGraph 读取 scenario2 冲突事实，计算权重。"""
    if db_path is None:
        db_path = DB_PATH

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sub, pred, obj, metadata
        FROM fact_triples
        WHERE source_node_id = 'scenario2'
        ORDER BY sub, pred
    """)
    rows = cursor.fetchall()
    conn.close()

    # 按 (sub, pred) 分组
    groups: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (r[1], r[2])
        if key not in groups:
            groups[key] = []
        try:
            meta = json.loads(r[4]) if isinstance(r[4], str) else r[4]
        except (json.JSONDecodeError, TypeError):
            meta = {}
        groups[key].append({
            "id": r[0],
            "sub": r[1],
            "pred": r[2],
            "obj": r[3],
            "metadata": meta,
        })

    # 每组内计算权重
    results = []
    for key, facts in groups.items():
        sub, pred = key
        total_conf = sum(f["metadata"].get("confidence", 0.5) for f in facts)
        for f in facts:
            weight = (
                round(f["metadata"].get("confidence", 0.5) / total_conf, 4)
                if total_conf > 0
                else 0.5
            )
            results.append({
                "id": f["id"],
                "sub": sub,
                "pred": pred,
                "obj": f["obj"],
                "weight": weight,
                "original_confidence": f["metadata"].get("confidence", 0.5),
            })

    return results


def apply_weights(conn: sqlite3.Connection, results: list[dict[str, Any]]) -> dict:
    """将加权结果写回 FactGraph 的 metadata 字段。"""
    cursor = conn.cursor()
    stats: dict[str, Any] = {"updated": 0, "skipped": 0, "errors": []}

    for r in results:
        cursor.execute("SELECT metadata FROM fact_triples WHERE id = ?", (r["id"],))
        row = cursor.fetchone()
        if not row:
            stats["skipped"] += 1
            continue

        try:
            meta = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        except (json.JSONDecodeError, TypeError):
            meta = {}

        meta["council_weight"] = r["weight"]
        meta["council_resolved"] = True
        meta["council_resolved_at"] = datetime.now(UTC).isoformat()

        cursor.execute(
            "UPDATE fact_triples SET metadata = ? WHERE id = ?",
            (json.dumps(meta, ensure_ascii=False), r["id"]),
        )
        stats["updated"] += 1

    conn.commit()
    return stats


def generate_report(results: list[dict[str, Any]], stats: dict) -> str:
    timestamp = datetime.now(UTC).isoformat()
    lines = [
        "# 加权合并报告",
        "",
        f"**时间:** {timestamp}",
        f"**更新:** {stats['updated']} 条",
        f"**跳过:** {stats['skipped']} 条",
        "",
        "## 权重分配",
        "",
        "| 实体 | 谓词 | 断言 | 原始置信度 | Council权重 |",
        "|------|------|------|-----------|-------------|",
    ]
    for r in results:
        obj_short = r["obj"][:40]
        lines.append(
            f"| {r['sub']} | {r['pred']} | {obj_short} | {r['original_confidence']} | {r['weight']} |"
        )

    lines.append(f"\n成功更新 {stats['updated']} 条事实的 Council 权重。")
    return "\n".join(lines)


def main() -> None:
    results = load_and_weight()
    if not results:
        print("未找到需要合并的冲突事实 (source_node_id='scenario2')。")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        stats = apply_weights(conn, results)
    finally:
        conn.close()

    report = generate_report(results, stats)
    report_path = REPORT_DIR / "weighted_merge_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\n合并报告: {report_path}")


if __name__ == "__main__":
    main()
