# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""冲突检测 — 扫描 FactGraph 中同一实体+谓词的矛盾断言。"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[6]
DB_PATH = str(PROJECT_ROOT / "data" / "db" / "organs" / "memory" / "fact_graph.db")


def get_conflict_via_definitions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """通过注入时的 conflict 元组来精确检测（基于场景内冲突对）。"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sub, pred, obj, metadata, source_node_id
        FROM fact_triples
        WHERE source_node_id = 'scenario2'
        ORDER BY sub, pred, timestamp
    """)
    rows = cursor.fetchall()

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
            "id": r[0], "sub": r[1], "pred": r[2], "obj": r[3],
            "source": meta.get("source", "unknown"),
            "confidence": meta.get("confidence", 0.5),
        })

    conflicts = []
    for key, facts in groups.items():
        sub, pred = key
        unique_objs = {f["obj"] for f in facts}
        if len(unique_objs) >= 2:
            conflicts.append({
                "sub": sub, "pred": pred,
                "fact_count": len(facts),
                "unique_statements": len(unique_objs),
                "facts": sorted(facts, key=lambda x: x.get("confidence", 0), reverse=True),
            })

    return conflicts


def get_all_conflicts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """通用冲突检测：扫描全库所有 (sub, pred) 组合。"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sub, pred, COUNT(DISTINCT obj) as distinct_objs
        FROM fact_triples
        GROUP BY sub, pred
        HAVING distinct_objs >= 2
        ORDER BY distinct_objs DESC
    """)
    candidates = cursor.fetchall()

    conflicts = []
    for sub, pred, _distinct_count in candidates:
        cursor.execute("""
            SELECT id, sub, pred, obj, metadata, source_node_id
            FROM fact_triples
            WHERE sub = ? AND pred = ?
            ORDER BY timestamp DESC
        """, (sub, pred))
        facts = cursor.fetchall()
        resolved: list[dict] = []
        for f in facts:
            try:
                meta = json.loads(f[4]) if isinstance(f[4], str) else f[4]
            except (json.JSONDecodeError, TypeError):
                meta = {}
            resolved.append({
                "id": f[0], "sub": f[1], "pred": f[2], "obj": f[3],
                "source": meta.get("source", "unknown"),
                "confidence": meta.get("confidence", 0.5),
            })

        unique_objs = {f["obj"] for f in resolved}
        if len(unique_objs) >= 2:
            conflicts.append({
                "sub": sub, "pred": pred,
                "fact_count": len(resolved),
                "unique_statements": len(unique_objs),
                "facts": sorted(resolved, key=lambda x: x.get("confidence", 0), reverse=True),
            })

    return conflicts


def generate_report(conflicts: list[dict[str, Any]], report_type: str = "scenario") -> str:
    timestamp = datetime.now(UTC).isoformat()
    lines = [
        "# 冲突检测报告",
        "",
        f"**时间:** {timestamp}",
        f"**类型:** {'场景特定' if report_type == 'scenario' else '全库扫描'}",
        f"**冲突数:** {len(conflicts)}",
        "",
        "---",
        "",
    ]

    if not conflicts:
        lines.append("✅ 未检测到事实冲突。")
        return "\n".join(lines)

    for i, c in enumerate(conflicts, 1):
        lines.append(f"## 冲突 {i}: {c['sub']} — {c['pred']}")
        lines.append("")
        lines.append(f"- 断言数: {c['fact_count']}")
        lines.append(f"- 不同陈述: {c['unique_statements']}")
        lines.append("")
        lines.append("| # | 断言 | 来源 | 置信度 |")
        lines.append("|---|------|------|--------|")
        for j, f in enumerate(c["facts"], 1):
            obj_short = f["obj"][:60]
            lines.append(f"| {j} | {obj_short} | {f['source']} | {f['confidence']} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    import sys as _sys
    mode = _sys.argv[1] if len(_sys.argv) > 1 else "scenario"

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    if mode == "scenario":
        conflicts = get_conflict_via_definitions(conn)
    else:
        conflicts = get_all_conflicts(conn)

    conn.close()

    report = generate_report(conflicts, report_type=mode)
    report_path = PROJECT_ROOT / "data" / "scenario2" / "conflict_detection_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
