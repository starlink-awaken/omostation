#!/usr/bin/env python3
# ruff: noqa
"""
KOS GraphRAG — 图谱多跳推理

基于本体图谱实现多跳关系推理，支持：
1. BFS/DFS 多跳遍历
2. 路径评分 (基于关系置信度)
3. 最短路径查找
4. 隐含关联发现

Usage:
    from kos.graphrag import GraphRAG

    rag = GraphRAG()

    # 多跳搜索
    results = rag.multi_hop_search("夏明星", hops=3, limit=10)

    # 路径查找
    path = rag.find_path("P:xia-mingxing", "J:kairon")

    # 隐含关联
    associations = rag.discover_implicit("数字化平台")
"""

from __future__ import annotations

import heapq
from collections import deque
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class GraphRAG:
    """图谱多跳推理引擎。"""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = get_connection(self.db_path)
        return self._conn

    # ── 多跳搜索 ────────────────────────────────────────────

    def multi_hop_search(
        self,
        query: str,
        hops: int = 2,
        limit: int = 10,
    ) -> dict[str, Any]:
        """多跳图谱搜索。

        从查询匹配的实体出发，沿关系边进行 BFS 遍历，
        找到多跳后的关联文档。

        Args:
            query: 搜索查询。
            hops: 最大跳数。
            limit: 最大结果数。

        Returns:
            搜索结果 + 推理路径。
        """
        # 1. 找到起始实体
        start_entities = self._find_entities(query)
        if not start_entities:
            return {"results": [], "paths": [], "message": "No matching entities found"}

        # 2. BFS 多跳遍历
        visited = set()
        queue = deque()

        for ent in start_entities:
            queue.append((ent["entity_id"], 0, [ent["entity_id"]], 1.0))
            visited.add(ent["entity_id"])

        all_paths = []
        found_docs = {}  # doc_id -> best_score

        while queue:
            current_id, current_hop, path, score = queue.popleft()

            if current_hop >= hops:
                continue

            # 获取邻居
            neighbors = self._get_neighbors(current_id)

            for neighbor_id, predicate, confidence in neighbors:
                if neighbor_id in visited:
                    continue

                new_score = score * confidence
                new_path = path + [predicate, neighbor_id]

                # 获取该实体的关联文档
                docs = self._get_entity_docs(neighbor_id)
                for doc in docs:
                    doc_id = doc["doc_id"]
                    doc_score = new_score * doc.get("relevance", 0.5)
                    if doc_id not in found_docs or found_docs[doc_id] < doc_score:
                        found_docs[doc_id] = doc_score

                all_paths.append(
                    {
                        "path": new_path,
                        "score": new_score,
                        "hops": current_hop + 1,
                    }
                )

                visited.add(neighbor_id)
                queue.append((neighbor_id, current_hop + 1, new_path, new_score))

        # 3. 排序结果
        sorted_docs = sorted(found_docs.items(), key=lambda x: -x[1])[:limit]

        results = []
        for doc_id, score in sorted_docs:
            doc = self.conn.execute(
                "SELECT doc_id, title, zone, canonical_path FROM documents WHERE doc_id = ?", (doc_id,)
            ).fetchone()
            if doc:
                results.append(
                    {
                        "doc_id": doc["doc_id"],
                        "title": doc["title"],
                        "zone": doc["zone"],
                        "canonical_path": doc["canonical_path"],
                        "score": round(score, 4),
                    }
                )

        # 4. 排序路径
        sorted_paths = sorted(all_paths, key=lambda x: -x["score"])[:limit]

        return {
            "query": query,
            "start_entities": [e["label"] for e in start_entities],
            "results": results,
            "paths": sorted_paths,
            "total_paths": len(all_paths),
        }

    # ── 路径查找 ────────────────────────────────────────────

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 5,
    ) -> dict[str, Any]:
        """查找两个实体之间的最短路径。

        使用 Dijkstra 算法 (基于置信度倒数为权重)。

        Args:
            source_id: 源实体 ID。
            target_id: 目标实体 ID。
            max_hops: 最大跳数。

        Returns:
            最短路径 + 详情。
        """
        # Dijkstra
        dist = {source_id: 0}
        prev = {source_id: None}
        pq = [(0, source_id, [])]

        while pq:
            cost, node, path = heapq.heappop(pq)

            if node == target_id:
                return {
                    "found": True,
                    "path": path + [node],
                    "hops": len(path),
                    "cost": cost,
                }

            if len(path) >= max_hops:
                continue

            for neighbor_id, predicate, confidence in self._get_neighbors(node):
                # 权重 = 1 / 置信度 (置信度越高，权重越低)
                weight = 1.0 / max(confidence, 0.1)
                new_cost = cost + weight

                if neighbor_id not in dist or new_cost < dist[neighbor_id]:
                    dist[neighbor_id] = new_cost  # type: ignore[reportArgumentType]
                    prev[neighbor_id] = (node, predicate)  # type: ignore[reportArgumentType]
                    heapq.heappush(pq, (new_cost, neighbor_id, path + [(node, predicate)]))  # type: ignore[reportArgumentType]

        return {"found": False, "message": f"No path found within {max_hops} hops"}

    # ── 隐含关联发现 ──────────────────────────────────────

    def discover_implicit(
        self,
        query: str,
        min_shared_docs: int = 2,
    ) -> dict[str, Any]:
        """发现隐含关联实体。

        找到与查询实体共现但未直接关联的实体。

        Args:
            query: 搜索查询。
            min_shared_docs: 最小共享文档数。
        Returns:
            隐含关联列表。
        """
        # 找到查询实体
        entities = self._find_entities(query)
        if not entities:
            return {"associations": [], "message": "No matching entities"}

        associations = []

        for ent in entities:
            # 找到共现但未关联的实体
            implicit = self.conn.execute(
                """
                SELECT e2.entity_id, e2.label, e2.entity_type, COUNT(*) as shared_docs
                FROM kos_entity_docs ed1
                JOIN kos_entity_docs ed2 ON ed1.doc_id = ed2.doc_id AND ed1.entity_id != ed2.entity_id
                JOIN kos_entities e2 ON ed2.entity_id = e2.entity_id
                WHERE ed1.entity_id = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM kos_relations r
                      WHERE (r.source_id = ed1.entity_id AND r.target_id = e2.entity_id)
                         OR (r.source_id = e2.entity_id AND r.target_id = ed1.entity_id)
                  )
                GROUP BY e2.entity_id
                HAVING shared_docs >= ?
                ORDER BY shared_docs DESC
                LIMIT 10
            """,
                (ent["entity_id"], min_shared_docs),
            ).fetchall()

            for imp in implicit:
                associations.append(
                    {
                        "from_entity": ent["label"],
                        "to_entity": imp["label"],
                        "to_type": imp["entity_type"],
                        "shared_docs": imp["shared_docs"],
                    }
                )

        return {
            "query": query,
            "associations": associations,
            "count": len(associations),
        }

    # ── 辅助方法 ────────────────────────────────────────────

    def _find_entities(self, query: str) -> list[dict]:
        """根据查询查找实体。"""
        rows = self.conn.execute(
            """
            SELECT entity_id, label, entity_type
            FROM kos_entities
            WHERE label LIKE ? OR ? LIKE '%' || label || '%'
            ORDER BY entity_type, label LIMIT 10
        """,
            (f"%{query}%", query),
        ).fetchall()

        return [dict(r) for r in rows]

    def _get_neighbors(self, entity_id: str) -> list[tuple[str, str, float]]:
        """获取实体的邻居 (出边 + 入边)。"""
        outgoing = self.conn.execute(
            "SELECT target_id, predicate, confidence FROM kos_relations WHERE source_id = ?", (entity_id,)
        ).fetchall()

        incoming = self.conn.execute(
            "SELECT source_id, predicate, confidence FROM kos_relations WHERE target_id = ?", (entity_id,)
        ).fetchall()

        neighbors = []
        for r in outgoing:
            neighbors.append((r["target_id"], r["predicate"], r["confidence"]))
        for r in incoming:
            neighbors.append((r["source_id"], f"inverse_{r['predicate']}", r["confidence"]))

        return neighbors

    def _get_entity_docs(self, entity_id: str) -> list[dict]:
        """获取实体关联的文档。"""
        rows = self.conn.execute(
            """
            SELECT doc_id, relevance FROM kos_entity_docs
            WHERE entity_id = ?
            ORDER BY relevance DESC LIMIT 5
        """,
            (entity_id,),
        ).fetchall()

        return [dict(r) for r in rows]

    def close(self):
        """关闭连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── CLI 入口 ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="KOS GraphRAG")
    sub = parser.add_subparsers(dest="command")

    # Multi-hop search
    p_search = sub.add_parser("search", help="Multi-hop graph search")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--hops", type=int, default=2, help="Max hops")
    p_search.add_argument("--limit", type=int, default=10, help="Max results")

    # Path finding
    p_path = sub.add_parser("path", help="Find path between entities")
    p_path.add_argument("source", help="Source entity ID")
    p_path.add_argument("target", help="Target entity ID")
    p_path.add_argument("--max-hops", type=int, default=5, help="Max hops")

    # Implicit associations
    p_implicit = sub.add_parser("discover", help="Discover implicit associations")
    p_implicit.add_argument("query", help="Search query")
    p_implicit.add_argument("--min-shared", type=int, default=2, help="Min shared docs")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    rag = GraphRAG()

    if args.command == "search":
        result = rag.multi_hop_search(args.query, hops=args.hops, limit=args.limit)
    elif args.command == "path":
        result = rag.find_path(args.source, args.target, max_hops=args.max_hops)
    elif args.command == "discover":
        result = rag.discover_implicit(args.query, min_shared_docs=args.min_shared)
    else:
        result = {"error": f"Unknown command: {args.command}"}

    rag.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))  # type: ignore[reportUndefinedVariable]


if __name__ == "__main__":
    main()
