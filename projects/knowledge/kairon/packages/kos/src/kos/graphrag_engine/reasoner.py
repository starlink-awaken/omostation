#!/usr/bin/env python3
# ruff: noqa
"""
KOS GraphRAG Reasoner — LLM 驱动的图谱深度推理.

将知识图谱路径 + 文档证据注入 LLM, 生成可解释的推理结果.

Usage:
    from kos.graphrag_reasoner import GraphRAGReasoner

    reasoner = GraphRAGReasoner()
    result = reasoner.reason("夏明星参与的项目的上下游依赖")
"""

from __future__ import annotations

import json
import re
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class GraphRAGReasoner:
    """GraphRAG 深度推理引擎。"""

    def __init__(self, db_path: str | None = None, llm_callable=None):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self._conn = None
        self._llm = llm_callable

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    def reason(self, query: str, max_hops: int = 3, max_evidence: int = 5) -> dict[str, Any]:
        """执行 GraphRAG 推理。

        Args:
            query: 自然语言查询。
            max_hops: 最大图谱跳数。
            max_evidence: 最大证据文档数。

        Returns:
            推理结果 dict。
        """
        # 1. 识别查询中的实体
        entities = self._extract_entities(query)
        if not entities:
            return {"answer": None, "reasoning_paths": [], "evidence": [], "message": "No entities found"}

        # 2. 从每个实体出发 BFS
        all_paths = []
        all_evidence = []

        for entity in entities[:3]:
            paths = self._bfs_paths(entity["entity_id"], max_hops)
            evidence = self._collect_evidence(entity["entity_id"], max_evidence)
            all_paths.extend(paths)
            all_evidence.extend(evidence)

        # 3. 构建推理提示
        prompt = self._build_prompt(query, all_paths, all_evidence)

        # 4. LLM 推理
        if self._llm:
            answer = self._llm(prompt)
        else:
            answer = self._rule_based_answer(query, all_paths, all_evidence)

        return {
            "query": query,
            "entities": [e["label"] for e in entities[:3]],
            "reasoning_paths": all_paths[:10],
            "evidence": all_evidence[:max_evidence],
            "prompt": prompt,
            "answer": answer,
            "method": "llm" if self._llm else "rule",
        }

    def _extract_entities(self, query: str) -> list[dict]:
        """从查询中提取已知实体。"""
        entities = []
        rows = self.conn.execute("SELECT entity_id, label, entity_type FROM kos_entities").fetchall()

        query_lower = query.lower()
        for row in rows:
            if row["label"].lower() in query_lower:
                entities.append(
                    {
                        "entity_id": row["entity_id"],
                        "label": row["label"],
                        "type": row["entity_type"],
                    }
                )

        return entities

    def _bfs_paths(self, start_id: str, max_hops: int) -> list[dict]:
        """BFS 遍历图谱路径。"""
        from collections import deque

        paths = []
        queue = deque([(start_id, [start_id], [])])
        visited = {start_id}

        while queue:
            node, path, predicates = queue.popleft()

            if len(path) > max_hops + 1:
                continue

            # Get neighbors
            neighbors = self.conn.execute(
                "SELECT target_id, predicate, confidence FROM kos_relations WHERE source_id = ?", (node,)
            ).fetchall()

            for nb in neighbors:
                if nb["target_id"] not in visited:
                    visited.add(nb["target_id"])
                    new_path = path + [nb["target_id"]]
                    new_preds = predicates + [nb["predicate"]]

                    if len(new_path) >= 2:
                        paths.append(
                            {
                                "path": new_path,
                                "predicates": new_preds,
                                "hops": len(new_path) - 1,
                                "min_confidence": min(p["confidence"] for p in [nb]),
                            }
                        )

                    queue.append((nb["target_id"], new_path, new_preds))

        # Sort by confidence
        paths.sort(key=lambda p: -p.get("min_confidence", 0))
        return paths

    def _collect_evidence(self, entity_id: str, limit: int) -> list[dict]:
        """收集实体的证据文档。"""
        rows = self.conn.execute(
            """SELECT d.doc_id, d.title, d.body, d.canonical_path, ed.relevance
               FROM kos_entity_docs ed
               JOIN documents d ON ed.doc_id = d.doc_id
               WHERE ed.entity_id = ?
               ORDER BY ed.relevance DESC LIMIT ?""",
            (entity_id, limit),
        ).fetchall()

        return [dict(r) for r in rows]

    def _build_prompt(self, query: str, paths: list, evidence: list) -> str:
        """构建 LLM 推理提示。"""
        lines = [f"Query: {query}\n"]

        if paths:
            lines.append("Knowledge Graph Paths:")
            for i, p in enumerate(paths[:5], 1):
                path_str = " -> ".join(p["path"])
                pred_str = " -> ".join(p["predicates"])
                lines.append(f"  {i}. {path_str} (via {pred_str})")

        if evidence:
            lines.append("\nEvidence:")
            for i, e in enumerate(evidence[:3], 1):
                snippet = (e.get("body") or "")[:200]
                lines.append(f"  {i}. [{e.get('title', '?')}] {snippet}")

        lines.append("\nBased on the above knowledge graph paths and evidence, answer the query.")
        return "\n".join(lines)

    def _rule_based_answer(self, query: str, paths: list, evidence: list) -> str:
        """基于规则的推理 (无 LLM 时的 fallback)."""
        if not paths and not evidence:
            return "Insufficient information to answer the query."

        parts = []
        if paths:
            parts.append(f"Found {len(paths)} reasoning paths in knowledge graph.")
            for p in paths[:3]:
                parts.append(f"  Path: {' -> '.join(p['path'])}")

        if evidence:
            parts.append(f"Found {len(evidence)} evidence documents.")

        return "\n".join(parts)

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


if __name__ == "__main__":
    reasoner = GraphRAGReasoner()

    # Test
    result = reasoner.reason("夏明星参与的项目")
    print(f"Entities: {result['entities']}")
    print(f"Paths: {len(result['reasoning_paths'])}")
    print(f"Evidence: {len(result['evidence'])}")
    print(f"Answer: {result['answer'][:200] if result['answer'] else 'N/A'}")

    reasoner.close()
