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
# Knowledge Transformer ≡ Module
# 内涵 ≝ {Knowledge, Transformer}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, KnowledgeTransformer)}
# 功能 ⊢ {Knowledge_Transformer, Init_Knowledge, Validate_Transformer}
# =============================================================================

# ---
# domain: D-Harvest
# layer: shared
# status: active
# ---
"""
KnowledgeToTripleTransformer — 统一的知识转三元组转换器

将知识条目转换为 FactGraph 三元组的统一实现，消除重复代码。

统一的 Schema (对齐 Organs Importer):
- (knowledge_{id}, "rdf_type", "KnowledgeItem")
- (knowledge_{id}, "dct_title", title[:500])
- (knowledge_{id}, "dct_source", uri[:1000])
- (knowledge_{id}, "dct_description", body[:2000])
- (knowledge_{id}, "bos_qualityScore", score)
- (knowledge_{id}, "bos_harvestedAt", timestamp)
- (knowledge_{id}, "bos_visibility", visibility)
- (source_{domain}, "rdf_type", "KnowledgeSource")
- (knowledge_{id}, "dct_sourceRef", source_{domain})
- (knowledge_{id}, "bos_meta_{key}", value) — 元数据扩展

遵循原则：
- KISS: 简单直接，不过度设计
- SRP: 只负责转换，不负责存储或同步
- DRY: 单一来源，避免重复
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

_log = logging.getLogger(__name__)


# =============================================================================
# 数据类型
# =============================================================================


@dataclass
class Triple:
    """RDF 风格的三元组"""

    subject: str
    predicate: str
    object: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransformResult:
    """转换结果"""

    success: bool
    triples: list[Triple] = field(default_factory=list)
    error: str | None = None


# =============================================================================
# 转换器
# =============================================================================


class KnowledgeToTripleTransformer:
    """
    统一的知识转三元组转换器

    使用示例：
        transformer = KnowledgeToTripleTransformer()
        result = transformer.transform({
            "id": 1,
            "uri": "https://example.com/article",
            "title": "示例标题",
            "body": "示例正文内容",
            "quality_score": 0.8,
            "harvested_at": "2024-01-01T00:00:00Z",
            "visibility": "private",
            "metadata": {"author": "张三"}
        })
    """

    # FactGraph 节点 ID 格式要求
    _NODE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

    # 统一质量门槛
    QUALITY_THRESHOLD = 0.6

    def __init__(self, quality_threshold: float | None = None) -> None:
        """
        初始化转换器

        Args:
            quality_threshold: 质量门槛（默认 0.6）
        """
        self._quality_threshold = quality_threshold or self.QUALITY_THRESHOLD

    def transform(
        self,
        item: dict[str, Any],
        validate_quality: bool = False,
    ) -> TransformResult:
        """
        将知识条目转换为三元组

        Args:
            item: 知识条目字典
            validate_quality: 是否验证质量门槛

        Returns:
            TransformResult 转换结果
        """
        try:
            # 质量验证
            if validate_quality:
                quality = float(item.get("quality_score", 0.0))
                if quality < self._quality_threshold:
                    return TransformResult(
                        success=False,
                        error=f"Quality {quality} below threshold {self._quality_threshold}",
                    )

            triples = self._convert_to_triples(item)
            return TransformResult(success=True, triples=triples)

        except (KeyError, ValueError, TypeError) as e:
            return TransformResult(success=False, error=str(e))

    def _convert_to_triples(self, item: dict[str, Any]) -> list[Triple]:
        """将知识条目转换为 FactGraph 三元组"""
        triples = []

        item_id = str(item["id"])
        uri = item["uri"]
        title = item["title"]
        body = item.get("body", "")
        metadata_raw = item.get("metadata", {})
        visibility = item.get("visibility", "private")
        quality = float(item.get("quality_score", 0.0))
        harvested_at = item.get("harvested_at", datetime.now(UTC).isoformat())

        # 解析元数据
        if isinstance(metadata_raw, str):
            try:
                metadata = json.loads(metadata_raw)
            except json.JSONDecodeError:
                metadata = {}
        else:
            metadata = metadata_raw or {}

        # 标准化节点 ID
        subject = self._normalize_node_id(f"knowledge_{item_id}")
        now = datetime.now(UTC).isoformat()

        # 1. 基础三元组：类型
        triples.append(
            Triple(
                subject=subject,
                predicate="rdf_type",
                object="KnowledgeItem",
                metadata={"created_at": now},
            )
        )

        # 2. 标题关系
        triples.append(
            Triple(
                subject=subject,
                predicate="dct_title",
                object=str(title)[:500],
                metadata={"source": "harvest"},
            )
        )

        # 3. URI 关系
        triples.append(
            Triple(
                subject=subject,
                predicate="dct_source",
                object=str(uri)[:1000],
                metadata={"source": "harvest"},
            )
        )

        # 4. 正文/描述关系
        body_preview = str(body)[:2000] if body else ""
        if body_preview:
            triples.append(
                Triple(
                    subject=subject,
                    predicate="dct_description",
                    object=body_preview,
                    metadata={"source": "harvest", "truncated": len(str(body)) > 2000},
                )
            )

        # 5. 质量分数
        triples.append(
            Triple(
                subject=subject,
                predicate="bos_qualityScore",
                object=str(quality),
                metadata={"source": "harvest"},
            )
        )

        # 6. 收割时间
        triples.append(
            Triple(
                subject=subject,
                predicate="bos_harvestedAt",
                object=str(harvested_at),
                metadata={"source": "harvest"},
            )
        )

        # 7. 可见性
        triples.append(
            Triple(
                subject=subject,
                predicate="bos_visibility",
                object=str(visibility),
                metadata={"source": "harvest"},
            )
        )

        # 8. 来源域（从 URI 解析）
        try:
            parsed = urlparse(uri)
            if parsed.netloc:
                domain = parsed.netloc
                source_node = self._normalize_node_id(f"source_{domain}")

                # 创建来源节点
                triples.append(
                    Triple(
                        subject=source_node,
                        predicate="rdf_type",
                        object="KnowledgeSource",
                        metadata={"source": "harvest"},
                    )
                )

                # 关联知识到来源
                triples.append(
                    Triple(
                        subject=subject,
                        predicate="dct_sourceRef",
                        object=source_node,
                        metadata={"source": "harvest"},
                    )
                )
        except (ValueError, TypeError):
            pass

        # 9. 元数据扩展
        for key, value in metadata.items():
            if isinstance(value, (str, int, float, bool)):
                predicate = self._normalize_node_id(f"bos_meta_{key}")
                triples.append(
                    Triple(
                        subject=subject,
                        predicate=predicate,
                        object=str(value)[:500],
                        metadata={"source": "harvest", "meta_key": key},
                    )
                )

        return triples

    def _normalize_node_id(self, node_id: str) -> str:
        """
        标准化节点 ID 以符合 FactGraph 要求

        要求: ^[A-Za-z0-9][A-Za-z0-9._-]*$
        """
        # 替换不合法字符
        normalized = node_id.replace(":", "_").replace("-", "_")

        # 如果不以字母数字开头，添加前缀
        if normalized and not normalized[0].isalnum():
            normalized = f"n_{normalized}"

        # 如果为空或全部不合法，使用哈希
        if not normalized or not self._NODE_ID_PATTERN.match(normalized):
            import hashlib

            hash_suffix = hashlib.sha256(node_id.encode()).hexdigest()[:12]
            normalized = f"node_{hash_suffix}"

        return normalized


# =============================================================================
# 便捷函数
# =============================================================================


def transform_knowledge_item(
    item: dict[str, Any],
    quality_threshold: float = 0.6,
) -> list[Triple]:
    """
    便捷函数：将单个知识条目转换为三元组

    Args:
        item: 知识条目字典
        quality_threshold: 质量门槛

    Returns:
        Triple 列表

    Raises:
        ValueError: 质量门槛不通过或转换失败
    """
    transformer = KnowledgeToTripleTransformer(quality_threshold=quality_threshold)
    result = transformer.transform(item, validate_quality=True)

    if not result.success:
        raise ValueError(result.error)

    return result.triples


__all__ = [
    "Triple",
    "TransformResult",
    "KnowledgeToTripleTransformer",
    "transform_knowledge_item",
]
