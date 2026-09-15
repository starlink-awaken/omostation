"""Mem0 shadow adapter — local, no Qdrant; feature-flagged (ADR-0372 Phase 2).

Default OFF. Enable with MOS_MEM0=1 or MOS_MEM0=on.
Does not import mem0ai; mirrors add/search/forget for dual-write evaluation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def mem0_enabled() -> bool:
    val = (os.environ.get("MOS_MEM0") or "").strip().lower()
    return val in {"1", "true", "on", "yes", "shadow"}


@dataclass
class Mem0ShadowAdapter:
    """In-process preference store used when MOS_MEM0 is on."""

    name: str = "mem0"
    docs: list[dict[str, Any]] = field(default_factory=list)
    forgotten: set[str] = field(default_factory=set)

    @property
    def enabled(self) -> bool:
        return mem0_enabled()

    def add(self, text: str, *, user_id: str = "default", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "skipped": True, "reason": "mem0_off"}
        mid = f"mem0_{len(self.docs) + 1}"
        doc = {
            "id": mid,
            "text": text,
            "user_id": user_id,
            "metadata": metadata or {},
        }
        self.docs.append(doc)
        return {"ok": True, "id": mid}

    def search(self, query: str, *, limit: int = 10, scope: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        q = (query or "").lower()
        hits: list[dict[str, Any]] = []
        for d in self.docs:
            if d["id"] in self.forgotten:
                continue
            text = str(d.get("text") or "").lower()
            if not q or q in text or any(tok and tok in text for tok in q.split()):
                hits.append(
                    {
                        "id": d["id"],
                        "title": d["id"],
                        "snippet": str(d.get("text") or "")[:200],
                        "backend": "mem0",
                        "score": 1.0,
                    }
                )
        return hits[:limit]

    def forget(self, memory_id: str) -> dict[str, Any]:
        if not self.enabled:
            return {"ok": False, "skipped": True}
        self.forgotten.add(memory_id)
        return {"ok": True, "id": memory_id}
