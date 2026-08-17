"""Policy Tracker KOS 存储 — 将卫生政策条目写入 KOS ontology store。

实体 ID 格式: ``CON-POL-<12位sha256>`` （CONCEPT 类型）
"""

from __future__ import annotations

import hashlib
import logging

from minerva.policy_tracker.types import PolicyItem

logger = logging.getLogger(__name__)


def _make_entity_id(item: PolicyItem) -> str:
    """生成 KOS 实体 ID。"""
    key = f"policy-tracker:{item.issuing_agency}:{item.doc_number or item.url or item.title}"
    return "CON-POL-" + hashlib.sha256(key.encode()).hexdigest()[:12]


def save_to_kos(items: list[PolicyItem]) -> dict[str, int]:
    """批量写入 KOS，zone=policy_tracker。

    Returns: ``{"saved": N, "failed": M, "skipped": K}``
    """
    try:
        from kos.ontology._types import Entity, EntityType
        from kos.ontology.store import put_entity
    except ImportError:
        logger.warning("kos not available — skipping KOS write")
        return {"saved": 0, "failed": 0, "skipped": len(items)}

    stats = {"saved": 0, "failed": 0, "skipped": 0}
    combined_tags_base = ["#health-policy", "#policy-tracker"]

    for item in items:
        if not item.title:
            stats["skipped"] += 1
            continue

        entity_id = _make_entity_id(item)
        all_tags = list(set(item.tags + combined_tags_base))

        try:
            entity = Entity(
                entity_id=entity_id,
                entity_type=EntityType.CONCEPT,
                label=item.title[:200],
                description=item.summary[:1000],
                zone="policy_tracker",
                source=item.issuing_agency,
                confidence=item.relevance_score or 0.6,
                metadata={
                    "url": item.url,
                    "issuing_agency": item.issuing_agency,
                    "doc_number": item.doc_number,
                    "published_at": item.published_at,
                    "relevance_score": str(item.relevance_score),
                    "tags": ",".join(all_tags),
                },
                references=[item.url] if item.url else [],
            )
            result = put_entity(entity)
            if isinstance(result, dict) and "error" in result:
                logger.warning("kos_write_error entity=%s err=%s", entity_id, result["error"])
                stats["failed"] += 1
            else:
                stats["saved"] += 1
        except Exception as exc:
            logger.warning("kos_write_exception entity=%s exc=%s", entity_id, exc)
            stats["failed"] += 1

    return stats
