#!/usr/bin/env python3
"""Decision Inbox — Scene Card 决策收件箱核心引擎.

The decision inbox is a P0 business scenario: collect raw intents from
multiple sources (email, file, message, manual, oa, sms), structure them
into a decision list, and drive the lifecycle:

    pending → task_created → approved/rejected → done

SSOT:  ecos/src/ecos/ssot/registry/scene-cards.yaml
Engine: bin/ssot/scene-card-decision-inbox.py
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Data types ──

@dataclass
class StructuredContent:
    title: str | None = None
    description: str | None = None
    category: str | None = None
    deadline: str | None = None
    related_knowledge: list[str] = field(default_factory=list)
    confidence: float | None = None


@dataclass
class EvidenceRecord:
    source: str = ""
    action: str = ""
    result: str = ""
    timestamp: str = ""
    actor: str | None = None


@dataclass
class IntentCard:
    id: str = ""
    journey_id: str = ""
    source: str = "manual"
    raw_content: str = ""
    structured: StructuredContent | None = None
    status: str = "pending"
    priority: str = "P3"
    task_id: str | None = None
    created_at: str = ""
    processed_at: str | None = None
    evidence: list[EvidenceRecord] = field(default_factory=list)


@dataclass
class JourneyCard:
    id: str = ""
    scene_id: str = ""
    name: str = ""
    status: str = "proposed"
    created_at: str = ""
    completed_at: str | None = None
    intents: list[IntentCard] = field(default_factory=list)


@dataclass
class SceneCard:
    id: str = ""
    name: str = ""
    description: str = ""
    status: str = "active"
    priority: str = "P1"
    created_at: str = ""
    journeys: list[JourneyCard] = field(default_factory=list)


# ── Helpers ──

def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _dictify(obj: Any) -> Any:
    """Convert dataclass to dict, handling nested dataclasses."""
    if isinstance(obj, list):
        return [_dictify(item) for item in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _dictify(v) for k, v in asdict(obj).items() if v is not None}
    return obj


# ── Storage ──

def _inbox_path(workspace_root: Path) -> Path:
    p = workspace_root / ".omo" / "_inbox"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _scene_path(workspace_root: Path, scene_id: str) -> Path:
    p = _inbox_path(workspace_root) / f"{scene_id}.json"
    return p


def load_scene(workspace_root: Path, scene_id: str) -> SceneCard | None:
    p = _scene_path(workspace_root, scene_id)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return _scene_from_dict(data)


def _scene_from_dict(data: dict) -> SceneCard:
    journeys = []
    for jd in data.get("journeys", []):
        intents = []
        for ind in jd.get("intents", []):
            structured = None
            if sd := ind.get("structured"):
                structured = StructuredContent(**sd)
            evidence = [EvidenceRecord(**e) for e in ind.get("evidence", [])]
            intents.append(IntentCard(
                id=ind.get("id", ""),
                journey_id=ind.get("journey_id", ""),
                source=ind.get("source", "manual"),
                raw_content=ind.get("raw_content", ""),
                structured=structured,
                status=ind.get("status", "pending"),
                priority=ind.get("priority", "P3"),
                task_id=ind.get("task_id"),
                created_at=ind.get("created_at", ""),
                processed_at=ind.get("processed_at"),
                evidence=evidence,
            ))
        journeys.append(JourneyCard(
            id=jd.get("id", ""),
            scene_id=jd.get("scene_id", ""),
            name=jd.get("name", ""),
            status=jd.get("status", "proposed"),
            created_at=jd.get("created_at", ""),
            completed_at=jd.get("completed_at"),
            intents=intents,
        ))
    return SceneCard(
        id=data.get("id", ""),
        name=data.get("name", ""),
        description=data.get("description", ""),
        status=data.get("status", "active"),
        priority=data.get("priority", "P1"),
        created_at=data.get("created_at", ""),
        journeys=journeys,
    )


def save_scene(workspace_root: Path, scene: SceneCard) -> None:
    p = _scene_path(workspace_root, scene.id)
    p.write_text(json.dumps(_dictify(scene), indent=2, ensure_ascii=False))


def list_scenes(workspace_root: Path) -> list[SceneCard]:
    p = _inbox_path(workspace_root)
    scenes = []
    for f in sorted(p.glob("scene-*.json")):
        data = json.loads(f.read_text())
        scenes.append(_scene_from_dict(data))
    return scenes


# ── Core operations ──

def create_scene(
    workspace_root: Path,
    name: str,
    description: str,
    priority: str = "P1",
) -> SceneCard:
    scene_id = _new_id("scene")
    scene = SceneCard(
        id=scene_id,
        name=name,
        description=description,
        status="active",
        priority=priority,
        created_at=_now_iso(),
    )
    save_scene(workspace_root, scene)
    return scene


def create_journey(
    workspace_root: Path,
    scene_id: str,
    name: str,
) -> JourneyCard:
    scene = load_scene(workspace_root, scene_id)
    if scene is None:
        raise ValueError(f"Scene {scene_id} not found")
    journey = JourneyCard(
        id=_new_id("journey"),
        scene_id=scene_id,
        name=name,
        status="proposed",
        created_at=_now_iso(),
    )
    scene.journeys.append(journey)
    save_scene(workspace_root, scene)
    return journey


def add_intent(
    workspace_root: Path,
    scene_id: str,
    journey_id: str,
    source: str,
    raw_content: str,
    priority: str = "P3",
) -> IntentCard:
    scene = load_scene(workspace_root, scene_id)
    if scene is None:
        raise ValueError(f"Scene {scene_id} not found")
    journey = next((j for j in scene.journeys if j.id == journey_id), None)
    if journey is None:
        raise ValueError(f"Journey {journey_id} not found in scene {scene_id}")
    intent = IntentCard(
        id=_new_id("intent"),
        journey_id=journey_id,
        source=source,
        raw_content=raw_content,
        status="pending",
        priority=priority,
        created_at=_now_iso(),
        evidence=[EvidenceRecord(
            source=source,
            action="ingested",
            result="intent_created",
            timestamp=_now_iso(),
        )],
    )
    journey.intents.append(intent)
    save_scene(workspace_root, scene)
    return intent


def list_intents(
    workspace_root: Path,
    scene_id: str,
    status_filter: str | None = None,
) -> list[IntentCard]:
    scene = load_scene(workspace_root, scene_id)
    if scene is None:
        raise ValueError(f"Scene {scene_id} not found")
    all_intents: list[IntentCard] = []
    for j in scene.journeys:
        all_intents.extend(j.intents)
    if status_filter:
        all_intents = [i for i in all_intents if i.status == status_filter]
    return all_intents


def update_intent_status(
    workspace_root: Path,
    intent_id: str,
    new_status: str,
    task_id: str | None = None,
    actor: str | None = None,
) -> IntentCard | None:
    valid_statuses = {"pending", "task_created", "approved", "rejected", "done"}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid status: {new_status}. Valid: {valid_statuses}")

    scenes = list_scenes(workspace_root)
    for scene in scenes:
        for journey in scene.journeys:
            for intent in journey.intents:
                if intent.id == intent_id:
                    intent.status = new_status
                    intent.processed_at = _now_iso()
                    if task_id:
                        intent.task_id = task_id
                    intent.evidence.append(EvidenceRecord(
                        source="decision_inbox",
                        action="status_update",
                        result=f"{new_status}",
                        timestamp=_now_iso(),
                        actor=actor,
                    ))
                    save_scene(workspace_root, scene)
                    return intent
    return None


def get_inbox_summary(workspace_root: Path) -> dict[str, Any]:
    """Return a summary of all pending intents across all scenes."""
    scenes = list_scenes(workspace_root)
    total_intents = 0
    pending_intents = 0
    by_source: dict[str, int] = {}
    by_priority: dict[str, int] = {}

    for scene in scenes:
        for journey in scene.journeys:
            for intent in journey.intents:
                total_intents += 1
                if intent.status == "pending":
                    pending_intents += 1
                by_source[intent.source] = by_source.get(intent.source, 0) + 1
                by_priority[intent.priority] = by_priority.get(intent.priority, 0) + 1

    return {
        "scene_count": len(scenes),
        "total_intents": total_intents,
        "pending_intents": pending_intents,
        "by_source": by_source,
        "by_priority": by_priority,
        "generated_at": _now_iso(),
    }
