"""Neo4j production writer + search for Memory OS temporal facts (Phase 6–7).

Enabled when NEO4J_URI is set (and optionally NEO4J_USER / NEO4J_PASSWORD).
Uses official neo4j driver when installed; otherwise reports unavailable.
Injectable driver factory for unit tests (no live Neo4j required).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC
from typing import Any, Protocol, runtime_checkable


def neo4j_configured() -> bool:
    return bool((os.environ.get("NEO4J_URI") or "").strip())


@runtime_checkable
class Neo4jSessionLike(Protocol):
    def run(self, query: str, parameters: dict[str, Any] | None = None) -> Any: ...


@runtime_checkable
class Neo4jDriverLike(Protocol):
    def session(self) -> Any: ...

    def close(self) -> None: ...


DriverFactory = Callable[[], Neo4jDriverLike | None]


def default_driver_factory() -> Neo4jDriverLike | None:
    uri = (os.environ.get("NEO4J_URI") or "").strip()
    if not uri:
        return None
    try:
        from neo4j import GraphDatabase  # type: ignore[import-not-found]
    except Exception:
        return None
    user = os.environ.get("NEO4J_USER") or os.environ.get("NEO4J_USERNAME") or "neo4j"
    password = os.environ.get("NEO4J_PASSWORD") or ""
    auth = (user, password) if password else None
    try:
        if auth:
            return GraphDatabase.driver(uri, auth=auth)
        return GraphDatabase.driver(uri)
    except Exception:
        return None


UPSERT_CYPHER = """
MERGE (s:Entity {name: $subject})
MERGE (o:Entity {name: $object})
MERGE (s)-[r:FACT {id: $id, predicate: $predicate}]->(o)
SET r.valid_from = $valid_from,
    r.valid_to = $valid_to,
    r.ingested_at = $ingested_at,
    r.invalidated_at = $invalidated_at,
    r.principal_id = $principal_id,
    r.agent_profile = $agent_profile,
    r.scene_id = $scene_id,
    r.text = $text,
    r.content_hash = $content_hash
RETURN r.id AS id
"""

INVALIDATE_CYPHER = """
MATCH ()-[r:FACT {id: $id}]->()
SET r.invalidated_at = $invalidated_at,
    r.valid_to = coalesce(r.valid_to, $invalidated_at)
RETURN r.id AS id
"""

# When $as_of is null/empty → current-state (invalidated_at IS NULL).
# When $as_of is set (ISO-8601) → bi-temporal world+system validity at that instant.
SEARCH_CYPHER = """
MATCH (s:Entity)-[r:FACT]->(o:Entity)
WHERE (
    ($as_of IS NULL OR $as_of = '') AND r.invalidated_at IS NULL
  )
  OR (
    $as_of IS NOT NULL AND $as_of <> ''
    AND (r.valid_from IS NULL OR r.valid_from <= $as_of)
    AND (r.valid_to IS NULL OR r.valid_to > $as_of)
    AND (r.invalidated_at IS NULL OR r.invalidated_at > $as_of)
  )
  AND (
    size($tokens) = 0 OR
    any(tok IN $tokens WHERE
      toLower(coalesce(s.name, '')) CONTAINS tok OR
      toLower(coalesce(o.name, '')) CONTAINS tok OR
      toLower(coalesce(r.predicate, '')) CONTAINS tok OR
      toLower(coalesce(r.text, '')) CONTAINS tok OR
      toLower(coalesce(r.id, '')) CONTAINS tok
    )
  )
RETURN r.id AS id,
       s.name AS subject,
       r.predicate AS predicate,
       o.name AS object,
       r.text AS text,
       r.valid_from AS valid_from,
       r.valid_to AS valid_to,
       r.invalidated_at AS invalidated_at,
       r.principal_id AS principal_id,
       r.agent_profile AS agent_profile,
       r.scene_id AS scene_id,
       r.ingested_at AS ingested_at
