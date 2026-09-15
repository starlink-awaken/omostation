"""Eidos adapter for Minerva — export entities and research results as Eidos types.

Usage:
    from minerva.knowledge.eidos_adapter import entity_to_node, research_result_to_card

Optional — Eidos is not a hard dependency. All functions gracefully degrade.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---- Optional Eidos import ----
EIDOS_AVAILABLE = False


class _MissingEidosType:
    pass


KnowledgeCard: type = _MissingEidosType
OntologyNode: type = _MissingEidosType
try:
    from eidos.types import KnowledgeCard, OntologyNode  # type: ignore[no-redef]

    EIDOS_AVAILABLE = True
except ImportError:
    logger.debug("Eidos not available — using Minerva native formats only")


def is_eidos_available() -> bool:
    return EIDOS_AVAILABLE


def entity_to_node(entity: Any) -> Any | None:
    """Convert Minerva Entity to Eidos OntologyNode."""
    if not EIDOS_AVAILABLE:
        return None

    props = dict(entity.properties) if entity.properties else {}
    return OntologyNode(
        id=entity.id,
        name=entity.name,
        node_type=entity.type,  # Already MetaType-normalized
        parent="",
        properties=props,
        aliases=list(entity.aliases) if entity.aliases else [],
        description="",
    )


def research_result_to_card(result: dict[str, Any]) -> Any | None:
    """Convert Minerva research result dict to Eidos KnowledgeCard."""
    if not EIDOS_AVAILABLE:
        return None

    import datetime

    card_id = result.get("id", f"card_{result.get('title', 'unknown')[:20]}")
    tags = result.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    return KnowledgeCard(
        id=card_id,
        title=result.get("title", "Untitled"),
        content=result.get("content") or result.get("snippet") or "",
        source=result.get("source", "minerva"),
        source_type=result.get("source_type", "research"),
        schema_type="KnowledgeCard",
        tags=tags,
        created_at=result.get("created_at", datetime.datetime.now().isoformat()),
    )


def export_cards_to_json(cards: list[Any], path: str | Path) -> int:
    """Export Eidos KnowledgeCards to a JSON file."""
    if not EIDOS_AVAILABLE:
        return 0

    data = [card.to_dict() for card in cards]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(cards)


def export_to_kos(cards: list[Any], kos_script: str | None = None) -> dict[str, Any]:
    """Export KnowledgeCards to KOS by writing a temp JSON and using kos ingest.

    Args:
        cards: List of Eidos KnowledgeCard instances
        kos_script: Path to kos-cli.py

    Returns:
        Dict with status and count
    """
    if not cards:
        return {"status": "skipped", "count": 0}

    if kos_script is None:
        import shutil

        kos_script = shutil.which("kos") or "kos"

    data = [c.to_dict() for c in cards]
    fd, tmp_path = tempfile.mkstemp(suffix=".json")
    tmp = Path(tmp_path)
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.close(fd)

    try:
        result = subprocess.run(
            [kos_script, "ingest", str(tmp), "--schema", "KnowledgeCard", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {"status": "done", "count": len(cards), "kos_output": result.stdout[:200]}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        tmp.unlink(missing_ok=True)
