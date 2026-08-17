from __future__ import annotations

"""
Extracted from SharedBrain D_Harvest → minerva.

---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Factgraph Importer ≡ Module
# 内涵 ≝ {Factgraph, Importer}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, FactgraphImporter)}
# 功能 ⊢ {Factgraph_Importer, Init_Factgraph, Validate_Importer}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
FactGraph知识导入器

将D-Harvest收割的知识条目转换为FactGraph的RDF三元组格式并导入。

职责：
- 从KnowledgeStore读取未同步的知识条目
- 将知识条目转换为RDF三元组
- 批量导入到FactGraph
- 标记已同步状态

遵循原则：
- KISS: 简单直接的转换逻辑
- SRP: 只负责转换和导入，不负责收割或验证
- DRY: 复用现有的存储层接口
"""
import logging
from datetime import UTC, datetime
from typing import Any

_log = logging.getLogger(__name__)


class FactGraphImporter:
    """
    FactGraph知识导入器

    将KnowledgeStore中的知识条目转换为RDF三元组并导入FactGraph。
    """

    # RDF命名空间前缀
    NS_HARVEST = "https://brain.ai/harvest/"
    NS_DC = "http://purl.org/dc/elements/1.1/"
    NS_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

    def __init__(self, knowledge_store: Any, fact_graph: Any) -> None:
        """
        初始化导入器

        Args:
            knowledge_store: D-Harvest知识存储实例
            fact_graph: D-Memory FactGraph实例
        """
        self.knowledge_store = knowledge_store
        self.fact_graph = fact_graph
        self._imported_count = 0
        self._skipped_count = 0

    def _create_uri_ref(self, uri: str) -> str:
        """
        创建URI引用，确保格式正确

        Args:
            uri: 原始URI

        Returns:
            规范化的URI引用
        """
        if not uri.startswith(("http://", "https://", "urn:")):
            # 如果不是标准URI，使用harvest命名空间
            return f"{self.NS_HARVEST}{uri}"
        return uri

    def _knowledge_to_triples(self, item_id: int, item: dict[str, Any]) -> list[tuple[str, str, str, dict]]:
        """
        将知识条目转换为RDF三元组

        Args:
            item_id: 知识条目ID
            item: 知识条目字典

        Returns:
            三元组列表 [(sub, pred, obj, metadata), ...]
        """
        uri = item["uri"]
        title = item["title"]
        body = item["body"]
        harvested_at = item.get("harvested_at", datetime.now(UTC).isoformat())
        quality_score = item.get("quality_score", 0.0)
        visibility = item.get("visibility", "private")

        # 创建主资源URI
        subject_uri = self._create_uri_ref(uri)

        triples = []

        # 1. 基本元数据三元组
        triples.append(
            (
                subject_uri,
                f"{self.NS_DC}title",
                title,
                {"importance": quality_score, "source": "harvest"},
            )
        )

        triples.append(
            (
                subject_uri,
                f"{self.NS_DC}description",
                body[:500],  # 截断过长内容
                {"importance": quality_score * 0.8, "source": "harvest"},
            )
        )

        # 2. 类型三元组
        triples.append(
            (
                subject_uri,
                f"{self.NS_RDF}type",
                f"{self.NS_HARVEST}HarvestedKnowledge",
                {"importance": 0.5, "source": "harvest"},
            )
        )

        # 3. 可见性三元组
        triples.append(
            (
                subject_uri,
                f"{self.NS_HARVEST}visibility",
                visibility,
                {"importance": 0.3, "source": "harvest"},
            )
        )

        # 4. 时间戳三元组
        triples.append(
            (
                subject_uri,
                f"{self.NS_HARVEST}harvestedAt",
                harvested_at,
                {"importance": 0.4, "source": "harvest"},
            )
        )

        # 5. 质量分数三元组
        triples.append(
            (
                subject_uri,
                f"{self.NS_HARVEST}qualityScore",
                str(quality_score),
                {"importance": 0.5, "source": "harvest"},
            )
        )

        # 6. 来源URI三元组（保留原始URI）
        triples.append(
            (
                subject_uri,
                f"{self.NS_HARVEST}sourceUri",
                uri,
                {"importance": 0.6, "source": "harvest"},
            )
        )

        # 7. 从metadata中提取的额外三元组
        metadata = item.get("metadata", {})
        if isinstance(metadata, str):
            try:
                import json

                metadata = json.loads(metadata)
            except (json.JSONDecodeError, ValueError):  # type: ignore[reportPossiblyUnboundVariable]
                metadata = {}

        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if key and value:
                    pred_uri = f"{self.NS_HARVEST}{key}"
                    obj_value = str(value)[:200]  # 限制长度
                    triples.append((subject_uri, pred_uri, obj_value, {"importance": 0.3, "source": "harvest"}))

        return triples

    async def import_batch(self, limit: int = 100, min_quality: float = 0.6, dry_run: bool = False) -> dict[str, Any]:
        """
        批量导入知识条目到FactGraph

        Args:
            limit: 最大导入数量
            min_quality: 最低质量分数阈值
            dry_run: 是否模拟运行（不实际导入）

        Returns:
            导入结果统计
        """
        _log.info(f"Starting FactGraph import: limit={limit}, min_quality={min_quality}, dry_run={dry_run}")

        # 1. 获取未同步的知识条目
        items = await self.knowledge_store.list_knowledge(
            limit=limit, min_quality=min_quality, unsynced_to_factgraph=True
        )

        if not items:
            _log.info("No items to import")
            return {"success": True, "imported": 0, "skipped": 0, "message": "No items to import"}

        _log.info(f"Found {len(items)} items to import")

        # 2. 转换为三元组
        all_triples = []
        item_ids = []
        for item in items:
            try:
                triples = self._knowledge_to_triples(item["id"], item)
                all_triples.extend(triples)
                item_ids.append(item["id"])
            except Exception as e:
                _log.error(f"Failed to convert item {item['id']}: {e}")
                self._skipped_count += 1
                continue

        _log.info(f"Converted to {len(all_triples)} triples")

        # 3. 模拟运行或实际导入
        if dry_run:
            _log.info(f"[DRY RUN] Would import {len(all_triples)} triples from {len(item_ids)} items")
            return {
                "success": True,
                "imported": len(item_ids),
                "skipped": self._skipped_count,
                "triples": len(all_triples),
                "message": "Dry run completed",
            }

        # 4. 实际导入到FactGraph
        try:
            fact_ids = self.fact_graph.add_facts(all_triples, _remote_sync=False)
            self._imported_count = len(item_ids)

            _log.info(f"Imported {len(fact_ids)} facts to FactGraph")

            # 5. 标记为已同步
            if item_ids:
                updated = await self.knowledge_store.mark_factgraph_synced(item_ids)
                _log.info(f"Marked {updated} items as synced")

            return {
                "success": True,
                "imported": self._imported_count,
                "skipped": self._skipped_count,
                "triples": len(fact_ids),
                "message": f"Successfully imported {self._imported_count} items",
            }

        except Exception as e:
            _log.error(f"Failed to import to FactGraph: {e}")
            return {
                "success": False,
                "imported": 0,
                "skipped": len(items),
                "error": str(e),
                "message": "Import failed",
            }

    async def import_single(self, item_id: int, dry_run: bool = False) -> dict[str, Any]:
        """
        导入单个知识条目

        Args:
            item_id: 知识条目ID
            dry_run: 是否模拟运行

        Returns:
            导入结果
        """
        item = await self.knowledge_store.get_knowledge(item_id)
        if not item:
            return {"success": False, "imported": 0, "error": f"Item {item_id} not found"}

        if item.get("factgraph_synced"):
            return {"success": True, "imported": 0, "skipped": 1, "message": "Item already synced"}

        triples = self._knowledge_to_triples(item_id, item)

        if dry_run:
            return {
                "success": True,
                "imported": 0,
                "triples": len(triples),
                "message": "Dry run completed",
            }

        try:
            fact_ids = self.fact_graph.add_facts(triples, _remote_sync=False)
            await self.knowledge_store.mark_factgraph_synced([item_id])

            return {
                "success": True,
                "imported": 1,
                "triples": len(fact_ids),
                "message": "Successfully imported",
            }

        except Exception as e:
            _log.error(f"Failed to import item {item_id}: {e}")
            return {"success": False, "imported": 0, "error": str(e)}

    def get_stats(self) -> dict[str, int]:
        """
        获取导入统计信息

        Returns:
            统计信息字典
        """
        return {"imported": self._imported_count, "skipped": self._skipped_count}