ORDER BY coalesce(r.ingested_at, r.valid_from) DESC
LIMIT $limit
"""


@dataclass
class Neo4jFactWriter:
    """Production write path for bi-temporal FACT relationships."""

    driver_factory: DriverFactory = field(default=default_driver_factory)
    _driver: Neo4jDriverLike | None = field(default=None, init=False, repr=False)

    def available(self) -> bool:
        if not neo4j_configured():
            return False
        try:
            d = self._get_driver()
            return d is not None
        except Exception:
            return False

    def _get_driver(self) -> Neo4jDriverLike | None:
        if self._driver is not None:
            return self._driver
        self._driver = self.driver_factory()
        return self._driver

    def upsert_fact(self, envelope: dict[str, Any]) -> dict[str, Any]:
        if not neo4j_configured():
            return {"ok": False, "skipped": True, "reason": "neo4j_uri_unset"}
        driver = self._get_driver()
        if driver is None:
            return {"ok": False, "skipped": True, "reason": "neo4j_driver_unavailable"}
        from datetime import datetime

        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        graph = envelope.get("graph") or {}
        temporal = envelope.get("temporal") or {}
        scope = envelope.get("scope") or {}
        params = {
            "id": envelope.get("id"),
            "subject": graph.get("subject") or envelope.get("subject") or "unknown",
            "predicate": graph.get("predicate") or envelope.get("predicate") or "relates",
            "object": graph.get("object") or envelope.get("object") or "",
            "valid_from": temporal.get("valid_from") or now,
            "valid_to": temporal.get("valid_to"),
            "ingested_at": temporal.get("ingested_at") or now,
            "invalidated_at": temporal.get("invalidated_at"),
            "principal_id": scope.get("principal_id"),
            "agent_profile": scope.get("agent_profile"),
            "scene_id": scope.get("scene_id"),
            "text": envelope.get("content") or "",
            "content_hash": (envelope.get("provenance") or {}).get("content_hash"),
        }
        try:
            with driver.session() as session:  # type: ignore[union-attr]
                result = session.run(UPSERT_CYPHER, params)
                # consume
                if hasattr(result, "single"):
                    result.single()
                elif hasattr(result, "data"):
                    result.data()
            return {"ok": True, "id": params["id"], "store": "neo4j", "uri": os.environ.get("NEO4J_URI")}
        except Exception as exc:
            return {"ok": False, "error": str(exc), "store": "neo4j"}

    def invalidate(self, edge_id: str, invalidated_at: str) -> dict[str, Any]:
        if not neo4j_configured():
            return {"ok": False, "skipped": True}
        driver = self._get_driver()
        if driver is None:
            return {"ok": False, "skipped": True, "reason": "neo4j_driver_unavailable"}
        try:
            with driver.session() as session:  # type: ignore[union-attr]
                session.run(INVALIDATE_CYPHER, {"id": edge_id, "invalidated_at": invalidated_at})
            return {"ok": True, "id": edge_id, "store": "neo4j"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def search_facts(
        self,
        query: str,
        *,
        limit: int = 10,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        """Lexical CONTAINS search over FACT edges.

        as_of=None → current-state (invalidated excluded).
        as_of=ISO timestamp → bi-temporal filter (valid_from/to + invalidated_at).
        """
        if not neo4j_configured():
            return []
        driver = self._get_driver()
        if driver is None:
            return []
        q = (query or "").strip().lower()
        # multi-word: token OR (full phrase alone is too strict for CONTAINS)
        tokens = [t for t in q.split() if t] if q else []
        if q and q not in tokens:
            tokens = [q] + tokens
        as_of_param = (as_of or "").strip() or None
        try:
            with driver.session() as session:  # type: ignore[union-attr]
                result = session.run(
                    SEARCH_CYPHER,
                    {"tokens": tokens, "limit": int(limit), "as_of": as_of_param},
                )
                if hasattr(result, "data"):
                    rows = result.data()
                else:
                    rows = list(result)  # type: ignore[arg-type]
            hits: list[dict[str, Any]] = []
            for row in rows or []:
                rec = dict(row) if not isinstance(row, dict) else row
                sid = rec.get("id")
                subj = rec.get("subject") or ""
                pred = rec.get("predicate") or ""
                obj = rec.get("object") or ""
                hits.append(
                    {
                        "id": sid,
                        "title": f"{subj} {pred} {obj}".strip(),
                        "snippet": rec.get("text") or f"{subj} {pred} {obj}".strip(),
                        "backend": "neo4j",
                        "score": 1.0,
                        "subject": subj,
                        "predicate": pred,
                        "object": obj,
                        "valid_from": rec.get("valid_from"),
                        "valid_to": rec.get("valid_to"),
                        "invalidated_at": rec.get("invalidated_at"),
                        "principal_id": rec.get("principal_id"),
                        "agent_profile": rec.get("agent_profile"),
                        "scene_id": rec.get("scene_id"),
                    }
                )
            return hits[:limit]
        except Exception:
            return []

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:
                pass
            self._driver = None


@dataclass
class Neo4jSearchBackend:
    """SearchBackend adapter over Neo4jFactWriter.search_facts."""

    name: str = "neo4j"
    writer: Neo4jFactWriter | None = None
    # unit-test inject: skip live driver
    fixed_hits: list[dict[str, Any]] | None = None

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        scope: dict[str, Any] | None = None,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        _ = scope
        if self.fixed_hits is not None:
            q = (query or "").lower()
            out = []
            for h in self.fixed_hits:
                blob = " ".join(
                    str(h.get(k) or "") for k in ("title", "snippet", "subject", "predicate", "object", "id")
                ).lower()
                if not q or q in blob or any(tok and tok in blob for tok in q.split()):
                    hit = dict(h)
                    hit.setdefault("backend", self.name)
                    out.append(hit)
            return out[:limit]
        w = self.writer or Neo4jFactWriter()
        hits = w.search_facts(query, limit=limit, as_of=as_of)
        for h in hits:
            h["backend"] = self.name
        return hits


@dataclass
class FakeNeo4jDriver:
    """Test double recording Cypher calls and storing FACT rows for search."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)

    def session(self) -> FakeNeo4jSession:
        return FakeNeo4jSession(self)

    def close(self) -> None:
        return None


