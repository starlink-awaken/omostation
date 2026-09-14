"""Backend ports and in-process implementations for MOS."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SearchBackend(Protocol):
    name: str

    def search(self, query: str, *, limit: int = 10, scope: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...


@runtime_checkable
class ThetaBackend(Protocol):
    """Searchable theta track (facts/index upsert)."""

    def upsert(self, envelope: dict[str, Any]) -> dict[str, Any]: ...

    def forget(self, memory_id: str) -> dict[str, Any]: ...


@runtime_checkable
class RawBackend(Protocol):
    """Auditable raw track."""

    def emit(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]: ...


@dataclass
class InMemoryRawBackend:
    """Append-only raw audit log for tests and offline use."""

    events: list[dict[str, Any]] = field(default_factory=list)

    def emit(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        record = {"event_type": event_type, "payload": dict(payload), "id": f"raw_{len(self.events) + 1}"}
        self.events.append(record)
        return {"ok": True, "id": record["id"]}


@dataclass
class InMemoryThetaBackend:
    """In-process searchable store for theta track."""

    docs: list[dict[str, Any]] = field(default_factory=list)
    forgotten_ids: set[str] = field(default_factory=set)
    fail_next: bool = False

    def upsert(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("theta backend forced failure")
        scope = envelope.get("scope") or {}
        text = envelope.get("content") or envelope.get("content_ref") or ""
        graph = envelope.get("graph") or {}
        if not text and graph.get("subject"):
            text = f"{graph.get('subject')} {graph.get('predicate')} {graph.get('object') or ''}"
        doc = {
            "id": envelope.get("id"),
            "type": envelope.get("type"),
            "text": text,
            "content_hash": (envelope.get("provenance") or {}).get("content_hash"),
            "metadata": envelope.get("metadata") or {},
            "principal_id": scope.get("principal_id"),
            "agent_profile": scope.get("agent_profile"),
            "scene_id": scope.get("scene_id"),
            "forgotten": False,
        }
        mid = str(doc.get("id") or "")
        if mid in self.forgotten_ids:
            self.forgotten_ids.discard(mid)
        # replace same id
        self.docs = [d for d in self.docs if d.get("id") != doc["id"]]
        self.docs.append(doc)
        return {"ok": True, "id": doc["id"]}

    def forget(self, memory_id: str) -> dict[str, Any]:
        mid = str(memory_id)
        self.forgotten_ids.add(mid)
        found = False
        for d in self.docs:
            if str(d.get("id")) == mid:
                d["forgotten"] = True
                found = True
        return {"ok": True, "id": mid, "found": found}

    def search(self, query: str, *, limit: int = 10, scope: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        q = (query or "").lower()
        hits = []
        for d in self.docs:
            if d.get("forgotten") or str(d.get("id")) in self.forgotten_ids:
                continue
            text = str(d.get("text") or "").lower()
            if not q or q in text or any(tok and tok in text for tok in q.split()):
                hits.append(
                    {
                        "id": d.get("id"),
                        "title": d.get("id"),
                        "snippet": str(d.get("text") or "")[:200],
                        "backend": "theta",
                        "score": 1.0,
                        "principal_id": d.get("principal_id"),
                        "agent_profile": d.get("agent_profile"),
                        "scene_id": d.get("scene_id"),
                    }
                )
        return hits[:limit]


@dataclass
class InMemorySearchBackend:
    name: str
    docs: list[dict[str, Any]] = field(default_factory=list)
    fail: bool = False

    def search(self, query: str, *, limit: int = 10, scope: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if self.fail:
            raise RuntimeError(f"backend {self.name} offline")
        q = (query or "").lower()
        hits: list[dict[str, Any]] = []
        for d in self.docs:
            text = " ".join(str(d.get(k, "")) for k in ("title", "snippet", "text", "path")).lower()
            if not q or q in text or any(tok and tok in text for tok in q.split()):
                hit = dict(d)
                hit.setdefault("backend", self.name)
                hit.setdefault("id", d.get("id") or d.get("path") or d.get("title"))
                hits.append(hit)
        return hits[:limit]
