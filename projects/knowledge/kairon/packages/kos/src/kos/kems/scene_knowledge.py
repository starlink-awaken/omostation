"""Scene Knowledge Graph Integration.

Registers documents scene cards as GraphEntity nodes in KEMS GraphStore,
enabling evidence-based traceability from scene execution to knowledge graph.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

from kos.kems.graph_store import GraphEntity, GraphRelation, GraphStore, ReviewState


class SceneKnowledgeGraph:
    """Scene ↔ Knowledge Graph bridge.

    Registers scene cards as GraphEntity nodes and journey state transitions
    as GraphRelation edges, enabling full evidence traceability.
    """

    def __init__(self, store: GraphStore | None = None):
        self.store = store or GraphStore()

    def register_scene(self, scene_card: dict[str, Any]) -> GraphEntity:
        """Register a scene card as a GraphEntity."""
        entity = GraphEntity(
            entity_id=f"scene:{scene_card['scene_id']}",
            entity_type="SceneCard",
            canonical_name=scene_card.get("goal", scene_card["scene_id"]),
            source_document_id=f"docs/scene-cards/{scene_card['scene_id']}.yaml",
            evidence_span=json.dumps(scene_card.get("architecture", {})),
            confidence=1.0,
            review_state="machine",
            valid_from=datetime.now(UTC).isoformat(),
            valid_to=None,
        )
        return self.store.upsert_entity(entity)

    def register_journey_state(
        self,
        scene_id: str,
        state: str,
        next_state: str | None = None,
        evidence_path: str | None = None,
    ) -> GraphRelation:
        """Register a journey state transition as a GraphRelation."""
        relation = GraphRelation(
            relation_id=f"transition:{scene_id}:{state}->{next_state}",
            subject_id=f"scene:{scene_id}",
            predicate="HAS_STATE" if next_state is None else "TRANSITIONS_TO",
            object_id=f"state:{state}" if next_state is None else f"state:{next_state}",
            evidence_refs=(evidence_path,) if evidence_path else (),
            confidence=1.0,
            review_state="machine",
        )
        return self.store.upsert_relation(relation)

    def record_evidence(
        self,
        scene_id: str,
        outcome_id: str,
        evidence_path: str,
        success_rate: float = 1.0,
        approved: bool = False,
    ) -> GraphRelation:
        """Record scene execution outcome as evidence."""
        relation = GraphRelation(
            relation_id=f"outcome:{scene_id}:{outcome_id}",
            subject_id=f"scene:{scene_id}",
            predicate="HAS_OUTCOME",
            object_id=f"outcome:{outcome_id}",
            evidence_refs=(evidence_path,),
            confidence=success_rate,
            review_state="human_verified" if approved else "machine",
        )
        return self.store.upsert_relation(relation)

    def register_all_scenes(self, scenes_dir: str = "docs/scene-cards") -> int:
        """Register all scene cards from directory."""
        count = 0
        scenes_path = Path(scenes_dir)
        for scene_file in sorted(scenes_path.glob("documents-*.yaml")):
            # Parse YAML frontmatter
            content = scene_file.read_text(encoding="utf-8")
            scene_card = self._parse_scene_card(content, scene_file.stem)
            if scene_card:
                self.register_scene(scene_card)
                count += 1
        return count

    def _parse_scene_card(self, content: str, scene_id: str) -> dict[str, Any] | None:
        """Parse scene card YAML content."""
        try:
            import yaml
            # Extract YAML between --- markers
            parts = content.split("---")
            if len(parts) >= 3:
                data = yaml.safe_load(parts[1])
                data["scene_id"] = scene_id
                if len(parts) > 2:
                    body = yaml.safe_load("---".join(parts[2:]))
                    if body:
                        data.update(body)
                return data
        except Exception:
            return None
        return None


def register_documents_scenes() -> int:
    """Convenience function to register all documents scenes."""
    bridge = SceneKnowledgeGraph()
    return bridge.register_all_scenes()
