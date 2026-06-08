# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""跨会话回忆验证 — 语义检索、来源标注、Council权重、时间轴排序。"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[6]
DB_PATH = str(PROJECT_ROOT / "data" / "db" / "organs" / "memory" / "fact_graph.db")
REPORT_DIR = PROJECT_ROOT / "data" / "scenario2"


def query_knowledge(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict[str, Any]]:
    q = query.lower()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, sub, pred, obj, metadata, source_node_id, timestamp
        FROM fact_triples
        WHERE LOWER(sub) LIKE ? OR LOWER(obj) LIKE ? OR LOWER(pred) LIKE ?
        LIMIT ?
    """, (f"%{q}%", f"%{q}%", f"%{q}%", limit))
    rows = cursor.fetchall()

    results = []
    for r in rows:
        try:
            meta = json.loads(r[4]) if isinstance(r[4], str) else r[4]
        except (json.JSONDecodeError, TypeError):
            meta = {}
        results.append({
            "id": r[0], "sub": r[1], "pred": r[2], "obj": r[3],
            "source": meta.get("source", "unknown"),
            "confidence": meta.get("confidence", 0.5),
            "council_weight": meta.get("council_weight"),
            "council_resolved": meta.get("council_resolved", False),
            "timestamp": r[6],
        })
    return results


def query_timeline(conn: sqlite3.Connection, topic: str) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sub, pred, obj, metadata, timestamp
        FROM fact_triples
        WHERE LOWER(sub) LIKE ? AND timestamp IS NOT NULL AND timestamp != ''
        ORDER BY timestamp ASC
    """, (f"%{topic.lower()}%",))
    rows = cursor.fetchall()

    results = []
    for r in rows:
        try:
            meta = json.loads(r[3]) if isinstance(r[3], str) else r[3]
        except (json.JSONDecodeError, TypeError):
            meta = {}
        results.append({
            "sub": r[0], "pred": r[1], "obj": r[2],
            "source": meta.get("source", "unknown"),
            "confidence": meta.get("confidence", 0.5),
            "council_weight": meta.get("council_weight"),
            "timestamp": r[4],
        })
    return results


def run_verification() -> dict[str, Any]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    test_queries = [
        ("Rust学习", "Rust"),
        ("Go并发", "Go"),
        ("Python数据处理", "Python"),
        ("学习计划", "学习计划"),
        ("编程语言推荐", "recommended_use"),
    ]

    query_results = []
    for label, query in test_queries:
        hits = query_knowledge(conn, query)
        query_results.append({
            "label": label, "query": query, "count": len(hits),
            "has_source_annotation": all(bool(h.get("source")) for h in hits) if hits else False,
            "has_council_weight": any(h.get("council_weight") is not None for h in hits),
            "top_hits": [{"sub": h["sub"], "pred": h["pred"], "source": h["source"]} for h in hits[:3]],
        })

    timeline = query_timeline(conn, "Rust")

    conn.close()

    total = len(test_queries)
    hit_count = sum(1 for q in query_results if q["count"] > 0)  # type: ignore[misc, operator]
    hit_rate = hit_count / total if total > 0 else 0
    source_annotated = sum(1 for q in query_results if q.get("has_source_annotation"))
    council_weighted = sum(1 for q in query_results if q.get("has_council_weight"))
    timeline_ordered = True
    if len(timeline) >= 2:
        for i in range(len(timeline) - 1):
            t0 = timeline[i]["timestamp"]
            t1 = timeline[i + 1]["timestamp"]
            if t0 == "N/A" or t1 == "N/A":
                continue
            if isinstance(t0, float) and isinstance(t1, str):
                t0_iso = datetime.fromtimestamp(t0, tz=UTC).isoformat()
                t1_iso = t1
            elif isinstance(t0, str) and isinstance(t1, float):
                t0_iso = t0
                t1_iso = datetime.fromtimestamp(t1, tz=UTC).isoformat()
            elif isinstance(t0, float) and isinstance(t1, float):
                t0_iso = datetime.fromtimestamp(t0, tz=UTC).isoformat()
                t1_iso = datetime.fromtimestamp(t1, tz=UTC).isoformat()
            else:
                t0_iso = str(t0)
                t1_iso = str(t1)
            if t0_iso > t1_iso:
                timeline_ordered = False
                break

    return {
        "query_results": query_results,
        "timeline": timeline,
        "metrics": {
            "total_queries": total, "hit_count": hit_count, "hit_rate": hit_rate,
            "source_annotated_count": source_annotated,
            "council_weighted_count": council_weighted,
            "timeline_ordered": timeline_ordered,
        },
    }


def generate_report(verification: dict[str, Any]) -> str:
    metrics = verification["metrics"]
    timestamp = datetime.now(UTC).isoformat()

    lines = [
        "# 跨会话回忆验证报告",
        "",
        f"**时间:** {timestamp}",
        "",
        "## 查询结果",
        "",
        "| 查询 | 命中数 | 来源标注 | Council权重 | Top命中 |",
        "|------|--------|----------|-------------|---------|",
    ]

    for q in verification["query_results"]:
        top = q["top_hits"][0]["sub"] if q["top_hits"] else "—"
        sa = "✅" if q.get("has_source_annotation") else "❌"
        cw = "✅" if q.get("has_council_weight") else "—"
        lines.append(f"| {q['label']} | {q['count']} | {sa} | {cw} | {top} |")

    lines.extend([
        "",
        "## 指标",
        "",
        "| 指标 | 值 | 标准 | 结果 |",
        "|------|-----|------|------|",
        f"| 查询命中率 | {metrics['hit_rate']:.0%} | ≥80% | {'✅' if metrics['hit_rate'] >= 0.8 else '❌'} |",
        f"| 全部来源标注 | {metrics['source_annotated_count']}/{metrics['total_queries']} | 全部标注 | {'✅' if metrics['source_annotated_count'] == metrics['total_queries'] else '❌'} |",
        f"| Council权重标注 | {metrics['council_weighted_count']}/{metrics['total_queries']} | ≥1查询有权重 | {'✅' if metrics['council_weighted_count'] > 0 else '❌'} |",
        f"| 时间轴排序 | {'是' if metrics['timeline_ordered'] else '否'} | 时间顺序 | {'✅' if metrics['timeline_ordered'] else '⚠️'} |",
        "",
    ])

    if verification["timeline"]:
        lines.extend([
            "## 时间轴: Rust 知识演变",
            "",
            "| 时间 | 来源 | 内容 |",
            "|------|------|------|",
        ])
        for t in verification["timeline"][:10]:
            obj_short = t["obj"][:50]
            lines.append(f"| {t['timestamp']} | {t['source']} | {obj_short} |")

    return "\n".join(lines)


def main() -> None:
    verification = run_verification()
    report = generate_report(verification)

    report_path = REPORT_DIR / "recall_verification_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\n📄 验证报告: {report_path}")


if __name__ == "__main__":
    main()
