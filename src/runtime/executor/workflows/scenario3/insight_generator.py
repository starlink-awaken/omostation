# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""洞察生成器 — 基于检索结果生成结构化洞察 + 图谱更新。"""
from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[6]
DB_PATH = str(PROJECT_ROOT / "data" / "db" / "organs" / "memory" / "fact_graph.db")


def analyze_facts(facts: list[dict[str, Any]], original_question: str) -> dict[str, Any]:
    """分析事实列表，提取洞察。

    分析维度:
    - 实体覆盖范围
    - 置信度分布
    - 来源多样性
    - 矛盾检测
    - 关系网络
    """
    unique_entities = {f["sub"] for f in facts}
    unique_sources = {f.get("source", "unknown") for f in facts}

    confidences = [f.get("confidence", 0.5) for f in facts]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    high_conf = sum(1 for c in confidences if c >= 0.8)
    low_conf = sum(1 for c in confidences if c < 0.6)

    # 矛盾检测
    pairs: dict[tuple[str, str], set[str]] = {}
    for f in facts:
        key = (f["sub"], f["pred"])
        if key not in pairs:
            pairs[key] = set()
        pairs[key].add(f["obj"])
    conflicts = sum(1 for v in pairs.values() if len(v) >= 2)

    # 主题聚类
    topic_clusters: dict[str, list[dict]] = {}
    for f in facts:
        sub = f["sub"]
        if sub not in topic_clusters:
            topic_clusters[sub] = []
        topic_clusters[sub].append(f)

    # 关系发现：检查事实间的关系
    relationships: list[dict] = []
    entity_list = list(unique_entities)
    for i in range(len(entity_list)):
        for j in range(i + 1, len(entity_list)):
            e1, e2 = entity_list[i], entity_list[j]
            for f in facts:
                if f["sub"] == e1 and e2.lower() in f["obj"].lower():
                    relationships.append({
                        "source": e1, "target": e2,
                        "relation": f.get("pred", "related_to"),
                        "evidence": f["obj"][:60],
                    })
                    break

    # 洞察语句生成
    insights = [f"基于对 {len(facts)} 条事实的分析:"]
    if len(unique_entities) >= 3:
        insights.append(f"- 覆盖 {len(unique_entities)} 个独特实体，知识面较广")
    else:
        insights.append(f"- 仅覆盖 {len(unique_entities)} 个实体，知识面有限")
    insights.append(f"- 数据来自 {len(unique_sources)} 个不同来源")
    insights.append(f"- 平均置信度 {avg_confidence:.2f}")
    if high_conf > 0:
        insights.append(f"- 高置信度事实 {high_conf} 条")
    if conflicts > 0:
        insights.append(f"- 发现 {conflicts} 组矛盾事实（需进一步审议）")

    return {
        "question": original_question,
        "total_facts_analyzed": len(facts),
        "unique_entities": list(unique_entities),
        "unique_sources": list(unique_sources),
        "avg_confidence": round(avg_confidence, 3),
        "high_confidence_count": high_conf,
        "low_confidence_count": low_conf,
        "conflict_pairs": conflicts,
        "topic_clusters": list(topic_clusters.keys()),
        "relationships": relationships,
        "insights": "\n".join(insights),
    }


def update_graph(insight: dict[str, Any], db_path: str | None = None) -> dict:
    """将新发现的关系写入 FactGraph。"""
    if db_path is None:
        db_path = DB_PATH

    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    stats = {"relations_added": 0, "skipped": 0}

    for rel in insight.get("relationships", []):
        cursor.execute(
            "SELECT id FROM fact_triples WHERE sub=? AND pred=? AND obj LIKE ?",
            (rel["source"], f"related_to_{rel['relation']}", f"%{rel['target']}%"),
        )
        if cursor.fetchone():
            stats["skipped"] += 1
            continue

        fact_id = str(uuid.uuid4())
        metadata = json.dumps({
            "source": "scenario3_insight_engine",
            "relation": rel["relation"],
            "evidence": rel["evidence"],
            "generated_at": datetime.now(UTC).isoformat(),
        }, ensure_ascii=False)

        iso_ts = datetime.now(UTC).isoformat()
        cursor.execute(
            "INSERT INTO fact_triples (id, sub, pred, obj, metadata, source_node_id, timestamp) VALUES (?,?,?,?,?,?,?)",
            (fact_id, rel["source"], f"related_to_{rel['relation']}", rel["target"],
             metadata, "scenario3_insight", iso_ts),
        )
        stats["relations_added"] += 1

    conn.commit()
    conn.close()
    return stats


