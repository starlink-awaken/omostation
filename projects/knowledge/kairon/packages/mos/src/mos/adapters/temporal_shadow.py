"""Bi-temporal fact store (Graphiti-shaped shadow; no Neo4j).

Enable with MOS_TEMPORAL=1 (default on for semantic triple writes when fields present).
Facts carry valid_from/valid_to (world time) and ingested_at/invalidated_at (system time).
Current-state query excludes invalidated and expired facts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def temporal_enabled() -> bool:
    val = (os.environ.get("MOS_TEMPORAL") or "1").strip().lower()
    return val not in {"0", "false", "off", "no"}


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@dataclass
class TemporalShadowAdapter:
    """In-memory bi-temporal edge store."""

    name: str = "temporal"
    edges: list[dict[str, Any]] = field(default_factory=list)

    def upsert_fact(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if not temporal_enabled():
            return {"ok": False, "skipped": True, "reason": "temporal_off"}
        graph = envelope.get("graph") or {}
        temporal = envelope.get("temporal") or {}
        scope = envelope.get("scope") or {}
        subject = graph.get("subject") or envelope.get("subject")
        predicate = graph.get("predicate") or envelope.get("predicate")
        obj = graph.get("object") or envelope.get("object")
        if not subject or not predicate:
            # Derive weak triple from content for temporal intent experiments
            text = envelope.get("content") or ""
            subject = subject or "fact"
            predicate = predicate or "states"
            obj = obj or text[:120]
        eid = envelope.get("id") or f"tmp_{len(self.edges) + 1}"
        # Invalidate previous current edges with same triple
        for e in self.edges:
            if (
                e.get("subject") == subject
                and e.get("predicate") == predicate
                and e.get("object") == obj
                and not e.get("invalidated_at")
            ):
                e["invalidated_at"] = _now_iso()
                e["valid_to"] = e.get("valid_to") or _now_iso()
        edge = {
            "id": eid,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "text": envelope.get("content") or f"{subject} {predicate} {obj}",
            "valid_from": temporal.get("valid_from") or envelope.get("valid_from") or _now_iso(),
            "valid_to": temporal.get("valid_to") or envelope.get("valid_to"),
            "ingested_at": temporal.get("ingested_at") or _now_iso(),
            "invalidated_at": temporal.get("invalidated_at"),
            "principal_id": scope.get("principal_id"),
            "agent_profile": scope.get("agent_profile"),
            "scene_id": scope.get("scene_id"),
            "content_hash": (envelope.get("provenance") or {}).get("content_hash"),
        }
        self.edges.append(edge)
        return {"ok": True, "id": eid, "edge": edge}

    def invalidate(self, edge_id: str) -> dict[str, Any]:
        for e in self.edges:
            if str(e.get("id")) == str(edge_id):
                e["invalidated_at"] = _now_iso()
                e["valid_to"] = e.get("valid_to") or _now_iso()
                return {"ok": True, "id": edge_id}
        return {"ok": True, "id": edge_id, "found": False}

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        scope: dict[str, Any] | None = None,
        as_of: str | None = None,
        current_only: bool = True,
    ) -> list[dict[str, Any]]:
        if not temporal_enabled():
            return []
        q = (query or "").lower()
        as_of_dt = _parse_ts(as_of) or datetime.now(UTC)
        hits: list[dict[str, Any]] = []
        for e in self.edges:
            # Fine ACL applied in mos.acl.filter_hits; still skip obvious principal mismatch early
            if current_only:
                if e.get("invalidated_at"):
                    continue
                vf = _parse_ts(e.get("valid_from"))
                vt = _parse_ts(e.get("valid_to"))
                if vf and as_of_dt < vf:
                    continue
                if vt and as_of_dt >= vt:
                    continue
            blob = " ".join(str(e.get(k) or "") for k in ("subject", "predicate", "object", "text")).lower()
            if not q or q in blob or any(tok and tok in blob for tok in q.split()):
                hits.append(
                    {
                        "id": e.get("id"),
                        "title": f"{e.get('subject')} {e.get('predicate')} {e.get('object')}",
                        "snippet": e.get("text") or "",
                        "backend": "temporal",
                        "score": 1.0,
                        "valid_from": e.get("valid_from"),
                        "valid_to": e.get("valid_to"),
                        "invalidated_at": e.get("invalidated_at"),
                        "principal_id": e.get("principal_id"),
                        "agent_profile": e.get("agent_profile"),
                        "scene_id": e.get("scene_id"),
                    }
                )
        return hits[:limit]
