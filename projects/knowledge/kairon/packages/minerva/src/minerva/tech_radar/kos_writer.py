"""Tech Radar KOS 存储 — 将技术情报条目写入 KOS ontology store。"""

from __future__ import annotations

import hashlib
import logging

from minerva.tech_radar.fetcher import TechItem

logger = logging.getLogger(__name__)


def _make_entity_id(item: TechItem) -> str:
    key = f"tech-radar:{item.source}:{item.url or item.title}"
    return "CON-TR-" + hashlib.sha256(key.encode()).hexdigest()[:12]


def save_to_kos(items: list[TechItem]) -> dict[str, int]:
    """批量写入 KOS，zone=tech_radar，附 #tech-radar 标签。

    Returns: {"saved": N, "failed": M, "skipped": K}
    """
    try:
        from kos.ontology._types import Entity, EntityType
        from kos.ontology.store import put_entity
    except ImportError:
        logger.warning("kos not available — skipping KOS write")
        return {"saved": 0, "failed": 0, "skipped": len(items)}

    stats = {"saved": 0, "failed": 0, "skipped": 0}

    for item in items:
        if not item.title:
            stats["skipped"] += 1
            continue

        entity_id = _make_entity_id(item)
        combined_tags = list(
            set(item.tags + ["#tech-radar"] + (["#upgrade-candidate"] if item.upgrade_candidate else []))
        )

        try:
            entity = Entity(
                entity_id=entity_id,
                entity_type=EntityType.CONCEPT,
                label=item.title[:200],
                description=item.description[:1000],
                zone="tech_radar",
                source=item.source,
                confidence=item.relevance_score or 0.5,
                metadata={
                    "url": item.url,
                    "source": item.source,
                    "published_at": item.published_at,
                    "relevance_score": str(item.relevance_score),
                    "upgrade_candidate": str(item.upgrade_candidate),
                    "tags": ",".join(combined_tags),
                },
                references=[item.url] if item.url else [],
            )
            result = put_entity(entity)
            if "error" in result:
                logger.warning("kos_write_error entity=%s err=%s", entity_id, result["error"])
                stats["failed"] += 1
            else:
                stats["saved"] += 1
        except Exception as exc:
            logger.warning("kos_write_exception entity=%s exc=%s", entity_id, exc)
            stats["failed"] += 1

    return stats
