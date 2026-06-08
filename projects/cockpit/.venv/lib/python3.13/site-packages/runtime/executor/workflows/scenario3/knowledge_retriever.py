# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""多源知识检索器 — 组合 FactGraph 查询 + 原始数据源重解析。"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[6]
DB_PATH = str(PROJECT_ROOT / "data" / "db" / "organs" / "memory" / "fact_graph.db")
PERSONAL_DATA = {
    "wechat": PROJECT_ROOT / "data" / "personal_ingest" / "wechat_parsed.jsonld",
    "notes": PROJECT_ROOT / "data" / "personal_ingest" / "notes_parsed.jsonld",
    "bookmarks": PROJECT_ROOT / "data" / "personal_ingest" / "bookmarks_parsed.jsonld",
}


def query_factgraph(conn: sqlite3.Connection, topics: list[str], limit: int = 50) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    seen_ids: set[str] = set()
    results = []

    for topic in topics:
        q = topic.lower()
        cursor.execute("""
            SELECT id, sub, pred, obj, metadata, source_node_id
            FROM fact_triples
            WHERE LOWER(sub) LIKE ? OR LOWER(obj) LIKE ? OR LOWER(pred) LIKE ?
            LIMIT ?
        """, (f"%{q}%", f"%{q}%", f"%{q}%", limit))
        rows = cursor.fetchall()

        for r in rows:
            if r[0] in seen_ids:
                continue
            seen_ids.add(r[0])
            try:
                meta = json.loads(r[4]) if isinstance(r[4], str) else r[4]
            except (json.JSONDecodeError, TypeError):
                meta = {}
            results.append({
                "id": r[0], "sub": r[1], "pred": r[2], "obj": r[3],
                "source": meta.get("source", "unknown"),
                "confidence": meta.get("confidence", 0.5),
                "council_weight": meta.get("council_weight"),
                "source_node": r[5],
            })

    return results


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    """Generate character n-grams from text."""
    text = text.lower()
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def _ngram_similarity(a: str, b: str, n: int = 3) -> float:
    """Compute Jaccard similarity of character n-grams between two strings."""
    if not a or not b:
        return 0.0
    a_lower = a.lower()
    b_lower = b.lower()

    # Direct substring match → high similarity
    if a_lower in b_lower or b_lower in a_lower:
        return 0.95

    # Chinese-friendly: share common characters?
    common_chars = len(set(a_lower) & set(b_lower))
    total_chars = max(len(set(a_lower)), len(set(b_lower)))
    char_overlap = common_chars / total_chars if total_chars > 0 else 0
    if char_overlap > 0.8:
        return 0.85

    # N-gram Jaccard similarity
    grams_a = _char_ngrams(a_lower, n)
    grams_b = _char_ngrams(b_lower, n)

    if not grams_a or not grams_b:
        return 0.0

    intersection = grams_a & grams_b
    union = grams_a | grams_b

    # Weighted: bi-gram + tri-gram combined
    grams_a_b = _char_ngrams(a_lower, 2)
    grams_b_b = _char_ngrams(b_lower, 2)
    intersect_b = grams_a_b & grams_b_b
    union_b = grams_a_b | grams_b_b

    jac_3 = len(intersection) / len(union) if union else 0
    jac_2 = len(intersect_b) / len(union_b) if union_b else 0

    return 0.4 * jac_2 + 0.6 * jac_3


def ranked_query(
    conn: sqlite3.Connection,
    query: str,
    limit: int = 20,
    min_score: float = 0.15,
) -> list[dict[str, Any]]:
    """语义排序检索 — 先用 LIKE 召回，再用 n-gram 排序。

    相比纯 LIKE 匹配:
    - "Rust学习" 能匹配 "学习Rust笔记"（字符重叠度计算）
    - "Go编程" 能匹配 "Go并发编程"
    - 返回结果按相关性降序排列
    """
    # 1. 宽召回：用单个字符匹配兜底
    cursor = conn.cursor()
    q = query.lower()

    # Build a broad recall query using character-level matching
    # This catches cases LIKE misses (e.g., different word order)
    seen_ids: set[str] = set()
    candidates: list[dict[str, Any]] = []

    # Method 1: LIKE on individual characters + whole query
    like_patterns = [f"%{q}%"]
    # Split Chinese query into individual characters for broader recall
    for ch in q:
        if ch.strip():
            like_patterns.append(f"%{ch}%")

    for pattern in like_patterns[:5]:  # Limit to 5 patterns max
        cursor.execute("""
            SELECT id, sub, pred, obj, metadata, source_node_id
            FROM fact_triples
            WHERE LOWER(sub) LIKE ? OR LOWER(obj) LIKE ? OR LOWER(pred) LIKE ?
            LIMIT ?
        """, (pattern, pattern, pattern, limit * 2))

        for r in cursor.fetchall():
            if r[0] in seen_ids:
                continue
            seen_ids.add(r[0])
            try:
                meta = json.loads(r[4]) if isinstance(r[4], str) else r[4]
            except (json.JSONDecodeError, TypeError):
                meta = {}
            candidates.append({
                "id": r[0], "sub": r[1], "pred": r[2], "obj": r[3],
                "source": meta.get("source", "unknown"),
                "confidence": meta.get("confidence", 0.5),
                "council_weight": meta.get("council_weight"),
            })

    # 2. 排序
    scored = []
    for c in candidates:
        sub_score = _ngram_similarity(query, c["sub"])
        obj_score = _ngram_similarity(query, c["obj"])
        pred_score = _ngram_similarity(query, c["pred"])
        combined = max(sub_score, obj_score, pred_score)
        c["similarity_score"] = round(combined, 4)
        if combined >= min_score:
            scored.append(c)

    # 3. 按分数降序排列
    scored.sort(key=lambda x: x["similarity_score"], reverse=True)
    return scored[:limit]