@dataclass
class FakeNeo4jSession:
    driver: FakeNeo4jDriver

    def __enter__(self) -> FakeNeo4jSession:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def run(self, query: str, parameters: dict[str, Any] | None = None) -> FakeNeo4jResult:
        params = dict(parameters or {})
        self.driver.calls.append({"query": query, "parameters": params})
        q = query or ""
        if "MERGE" in q and "FACT" in q:
            # upsert: replace same id
            fid = params.get("id")
            self.driver.facts = [f for f in self.driver.facts if f.get("id") != fid]
            self.driver.facts.append(
                {
                    "id": fid,
                    "subject": params.get("subject"),
                    "predicate": params.get("predicate"),
                    "object": params.get("object"),
                    "text": params.get("text"),
                    "valid_from": params.get("valid_from"),
                    "valid_to": params.get("valid_to"),
                    "ingested_at": params.get("ingested_at"),
                    "invalidated_at": params.get("invalidated_at"),
                    "principal_id": params.get("principal_id"),
                    "agent_profile": params.get("agent_profile"),
                    "scene_id": params.get("scene_id"),
                }
            )
            return FakeNeo4jResult([{"id": fid}])
        if "invalidated_at" in q and "MATCH" in q and "SET" in q:
            eid = params.get("id")
            for f in self.driver.facts:
                if f.get("id") == eid:
                    f["invalidated_at"] = params.get("invalidated_at")
                    f["valid_to"] = f.get("valid_to") or params.get("invalidated_at")
            return FakeNeo4jResult([{"id": eid}])
        if "MATCH" in q and "FACT" in q and "RETURN" in q:
            tokens = [str(t).lower() for t in (params.get("tokens") or []) if t]
            if not tokens and params.get("q"):
                tokens = [str(params.get("q")).lower()]
            limit = int(params.get("limit") or 10)
            as_of = (params.get("as_of") or "").strip() or None
            rows = []
            for f in self.driver.facts:
                if not _fake_fact_visible(f, as_of=as_of):
                    continue
                blob = " ".join(str(f.get(k) or "") for k in ("subject", "predicate", "object", "text", "id")).lower()
                if not tokens or any(tok in blob for tok in tokens):
                    rows.append(dict(f))
            return FakeNeo4jResult(rows[:limit])
        return FakeNeo4jResult()


def _fake_fact_visible(f: dict[str, Any], *, as_of: str | None) -> bool:
    """Mirror SEARCH_CYPHER bi-temporal visibility for FakeNeo4jDriver."""
    if not as_of:
        return not f.get("invalidated_at")
    # as_of set: world + system validity
    vf = f.get("valid_from")
    vt = f.get("valid_to")
    inv = f.get("invalidated_at")
    if vf and str(vf) > as_of:
        return False
    if vt and str(vt) <= as_of:
        return False
    if inv and str(inv) <= as_of:
        return False
    return True


class FakeNeo4jResult:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or [{"id": "ok"}]

    def single(self) -> dict[str, Any]:
        return self._rows[0] if self._rows else {}

    def data(self) -> list[dict[str, Any]]:
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)
