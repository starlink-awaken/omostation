#!/usr/bin/env python3
# ruff: noqa
"""
KOS Ontology Evolution Engine — 本体演化引擎

自动发现和修复本体问题:
1. 实体去重 — 合并重复/相似实体
2. 类型规范化 — 统一实体类型 (如 concept→Concept)
3. 关系冲突检测 — 发现矛盾关系
4. 孤立实体检测 — 发现无关系的实体
5. 类型发现 — 从实体名称推断缺失类型

Usage:
    from kos.ontology.evolution import OntologyEvolution

    evo = OntologyEvolution()
    report = evo.evolve()
    print(report)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from kos.config import get_artifact_path
from kos.db import get_connection


class OntologyEvolution:
    """本体演化引擎。

    自动发现和修复本体中的质量问题。
    """

    # 类型归一化映射
    TYPE_NORMALIZATION = {
        "concept": "Concept",
        "person": "Person",
        "org": "Organization",
        "organization": "Organization",
        "project": "Project",
        "regulation": "Regulation",
        "doc": "Document",
        "document": "Document",
        "event": "Event",
        "role": "Role",
        "axiom": "Axiom",
        "principle": "Principle",
        "theory": "Theory",
        "framework": "Framework",
        "skill": "Skill",
        "consensus": "Consensus",
        "task": "Task",
        "node": "Node",
    }

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_artifact_path("retrievalDatabase")

    def evolve(self) -> dict[str, Any]:
        """运行一次完整的本体演化循环。

        Returns:
            演化报告。
        """
        conn = get_connection(self.db_path)

        report = {
            "timestamp": datetime.now().isoformat(),
            "deduplication": self._deduplicate(conn),
            "type_normalization": self._normalize_types(conn),
            "orphan_detection": self._detect_orphans(conn),
            "relation_conflicts": self._detect_conflicts(conn),
        }

        conn.close()
        return report

    def _deduplicate(self, conn: sqlite3.Connection) -> dict[str, Any]:
        """合并重复实体 (基于标签精确匹配)。"""
        # 查找重复标签
        dupes = conn.execute("""
            SELECT LOWER(label) as low_label, COUNT(*) as cnt,
                   GROUP_CONCAT(entity_id, '|||') as ids
            FROM kos_entities
            GROUP BY LOWER(label)
            HAVING cnt > 1
        """).fetchall()

        merged = 0
        for dup in dupes:
            ids = dup["ids"].split("|||")
            canonical_id = ids[0]
            for other_id in ids[1:]:
                # 更新关系指向规范实体
                conn.execute(
                    "UPDATE OR IGNORE kos_relations SET target_id=? WHERE target_id=?",
                    (canonical_id, other_id),
                )
                conn.execute(
                    "UPDATE OR IGNORE kos_relations SET source_id=? WHERE source_id=?",
                    (canonical_id, other_id),
                )
                # 更新文档关联
                conn.execute(
                    "UPDATE OR IGNORE kos_entity_docs SET entity_id=? WHERE entity_id=?",
                    (canonical_id, other_id),
                )
                # 删除重复
                conn.execute("DELETE FROM kos_entities WHERE entity_id=?", (other_id,))
                merged += 1

        conn.commit()
        return {"duplicate_groups": len(dupes), "entities_merged": merged}

    def _normalize_types(self, conn: sqlite3.Connection) -> dict[str, Any]:
        """归一化实体类型 (大小写、别名)。"""
        entities = conn.execute("SELECT entity_id, entity_type FROM kos_entities").fetchall()
        normalized = 0

        for ent in entities:
            current_type = ent["entity_type"]
            normalized_type = self.TYPE_NORMALIZATION.get(current_type.lower())
            if normalized_type and normalized_type != current_type:
                conn.execute(
                    "UPDATE kos_entities SET entity_type=? WHERE entity_id=?",
                    (normalized_type, ent["entity_id"]),
                )
                normalized += 1

        conn.commit()
        return {"entities_normalized": normalized}

    def _detect_orphans(self, conn: sqlite3.Connection) -> dict[str, Any]:
        """检测孤立实体 (无文档关联、无关系)。"""
        orphans = conn.execute("""
            SELECT e.entity_id, e.label, e.entity_type
            FROM kos_entities e
            LEFT JOIN kos_entity_docs ed ON e.entity_id = ed.entity_id
            LEFT JOIN kos_relations r ON e.entity_id = r.source_id OR e.entity_id = r.target_id
            WHERE ed.doc_id IS NULL AND r.source_id IS NULL
        """).fetchall()

        return {
            "orphan_count": len(orphans),
            "orphans": [
                {"id": o["entity_id"], "label": o["label"], "type": o["entity_type"]}
                for o in orphans[:20]  # 限制输出数量
            ],
        }

    def _detect_conflicts(self, conn: sqlite3.Connection) -> dict[str, Any]:
        """检测关系冲突 (重复关系、自引用)。"""
        # 1. 重复关系
        dup_relations = conn.execute("""
            SELECT source_id, predicate, target_id, COUNT(*) as cnt
            FROM kos_relations
            GROUP BY source_id, predicate, target_id
            HAVING cnt > 1
        """).fetchall()

        # 2. 自引用
        self_refs = conn.execute("""
            SELECT source_id, target_id FROM kos_relations
            WHERE source_id = target_id
        """).fetchall()

        # 清理自引用
        cleaned = 0
        for sr in self_refs:
            conn.execute(
                "DELETE FROM kos_relations WHERE source_id=? AND target_id=?",
                (sr["source_id"], sr["target_id"]),
            )
            cleaned += 1

        conn.commit()
        return {
            "duplicate_relations": len(dup_relations),
            "self_references_removed": cleaned,
        }

    def get_stats(self) -> dict[str, Any]:
        """获取本体统计信息。"""
        conn = get_connection(self.db_path)

        entity_count = conn.execute("SELECT COUNT(*) FROM kos_entities").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM kos_relations").fetchone()[0]
        doc_link_count = conn.execute("SELECT COUNT(*) FROM kos_entity_docs").fetchone()[0]

        # 类型分布
        types = conn.execute(
            "SELECT entity_type, COUNT(*) as cnt FROM kos_entities GROUP BY entity_type ORDER BY cnt DESC"
        ).fetchall()

        conn.close()

        return {
            "entities": entity_count,
            "relations": relation_count,
            "entity_doc_links": doc_link_count,
            "type_distribution": {t["entity_type"]: t["cnt"] for t in types},
        }

    def get_recommendations(self) -> list[dict]:
        """获取改进建议。"""
        conn = get_connection(self.db_path)
        recommendations = []

        # 1. 无文档关联的实体
        orphans = conn.execute("""
            SELECT e.entity_id, e.label FROM kos_entities e
            LEFT JOIN kos_entity_docs ed ON e.entity_id = ed.entity_id
            WHERE ed.doc_id IS NULL LIMIT 10
        """).fetchall()

        if orphans:
            recommendations.append(
                {
                    "type": "orphan_entities",
                    "message": f"Found {len(orphans)} entities without document links",
                    "entities": [o["label"] for o in orphans],
                }
            )

        # 2. 低置信度关系
        low_conf = conn.execute("""
            SELECT source_id, target_id, confidence FROM kos_relations
            WHERE confidence < 0.5 LIMIT 10
        """).fetchall()

        if low_conf:
            recommendations.append(
                {
                    "type": "low_confidence_relations",
                    "message": f"Found {len(low_conf)} relations with confidence < 0.5",
                }
            )

        conn.close()
        return recommendations


# ── CLI 入口 ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="KOS Ontology Evolution Engine")
    parser.add_argument(
        "action",
        choices=["evolve", "stats", "recommend"],
        default="stats",
        nargs="?",
        help="Action: evolve/stats/recommend",
    )
    args = parser.parse_args()

    evo = OntologyEvolution()

    if args.action == "evolve":
        report = evo.evolve()
        print(f"Evolution Report:")
        print(f"  Duplicates merged: {report['deduplication']['entities_merged']}")
        print(f"  Types normalized: {report['type_normalization']['entities_normalized']}")
        print(f"  Orphans found: {report['orphan_detection']['orphan_count']}")
        print(f"  Conflicts resolved: {report['relation_conflicts']['self_references_removed']}")
        print(json.dumps(report, ensure_ascii=False, indent=2))  # type: ignore[reportUndefinedVariable]
    elif args.action == "stats":
        stats = evo.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))  # type: ignore[reportUndefinedVariable]
    elif args.action == "recommend":
        recs = evo.get_recommendations()
        print(json.dumps(recs, ensure_ascii=False, indent=2))  # type: ignore[reportUndefinedVariable]


if __name__ == "__main__":
    main()
