"""MemoryOS control plane: write / recall / forget / status."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC
from typing import Any

from mos.acl import filter_hits
from mos.adapters.graphiti_bridge import backend_status as graphiti_backend_status
from mos.adapters.graphiti_bridge import build_temporal_backend
from mos.adapters.mem0_shadow import Mem0ShadowAdapter, mem0_enabled
from mos.adapters.temporal_shadow import TemporalShadowAdapter, temporal_enabled
from mos.backends import InMemoryRawBackend, InMemorySearchBackend, InMemoryThetaBackend, SearchBackend
from mos.consolidate import (
    ConsolidateResult,
    DreamRunner,
    measure_backlog,
    run_consolidate,
)
from mos.dual_track import DualTrackResult, DualTrackWriter
from mos.envelope import MemoryEnvelope, validate_envelope
from mos.neo4j_writer import Neo4jFactWriter, Neo4jSearchBackend, neo4j_configured
from mos.rbac import check_action, resolve_role
from mos.routing import backends_for_intent, classify_intent, rrf_fuse


def rbac_enforced() -> bool:
    """RBAC on by default; set MOS_RBAC=0 to disable (tests/dev)."""
    val = (os.environ.get("MOS_RBAC") or "1").strip().lower()
    return val not in {"0", "false", "off", "no"}


@dataclass
class WriteResult:
    ok: bool
    envelope_id: str
    dual_track: DualTrackResult
    content_hash: str
    mem0: dict[str, Any] | None = None
    temporal: dict[str, Any] | None = None
    neo4j: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        dt = self.dual_track
        out = {
            "ok": self.ok,
            "envelope_id": self.envelope_id,
            "content_hash": self.content_hash,
            "raw_id": dt.raw_id,
            "raw_ok": dt.raw_ok,
            "theta_ok": dt.theta_ok,
            "theta_id": dt.theta_id,
            "degraded": dt.degraded,
            "skipped_theta": dt.skipped_theta,
            "theta_error": dt.theta_error,
            "reason": dt.reason,
        }
        if self.mem0 is not None:
            out["mem0"] = self.mem0
        if self.temporal is not None:
            out["temporal"] = self.temporal
        if self.neo4j is not None:
            out["neo4j"] = self.neo4j
        return out


@dataclass
class KnowledgeRef:
    """ADR-0315 citation: metadata only, no body text."""

    ref_id: str
    query_hash: str
    hit_ids: list[str]
    intent: str | None
    scene_id: str | None
    principal_id: str | None
    created_from: str = "mos.recall"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ref_id": self.ref_id,
            "query_hash": self.query_hash,
            "hit_ids": self.hit_ids,
            "intent": self.intent,
            "scene_id": self.scene_id,
            "principal_id": self.principal_id,
            "created_from": self.created_from,
            "schema": "knowledge-action/v1",
        }


@dataclass
class ForgetResult:
    ok: bool
    memory_id: str
    dual_track: DualTrackResult
    mem0: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        dt = self.dual_track
        return {
            "ok": self.ok,
            "memory_id": self.memory_id,
            "raw_ok": dt.raw_ok,
            "raw_id": dt.raw_id,
            "theta_ok": dt.theta_ok,
            "degraded": dt.degraded,
            "theta_error": dt.theta_error,
            "mem0": self.mem0,
        }


@dataclass
class RecallResult:
    query: str
    intent: str
    hits: list[dict[str, Any]]
    backend_status: dict[str, str] = field(default_factory=dict)
    empty: bool = False

    @property
    def count(self) -> int:
        return len(self.hits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "intent": self.intent,
            "hits": self.hits,
            "backend_status": self.backend_status,
            "empty": self.empty or len(self.hits) == 0,
            "count": self.count,
        }


class MemoryOS:
    """Unified memory control surface."""

    def __init__(
        self,
        *,
        dual_track: DualTrackWriter | None = None,
        search_backends: dict[str, SearchBackend] | None = None,
        raw: InMemoryRawBackend | None = None,
        theta: InMemoryThetaBackend | None = None,
        mem0: Mem0ShadowAdapter | None = None,
        temporal: TemporalShadowAdapter | None = None,
        neo4j: Neo4jFactWriter | None = None,
        confidence_threshold: float = 0.6,
        dream_runner: DreamRunner | None = None,
        enforce_rbac: bool | None = None,
    ) -> None:
        self._raw = raw or InMemoryRawBackend()
        self._theta = theta or InMemoryThetaBackend()
        self._dual = dual_track or DualTrackWriter(self._raw, self._theta, confidence_threshold=confidence_threshold)
        self._mem0 = mem0 if mem0 is not None else Mem0ShadowAdapter()
        self._temporal = temporal if temporal is not None else build_temporal_backend()
        self._neo4j = neo4j if neo4j is not None else Neo4jFactWriter()
        self._dream = dream_runner
        self._enforce_rbac = rbac_enforced() if enforce_rbac is None else enforce_rbac
        self._last_consolidate: dict[str, Any] | None = None
        # Default offline-friendly backends; tests inject corpora
        self._search: dict[str, SearchBackend] = search_backends or {}
        # Theta store is also searchable under gbrain_facts when no override
        if "gbrain_facts" not in self._search:
            self._search["gbrain_facts"] = _ThetaAsSearch(self._theta, name="gbrain_facts")
        if "gbrain" not in self._search:
            self._search["gbrain"] = _ThetaAsSearch(self._theta, name="gbrain")
        if "mem0" not in self._search:
            self._search["mem0"] = self._mem0  # type: ignore[assignment]
        if "temporal" not in self._search:
            self._search["temporal"] = self._temporal  # type: ignore[assignment]
        # Production graph recall (NEO4J_URI-gated; empty hits when unset)
        if "neo4j" not in self._search:
            self._search["neo4j"] = Neo4jSearchBackend(writer=self._neo4j)

    def _authorize(
        self,
        action: str,
        *,
        role: str | None = None,
        agent_profile: str | None = None,
        principal_id: str | None = None,
    ) -> None:
        if not self._enforce_rbac:
            return
        check_action(action, role=role, agent_profile=agent_profile)

    @property
    def raw_backend(self) -> InMemoryRawBackend:
        return self._raw  # type: ignore[return-value]

    @property
    def theta_backend(self) -> InMemoryThetaBackend:
        return self._theta  # type: ignore[return-value]

    @property
    def mem0(self) -> Mem0ShadowAdapter:
        return self._mem0

    def write(
        self,
        envelope: MemoryEnvelope | dict[str, Any],
        *,
        role: str | None = None,
    ) -> WriteResult:
        env = validate_envelope(envelope)
        self._authorize(
            "write",
            role=role,
            agent_profile=env.agent_profile,
            principal_id=env.principal_id,
        )
        # Store principal on theta text metadata via dual track envelope
        dt = self._dual.write(env)
        mem0_res = None
        temporal_res = None
        neo4j_res = None
        # Shadow dual-write preferences/semantics when enabled
        if mem0_enabled() and env.type in {"semantic", "episodic"} and env.content:
            mem0_res = self._mem0.add(
                env.content,
                user_id=env.principal_id or "default",
                metadata={"envelope_id": env.id, "type": env.type},
            )
        # Temporal triple / bi-temporal fact (Graphiti-shaped shadow)
        env_dict = env.to_dict()
        if temporal_enabled() and ((env.subject and env.predicate) or (env.metadata or {}).get("temporal")):
            temporal_res = self._temporal.upsert_fact(env_dict)
        # Production Neo4j write when NEO4J_URI configured (Graphiti/FACT Cypher)
        if neo4j_configured() and ((env.subject and env.predicate) or (env.metadata or {}).get("temporal")):
            neo4j_res = self._neo4j.upsert_fact(env_dict)
        # Optional live gbrain put (MOS_LIVE_GBRAIN_WRITE=1) — does not replace dual-track
        gbrain_live_res = None
        try:
            from mos.adapters.live_backends import gbrain_put_page, live_gbrain_write_enabled

            if live_gbrain_write_enabled() and env.content and env.type in {"semantic", "episodic", "institutional"}:
                slug = f"mos/{env.type}/{(env.id or 'anon')[:48]}"
                gbrain_live_res = gbrain_put_page(slug, env.content)
        except Exception as exc:
            gbrain_live_res = {"ok": False, "error": str(exc)}
        result = WriteResult(
            ok=dt.raw_ok,
            envelope_id=env.id or "",
            dual_track=dt,
            content_hash=env.content_hash or "",
            mem0=mem0_res,
            temporal=temporal_res,
            neo4j=neo4j_res,
        )
        if gbrain_live_res is not None:
            # surface on write dict without expanding WriteResult schema hard
            result.mem0 = {**(mem0_res or {}), "gbrain_live": gbrain_live_res}
        return result

    def forget(
        self,
        memory_id: str,
        *,
        reason: str | None = None,
        role: str | None = None,
        agent_profile: str | None = None,
    ) -> ForgetResult:
        self._authorize("forget", role=role, agent_profile=agent_profile)
        dt = self._dual.forget(memory_id, reason=reason)
        mem0_res = self._mem0.forget(memory_id) if mem0_enabled() else {"ok": False, "skipped": True}
        neo4j_res = None
        if neo4j_configured():
            from datetime import datetime

            now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            neo4j_res = self._neo4j.invalidate(memory_id, now)
        result = ForgetResult(ok=dt.raw_ok, memory_id=memory_id, dual_track=dt, mem0=mem0_res)
        # attach neo4j on dict via mem0 slot pattern — extend to_dict below if needed
        if neo4j_res is not None:
            # ForgetResult has fixed fields; surface via dual_track reason is wrong —
            # stash on instance for CLI consumers
            result.mem0 = {**(mem0_res or {}), "neo4j": neo4j_res} if neo4j_res else mem0_res
        return result

    def recall(
        self,
        query: str,
        *,
        intent: str | None = None,
        scope: dict[str, Any] | None = None,
        limit: int = 20,
        as_of: str | None = None,
        role: str | None = None,
    ) -> RecallResult:
        scope = scope or {}
        self._authorize(
            "recall",
            role=role,
            agent_profile=scope.get("agent_profile"),
            principal_id=scope.get("principal_id"),
        )
        resolved = classify_intent(query, intent)
        names = backends_for_intent(resolved)
        # Skip mem0 backend when feature off
        if not mem0_enabled():
            names = [n for n in names if n != "mem0"]
        if not temporal_enabled():
            names = [n for n in names if n != "temporal"]
        # Drop neo4j from fan-out when URI unset (avoid noisy missing/degraded)
        if not neo4j_configured():
            names = [n for n in names if n != "neo4j"]
        ranked: list[list[dict[str, Any]]] = []
        status: dict[str, str] = {}
        for name in names:
            backend = self._search.get(name)
            if backend is None:
                status[name] = "missing"
                continue
            try:
                if name in {"temporal", "neo4j"} and hasattr(backend, "search"):
                    hits = backend.search(query, limit=limit, scope=scope, as_of=as_of)  # type: ignore[call-arg]
                else:
                    hits = backend.search(query, limit=limit, scope=scope)
                for h in hits:
                    h.setdefault("backend", name)
                hits = filter_hits(hits, scope)
                ranked.append(hits)
                status[name] = "ok"
            except Exception as exc:
                status[name] = f"degraded:{exc}"
        fused = rrf_fuse(ranked, limit=limit)
        fused = filter_hits(fused, scope)
        return RecallResult(
            query=query,
            intent=resolved,
            hits=fused,
            backend_status=status,
            empty=len(fused) == 0,
        )

    def create_knowledge_ref(
        self,
        query: str,
        *,
        intent: str | None = None,
        scope: dict[str, Any] | None = None,
        limit: int = 5,
        role: str | None = None,
    ) -> KnowledgeRef:
        """Build ADR-0315 knowledge citation from a recall (metadata only)."""
        import hashlib

        scope = scope or {}
        self._authorize(
            "knowledge_ref",
            role=role,
            agent_profile=scope.get("agent_profile"),
            principal_id=scope.get("principal_id"),
        )
        result = self.recall(query, intent=intent, scope=scope, limit=limit, role=role)
        hit_ids = [str(h.get("id")) for h in result.hits if h.get("id")]
        qh = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
        ref_id = f"kref_{qh}_{len(hit_ids)}"
        ref = KnowledgeRef(
            ref_id=ref_id,
            query_hash=qh,
            hit_ids=hit_ids,
            intent=result.intent,
            scene_id=(scope or {}).get("scene_id"),
            principal_id=(scope or {}).get("principal_id"),
        )
        # Raw audit without storing full body
        self._raw.emit(
            "memory.knowledge_ref",
            {
                "ref_id": ref.ref_id,
                "query_hash": ref.query_hash,
                "hit_ids": ref.hit_ids,
                "intent": ref.intent,
                "scene_id": ref.scene_id,
                "principal_id": ref.principal_id,
            },
        )
        return ref

    def consolidate(
        self,
        *,
        phases: list[str] | None = None,
        dry_run: bool = False,
        role: str | None = None,
        agent_profile: str | None = None,
    ) -> ConsolidateResult:
        """Sleep-time consolidation: orchestrate gbrain dream; emit raw audit event."""
        self._authorize("consolidate", role=role, agent_profile=agent_profile)
        before = measure_backlog(
            list(getattr(self._theta, "docs", []) or []),
            set(getattr(self._theta, "forgotten_ids", set()) or []),
        )
        result = run_consolidate(
            dream=self._dream,
            phases=phases,
            dry_run=dry_run,
            backlog_before=before,
        )
        after = measure_backlog(
            list(getattr(self._theta, "docs", []) or []),
            set(getattr(self._theta, "forgotten_ids", set()) or []),
        )
        result.backlog_after = after
        self._raw.emit(
            "memory.consolidate",
            {
                "ok": result.ok,
                "dry_run": dry_run,
                "phases": result.phases,
                "duration_ms": result.duration_ms,
                "degraded": result.degraded,
                "engine": (result.engine_report or {}).get("engine"),
            },
        )
        self._last_consolidate = result.to_dict()
        return result

    def status(self, *, role: str | None = None, agent_profile: str | None = None) -> dict[str, Any]:
        self._authorize("status", role=role, agent_profile=agent_profile)
        raw_n = len(getattr(self._raw, "events", []) or [])
        theta_n = len(getattr(self._theta, "docs", []) or [])
        forgotten = len(getattr(self._theta, "forgotten_ids", set()) or [])
        backlog = measure_backlog(
            list(getattr(self._theta, "docs", []) or []),
            set(getattr(self._theta, "forgotten_ids", set()) or []),
        )
        neo4j_ok = False
        try:
            neo4j_ok = bool(self._neo4j.available())
        except Exception:
            neo4j_ok = False
        last_c = self._last_consolidate
        return {
            "ok": True,
            "version": "0.10.0",
            "raw_events": raw_n,
            "theta_docs": theta_n,
            "forgotten": forgotten,
            "backlog": backlog,
            "last_consolidate": last_c,
            "consolidate": {
                "last": last_c,
                "ok": None if not last_c else bool(last_c.get("ok")),
                "dry_run": None if not last_c else bool(last_c.get("dry_run")),
                "degraded": None if not last_c else bool(last_c.get("degraded")),
                "duration_ms": None if not last_c else last_c.get("duration_ms"),
                "phases": None if not last_c else last_c.get("phases"),
            },
            "mem0_enabled": mem0_enabled(),
            "temporal_enabled": temporal_enabled(),
            "temporal_edges": len(getattr(self._temporal, "edges", []) or []),
            "neo4j_configured": neo4j_configured(),
            "neo4j_available": neo4j_ok,
            "neo4j_recall": neo4j_configured() and neo4j_ok,
            "neo4j_as_of": True,
            "rbac_enforced": self._enforce_rbac,
            "rbac_default_role": resolve_role(),
            "graphiti": graphiti_backend_status(),
            "search_backends": sorted(self._search.keys()),
            # Honest adapter posture (registry SSOT narrative; runtime probes above)
            "adapters": self._adapter_status(neo4j_ok=neo4j_ok),
            "events": {
                "card_updated_canonical": "bos://memory/events/card_updated",
                "card_updated_legacy": "bos://brain/events/card_updated",
                "dual_accept": True,
            },
            "control_plane": "bos://memory/mos/*",
        }

    def _adapter_status(self, *, neo4j_ok: bool) -> dict[str, Any]:
        try:
            from mos.adapters.live_backends import live_status_snapshot

            live = live_status_snapshot()
        except Exception as exc:
            live = {"error": str(exc)}
        return {
            "neo4j": {
                "status": "production_path_gated" if neo4j_configured() else "unconfigured",
                "available": neo4j_ok,
                "as_of_supported": True,
            },
            "mem0": {
                "status": "stub_optional" if not mem0_enabled() else "shadow_enabled",
                "enabled": mem0_enabled(),
            },
            "graphiti": graphiti_backend_status(),
            "temporal": {
                "status": "shadow_active" if temporal_enabled() else "shadow_disabled",
                "enabled": temporal_enabled(),
                "as_of_supported": True,
            },
            "kos_gbrain_live": live,
        }

    def register_search_backend(self, name: str, backend: SearchBackend) -> None:
        self._search[name] = backend


class _ThetaAsSearch:
    """Adapt InMemoryThetaBackend to SearchBackend protocol."""

    def __init__(self, theta: InMemoryThetaBackend, name: str = "gbrain") -> None:
        self.name = name
        self._theta = theta

    def search(self, query: str, *, limit: int = 10, scope: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        hits = self._theta.search(query, limit=limit, scope=scope)
        for h in hits:
            h["backend"] = self.name
        return hits


def default_memory_os_with_fixtures() -> MemoryOS:
    """Factory used by CLI smoke and demos with empty corpora."""
    kos = InMemorySearchBackend(
        name="kos",
        docs=[
            {
                "id": "kos-adr-0372",
                "title": "ADR-0372 Memory OS",
                "snippet": "Memory OS control plane unified write recall",
                "path": ".omo/_knowledge/decisions/0372-memory-os-control-plane.md",
            }
        ],
    )
    mos = MemoryOS()
    mos.register_search_backend("kos", kos)
    mos.register_search_backend("cards", InMemorySearchBackend(name="cards", docs=[]))
    mos.register_search_backend("codebase_memory", InMemorySearchBackend(name="codebase_memory", docs=[]))
    mos.register_search_backend("governance_omo", InMemorySearchBackend(name="governance_omo", docs=[]))
    return mos