def generate_report(insight: dict[str, Any], graph_stats: dict) -> str:
    timestamp = datetime.now(UTC).isoformat()
    lines = [
        "# 洞察分析报告",
        "",
        f"**时间:** {timestamp}",
        f"**问题:** {insight['question']}",
        f"**分析事实数:** {insight['total_facts_analyzed']}",
        "",
        "## 知识覆盖",
        "",
        f"- 独特实体: {', '.join(insight['unique_entities'])}",
        f"- 来源数: {len(insight['unique_sources'])}",
        f"- 实体数: {len(insight['unique_entities'])}",
        "",
        "## 质量评估",
        "",
        f"- 平均置信度: {insight['avg_confidence']}",
        f"- 高置信度(≥0.8): {insight['high_confidence_count']} 条",
        f"- 低置信度(<0.6): {insight['low_confidence_count']} 条",
        f"- 矛盾对: {insight['conflict_pairs']} 组",
        "",
        "## 主题聚类",
        "",
    ]
    for topic in insight.get("topic_clusters", []):
        lines.append(f"- {topic}")

    if insight.get("relationships"):
        lines.extend([
            "",
            "## 新发现关系",
            "",
            "| 源实体 | 目标实体 | 关系 | 证据 |",
            "|--------|---------|------|------|",
        ])
        for rel in insight["relationships"]:
            lines.append(f"| {rel['source']} | {rel['target']} | {rel['relation']} | {rel['evidence']} |")

    lines.extend([
        "",
        "## 洞察总结",
        "",
        insight["insights"],
        "",
        "## 图谱更新",
        "",
        f"- 新增关系: {graph_stats['relations_added']} 条",
        f"- 跳过重复: {graph_stats['skipped']} 条",
        "",
    ])

    return "\n".join(lines)


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "分析我对编程语言的学习模式"

    retrieval_path = PROJECT_ROOT / "data" / "scenario3" / "retrieval_result.json"
    if retrieval_path.exists():
        with open(retrieval_path, encoding="utf-8") as f:
            retrieval = json.load(f)
        print(f"已加载检索结果: {retrieval_path}")
    else:
        print("⚠️ 未找到检索结果文件，尝试直接查询 FactGraph...")
        # 直接查询 FactGraph
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        q = question.lower()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, sub, pred, obj, metadata, source_node_id
            FROM fact_triples
            WHERE LOWER(sub) LIKE ? OR LOWER(obj) LIKE ? OR LOWER(pred) LIKE ?
            LIMIT 50
        """, (f"%{q}%", f"%{q}%", f"%{q}%"))
        rows = cursor.fetchall()
        graph_results = []
        for r in rows:
            try:
                meta = json.loads(r[4]) if isinstance(r[4], str) else r[4]
            except (json.JSONDecodeError, TypeError):
                meta = {}
            graph_results.append({
                "id": r[0], "sub": r[1], "pred": r[2], "obj": r[3],
                "source": meta.get("source", "unknown"),
                "confidence": meta.get("confidence", 0.5),
            })
        conn.close()
        retrieval = {"question": question, "graph_results": graph_results}

    facts = retrieval.get("graph_results", [])
    if not facts:
        print("❌ 无事实可供分析")
        return

    print(f"分析 {len(facts)} 条事实...")
    insight = analyze_facts(facts, question)
    graph_stats = update_graph(insight)
    report = generate_report(insight, graph_stats)

    report_path = PROJECT_ROOT / "data" / "scenario3" / "insight_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    print(report)
    print(f"\n📄 报告: {report_path}")
    print(f"  新增关系: {graph_stats['relations_added']} 条")


if __name__ == "__main__":
    main()
