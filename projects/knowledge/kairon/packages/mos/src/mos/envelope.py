"""MemoryEnvelope validation (ADR-0372)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

MEMORY_TYPES = frozenset(
    {
        "working",
        "episodic",
        "semantic",
        "procedural",
        "institutional",
        "governance_ref",
    }
)
PII_CLASSES = frozenset({"none", "low", "high"})
LIFECYCLE_STATUSES = frozenset({"raw", "consolidated", "pinned", "forgotten"})


class ValidationError(ValueError):
    """Invalid MemoryEnvelope."""


@dataclass
class MemoryEnvelope:
    """Canonical memory write envelope."""

    type: str
    content: str | None = None
    content_ref: str | None = None
    id: str | None = None
    principal_id: str | None = None
    agent_profile: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    scene_id: str | None = None
    source: str = "kairon"
    content_hash: str | None = None
    pii_class: str = "none"
    salience: float = 0.5
    confidence: float = 0.8
    lifecycle_status: str = "raw"
    metadata: dict[str, Any] = field(default_factory=dict)
    # Bi-temporal fields (Graphiti-aligned shadow model)
    valid_from: str | None = None
    valid_to: str | None = None
    ingested_at: str | None = None
    invalidated_at: str | None = None
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None

    def body_text(self) -> str:
        return (self.content or "") if self.content is not None else ""

    def ensure_hash(self) -> str:
        if self.content_hash:
            return self.content_hash
        payload = self.content or self.content_ref or ""
        if self.subject and self.predicate:
            payload = f"{self.subject}|{self.predicate}|{self.object or ''}|{payload}"
        self.content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self.content_hash

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "content_ref": self.content_ref,
            "scope": {
                "principal_id": self.principal_id,
                "agent_profile": self.agent_profile,
                "session_id": self.session_id,
                "run_id": self.run_id,
                "scene_id": self.scene_id,
            },
            "temporal": {
                "valid_from": self.valid_from,
                "valid_to": self.valid_to,
                "ingested_at": self.ingested_at,
                "invalidated_at": self.invalidated_at,
            },
            "graph": {
                "subject": self.subject,
                "predicate": self.predicate,
                "object": self.object,
            },
            "provenance": {
                "source": self.source,
                "content_hash": self.ensure_hash(),
            },
            "governance": {"pii_class": self.pii_class},
            "lifecycle": {"status": self.lifecycle_status, "salience": self.salience},
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


def _as_envelope(data: MemoryEnvelope | dict[str, Any]) -> MemoryEnvelope:
    if isinstance(data, MemoryEnvelope):
        return data
    if not isinstance(data, dict):
        raise ValidationError("envelope must be a dict or MemoryEnvelope")
    scope = data.get("scope") or {}
    prov = data.get("provenance") or {}
    gov = data.get("governance") or {}
    life = data.get("lifecycle") or {}
    temporal = data.get("temporal") or {}
    graph = data.get("graph") or {}
    return MemoryEnvelope(
        id=data.get("id"),
        type=str(data.get("type") or ""),
        content=data.get("content"),
        content_ref=data.get("content_ref"),
        principal_id=scope.get("principal_id") or data.get("principal_id"),
        agent_profile=scope.get("agent_profile") or data.get("agent_profile"),
        session_id=scope.get("session_id") or data.get("session_id"),
        run_id=scope.get("run_id") or data.get("run_id"),
        scene_id=scope.get("scene_id") or data.get("scene_id"),
        source=str(prov.get("source") or data.get("source") or "kairon"),
        content_hash=prov.get("content_hash") or data.get("content_hash"),
        pii_class=str(gov.get("pii_class") or data.get("pii_class") or "none"),
        salience=float(life.get("salience") if life.get("salience") is not None else data.get("salience", 0.5)),
        confidence=float(data.get("confidence", 0.8)),
        lifecycle_status=str(life.get("status") or data.get("lifecycle_status") or "raw"),
        metadata=dict(data.get("metadata") or {}),
        valid_from=temporal.get("valid_from") or data.get("valid_from"),
        valid_to=temporal.get("valid_to") or data.get("valid_to"),
        ingested_at=temporal.get("ingested_at") or data.get("ingested_at"),
        invalidated_at=temporal.get("invalidated_at") or data.get("invalidated_at"),
        subject=graph.get("subject") or data.get("subject"),
        predicate=graph.get("predicate") or data.get("predicate"),
        object=graph.get("object") or data.get("object"),
    )


def validate_envelope(data: MemoryEnvelope | dict[str, Any]) -> MemoryEnvelope:
    """Validate and normalize a MemoryEnvelope. Raises ValidationError."""
    env = _as_envelope(data)
    if env.type not in MEMORY_TYPES:
        raise ValidationError(f"invalid type {env.type!r}; expected one of {sorted(MEMORY_TYPES)}")
    # Triple writes may omit free-text body
    has_triple = bool(env.subject and env.predicate)
    if not env.content and not env.content_ref and not has_triple:
        raise ValidationError("either content, content_ref, or subject+predicate is required")
    if env.pii_class not in PII_CLASSES:
        raise ValidationError(f"invalid pii_class {env.pii_class!r}")
    if env.lifecycle_status not in LIFECYCLE_STATUSES:
        raise ValidationError(f"invalid lifecycle status {env.lifecycle_status!r}")
    if env.pii_class == "high" and env.content and not env.content_ref:
        # High PII must not travel as raw body into audit track as sole form
        raise ValidationError("high pii_class requires content_ref; omit inline content for raw track safety")
    if not (0.0 <= env.salience <= 1.0):
        raise ValidationError("salience must be in [0, 1]")
    if not (0.0 <= env.confidence <= 1.0):
        raise ValidationError("confidence must be in [0, 1]")
    env.ensure_hash()
    if env.id is None:
        # Stable-ish id from type+hash prefix
        env.id = f"mem_{env.type}_{env.content_hash[:12]}"
    elif not re.match(r"^[\w.:\-]+$", env.id):
        raise ValidationError("id contains invalid characters")
    return env