def format_ranked_results(results: list[dict], query: str) -> str:
    """格式化排序结果。"""
    lines = [
        f"## 语义检索: '{query}'",
        "",
        "| 分数 | 实体 | 谓词 | 内容 |",
        "|------|------|------|------|",
    ]
    for r in results[:15]:
        score = r.get("similarity_score", 0)
        bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
        obj_short = r["obj"][:40]
        lines.append(f"| {score:.3f} {bar} | {r['sub']} | {r['pred']} | {obj_short} |")
    return "\n".join(lines)


def scan_raw_sources(topics: list[str]) -> dict[str, list[dict]]:
    raw_results: dict[str, list[dict]] = {"wechat": [], "notes": [], "bookmarks": []}

    for source_name, path in PERSONAL_DATA.items():
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            facts = data.get("facts", [])
            for fact in facts:
                content = json.dumps(fact, ensure_ascii=False).lower()
                if any(t.lower() in content for t in topics):
                    raw_results[source_name].append(fact)
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    return raw_results


def retrieve(question: str, topics: list[str] | None = None) -> dict[str, Any]:
    if topics is None:
        import re
        stop_words = {"分析", "总结", "生成", "查询", "检索", "比较", "我的", "什么", "如何",
                      "哪些", "这个", "那个", "一个", "可以", "进行", "使用", "需要",
                      "对", "的", "了"}
        text = re.sub(r"([一-鿿])([和与的在了是对有把被让从到])", r"\1 \2", question)
        words = re.findall(r"[一-鿿]+|[a-zA-Z0-9_]+", text)
        words = [w for w in words if w not in stop_words and len(w) >= 2]
        extra = []  # type: ignore[var-annotated]
        for w in list(words):
            if len(w) > 4:
                extra.extend(w[i : i + 2] for i in range(len(w) - 1))
                extra.extend(w[i : i + 3] for i in range(len(w) - 2))
        words += extra
        topics = list(dict.fromkeys(words)) or [question]

    print(f"检索主题: {topics}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        graph_results = query_factgraph(conn, topics)
    finally:
        conn.close()
    print(f"  FactGraph 命中: {len(graph_results)} 条")

    raw_results = scan_raw_sources(topics)
    raw_total = sum(len(v) for v in raw_results.values())
    print(f"  原始数据源命中: {raw_total} 条")

    # 按实体分类
    entities: dict[str, dict] = {}
    for fact in graph_results:
        sub = fact["sub"]
        if sub not in entities:
            entities[sub] = {"entity": sub, "facts": [], "sources": set(), "council_weights": []}
        entities[sub]["facts"].append(fact)
        entities[sub]["sources"].add(fact.get("source", "unknown"))
        if fact.get("council_weight") is not None:
            entities[sub]["council_weights"].append(fact["council_weight"])

    return {
        "question": question,
        "topics": topics,
        "total_graph_hits": len(graph_results),
        "total_raw_hits": raw_total,
        "graph_results": graph_results,
        "raw_sources": {k: {"count": len(v)} for k, v in raw_results.items()},
        "entities": {k: {
            "entity": v["entity"],
            "fact_count": len(v["facts"]),
            "sources": list(v["sources"]),
            "has_council_weights": len(v["council_weights"]) > 0,
        } for k, v in entities.items()},
    }


def format_retrieval(result: dict[str, Any]) -> str:
    lines = [
        "# 多源知识检索结果",
        "",
        f"**问题:** {result['question']}",
        f"**检索主题:** {', '.join(result['topics'])}",
        f"**FactGraph 命中:** {result['total_graph_hits']} 条",
        f"**原始数据源命中:** {result['total_raw_hits']} 条",
        "",
        "## 实体分布",
        "",
        "| 实体 | 事实数 | 来源 | Council权重 |",
        "|------|--------|------|-------------|",
    ]
    for name, ent in sorted(result.get("entities", {}).items()):
        cw = "✅" if ent.get("has_council_weights") else "—"
        sources = ", ".join(ent["sources"][:3])
        lines.append(f"| {name} | {ent['fact_count']} | {sources} | {cw} |")

    lines.extend([
        "",
        "## 详细事实 (前15条)",
        "",
        "| 实体 | 谓词 | 内容 | 来源 | 置信度 |",
        "|------|------|------|------|--------|",
    ])
    for fact in result["graph_results"][:15]:
        obj_short = fact["obj"][:50]
        lines.append(f"| {fact['sub']} | {fact['pred']} | {obj_short} | {fact['source']} | {fact['confidence']} |")

    return "\n".join(lines)


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "分析我对编程语言的学习模式"
    result = retrieve(question)
    print(format_retrieval(result))

    output = PROJECT_ROOT / "data" / "scenario3" / "retrieval_result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {output}")


if __name__ == "__main__":
    main()
