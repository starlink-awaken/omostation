"""Unified memory access (T6-02): bos://memory/unified front-door over MemoryOS.

Merges the knowledge-layer access paths (vector / graph / long-term episodic)
behind one intent-routed surface. Reuses MemoryOS (write/recall/forget) and
routing (classify_intent / backends_for_intent / rrf_fuse) as the single source
of truth — no new adapter logic lives here.
"""

from __future__ import annotations

from typing import Any

from mos.envelope import MemoryEnvelope, validate_envelope
from mos.routing import backends_for_intent, classify_intent, rrf_fuse
from mos.service import MemoryOS, RecallResult, WriteResult

# BOS namespace this surface registers under.
UNIFIED_NAMESPACE = "bos://memory/unified"


class UnifiedMemory:
    """Single front-door for knowledge-layer memory write/recall/search.

    All operations are intent-routed and delegated to a shared MemoryOS
    instance; the unified layer only adds the bos://memory/unified contract
    (scope envelopes, dedup, conflict pre-check) on top.
    """

    def __init__(self, memory_os: MemoryOS | None = None) -> None:
        self._mos = memory_os or MemoryOS()

    @property
    def memory_os(self) -> MemoryOS:
        return self._mos

    # ── write ────────────────────────────────────────────────────────────
    def unified_write(
        self,
        content: str,
        *,
        scope: str | None = None,
        principal_id: str | None = None,
        agent_profile: str | None = None,
        type: str = "episodic",
        dedup: bool = True,
        role: str | None = None,
    ) -> WriteResult:
        """Write one memory through the unified surface.

        ``dedup=True`` runs a conflict pre-check via recall and skips the write
        when a near-duplicate already exists (memory conflict elimination).
        """
        if dedup and content:
            probe = self.unified_search(content, limit=1, role=role)
            for hit in probe:
                stored = str(hit.get("content") or hit.get("text") or hit.get("snippet") or hit.get("title") or "")
                if stored and (stored == content or stored.startswith(content[:64])):
                    return WriteResult(
                        ok=True,
                        envelope_id=str(hit.get("id") or hit.get("envelope_id") or "dedup-skip"),
                        dual_track=_SKIP_DUAL_TRACK,
                        content_hash="dedup-skip",
                    )
        env = MemoryEnvelope(
            content=content,
            type=type,
            principal_id=principal_id or "default",
            agent_profile=agent_profile or "governance-agent",
            metadata={"scope": scope or "default"},
        )
        return self._mos.write(env, role=role)

    # ── recall ───────────────────────────────────────────────────────────
    def unified_recall(
        self,
        query: str,
        *,
        intent: str | None = None,
        limit: int = 10,
        as_of: str | None = None,
        role: str | None = None,
        agent_profile: str | None = None,
    ) -> RecallResult:
        """Intent-routed recall. Falls back to RRF fusion over routed backends."""
        resolved = classify_intent(query, explicit=intent)
        result = self._mos.recall(
            query,
            intent=resolved,
            limit=limit,
            as_of=as_of,
            role=role,
            scope={"agent_profile": agent_profile or "governance-agent"},
        )
        if result.hits:
            return result
        # Empty from the primary path — fall back to RRF over routed backends.
        fused = self.unified_search(query, intent=resolved, limit=limit, role=role)
        return RecallResult(query=query, intent=resolved, hits=fused, empty=not fused)

    # ── search ───────────────────────────────────────────────────────────
    def unified_search(
        self,
        query: str,
        *,
        intent: str | None = None,
        limit: int = 10,
        role: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search across all backends for an intent, fused by RRF."""
        resolved = classify_intent(query, explicit=intent)
        ranked: list[list[dict[str, Any]]] = []
        for backend in backends_for_intent(resolved):
            try:
                hits = self._mos.recall(
                    query,
                    intent=resolved,
                    limit=max(limit * 3, 30),
                    role=role,
                )
            except Exception:
                hits = None
            if hits is not None and hits.hits:
                tagged = [dict(h) | {"backend": backend} for h in hits.hits]
                ranked.append(tagged)
        return rrf_fuse(ranked, limit=limit)

    # ── status ───────────────────────────────────────────────────────────
    def unified_status(self) -> dict[str, Any]:
        """Backend availability for the unified surface (diagnostics)."""
        from mos.service import RecallResult as _R  # noqa: F401

        try:
            probe = self._mos.recall("__unified_status_probe__", limit=1)
            return {"ok": True, "intent": probe.intent, "backend_status": probe.backend_status}
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "error": str(exc)}


# Shared "skipped by dedup" dual-track placeholder (raw+theta both skipped).
class _SkipDualTrack:
    raw_ok = True
    raw_id = ""
    theta_ok = False
    theta_id = ""
    degraded = True
    skipped_theta = True
    theta_error = "dedup-skip"
    reason = "dedup-skip (duplicate write suppressed)"


_SKIP_DUAL_TRACK = _SkipDualTrack()


def default_unified_memory() -> UnifiedMemory:
    """Convenience factory with a fresh in-memory MemoryOS."""
    return UnifiedMemory()
