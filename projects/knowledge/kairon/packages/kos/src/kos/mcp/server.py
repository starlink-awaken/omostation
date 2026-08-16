#!/usr/bin/env python3
# ruff: noqa
"""
KOS MCP Server v1.4 — Knowledge Operating System via Model Context Protocol

19 tools: search_knowledge, get_knowledge, get_system_status, list_domains,
         cross_domain_sync, get_entity, search_entity, ontology_rebuild,
         ontology_graph, run_indexer, full_sync, research_now, semantic_search,
         build_context, verify_claim, memory_stats, get_stats, subscribe_topic,
         check_subscription, get_entity_timeline
"""

import json
import os
import sqlite3
import subprocess as sp
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from kos.db import get_connection

# ── Path setup ──────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
# Ensure KOS_HOME defaults to workspace root (parent of kos/kos/mcp)
KOS_HOME_DEFAULT = str(SCRIPT_DIR.parent.parent)
os.environ.setdefault("KOS_HOME", KOS_HOME_DEFAULT)

from kos.config import get_vault_ops_dir  # type: ignore[unused-ignore, import-not-found]

VAULT_OPS_DIR = get_vault_ops_dir()
os.chdir(str(SCRIPT_DIR))
# sys.path.insert(0, str(SCRIPT_DIR))  # removed — kos_ontology is now a package member

KOS_READY = False
try:
    from kos.config import get_artifact_path, get_documents_root, get_workspace_manifest  # type: ignore[attr-defined]

    KOS_READY = True
except ImportError:
    pass

from kos.mcp.tools_schema import TOOLS_SCHEMA  # type: ignore[import-not-found]

KOS_INIT_ERROR = {
    "error": "KOS not initialized. Set KOS_HOME env var to the directory containing workspace_config.py, "
    "or run: kos setup"
}

# ── Background task tracker ─────────────────────────
_bg_tasks: dict[str, dict] = {}
_bg_lock = threading.Lock()


def _bg_run(task_id: str, fn: Any) -> None:
    """Run a function in background thread and store result in _bg_tasks."""
    try:
        result = fn()
        with _bg_lock:
            _bg_tasks[task_id] = result
            _bg_tasks[task_id]["_status"] = "completed"
            _bg_tasks[task_id]["_ts"] = datetime.now().isoformat()
    except Exception as e:  # noqa: BLE001
        with _bg_lock:
            _bg_tasks[task_id] = {"_status": "error", "_error": str(e), "_ts": datetime.now().isoformat()}


def _require_ready(result: Any = None) -> dict[str, Any] | None:
    """Decorator-like check: if KOS not ready, return error immediately."""
    if not KOS_READY:
        return KOS_INIT_ERROR
    return None


SERVER_NAME = "kos-mcp-server"
SERVER_VERSION = "1.2.0"

# ── External adapters (version-aware, resilient) ─────────
from kos.adapters import MinervaAdapter, NullMinerva, SemanticScholarAdapter, negotiate_mcp_protocol  # type: ignore[import-not-found]

# ── Domain modules ────────────────────────────────────────
from kos.self.mcp import SELF_HANDLERS, SELF_TOOLS  # type: ignore[import-not-found]
from kos.collab.mcp import COLLAB_HANDLERS, COLLAB_TOOLS  # type: ignore[import-not-found]
from kos.consensus.mcp import CONSENSUS_HANDLERS, CONSENSUS_TOOLS  # type: ignore[import-not-found]

_MINERVA = None
_S2 = None


def _get_minerva():  # type: ignore[no-untyped-def]  # type: ignore[unused-ignore]
    global _MINERVA
    if _MINERVA is None:
        _MINERVA = MinervaAdapter.discover() or NullMinerva
    return _MINERVA


def _get_s2() -> SemanticScholarAdapter:  # type: ignore[unused-ignore]
    global _S2
    if _S2 is None:
        _S2 = SemanticScholarAdapter()
    return _S2


# ── MCP Protocol helpers ─────────────────────────────────
def send_jsonrpc(data: dict) -> None:  # type: ignore[unused-ignore]
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def read_jsonrpc() -> dict[str, Any]:
    line = sys.stdin.readline()
    if not line:
        sys.exit(0)
    return cast("dict[str, Any]", json.loads(line))


# ── Tool implementations ─────────────────────────────────


def tool_list_domains() -> dict[str, Any]:  # type: ignore[unused-ignore]
    if not KOS_READY:
        return KOS_INIT_ERROR
    manifest = get_workspace_manifest()  # type: ignore[reportPossiblyUnboundVariable]
    domains = manifest.get("domains", {})
    zones = manifest.get("zones", {})
    result = []
    if domains:
        for domain_id, domain_info in domains.items():
            zone_id = domain_info.get("zoneId", domain_id)
            zone = zones.get(zone_id, {})
            result.append(
                {
                    "domain": domain_id,
                    "label": zone.get("label", domain_info.get("description", "")),
                    "zone": zone_id,
                    "scope": zone.get("scope", "internal"),
                    "indexable": zone.get("indexable", False),
                    "agent_entry": zone.get("agentEntry", ""),
                }
            )
    else:
        # Fallback: map zones directly as domains
        for zone_id, zone_info in zones.items():
            result.append(
                {
                    "domain": zone_id,
                    "label": zone_info.get("label", zone_id),
                    "zone": zone_id,
                    "scope": zone_info.get("scope", "internal"),
                    "indexable": zone_info.get("indexable", False),
                    "agent_entry": zone_info.get("agentEntry", ""),
                }
            )
    return {"domains": result, "count": len(result)}


def tool_search_knowledge(  # type: ignore[no-untyped-def]
    query: str, domains: str = "", limit: int = 10, match_mode: str = "OR", include_templates: bool = False
) -> dict[str, Any]:
    if not KOS_READY:
        return KOS_INIT_ERROR
    try:
        raw_query = query
        # jieba Chinese tokenization: segment query, join with OR for FTS5
        if match_mode == "OR" and " OR " not in query and " AND " not in query:
            try:
                import jieba  # type: ignore[import-untyped]

                tokens = list(jieba.cut(query))
                if len(tokens) > 1:
                    query = " OR ".join(t for t in tokens if t.strip())
            except ImportError:
                tokens = query.split()
                if len(tokens) > 1:
                    query = " OR ".join(tokens)
        from pathlib import Path

        db_path = get_artifact_path("retrievalDatabase")  # type: ignore[reportPossiblyUnboundVariable]
        if not Path(str(db_path)).exists():
            return {"error": "Retrieval database not found", "results": [], "count": 0}
        conn = get_connection(str(db_path))
        exclude_clause = ""
        if not include_templates:
            manifest = get_workspace_manifest()  # type: ignore[reportPossiblyUnboundVariable]
            excludes = manifest.get("indexing", {}).get("searchDefaultExclude", [])
            if excludes:
                clauses = [f"d.canonical_path NOT LIKE '%{p}%'" for p in excludes]
                exclude_clause = "AND " + " AND ".join(clauses)
        params = [query]
        domain_filter = ""
        if domains:
            domain_list = [d.strip() for d in domains.split(",")]
            placeholders = ",".join(["?" for _ in domain_list])
            domain_filter = f"AND d.zone IN ({placeholders})"
            params.extend(domain_list)
        rows: list[sqlite3.Row] = []
        seen_doc_ids = set()
        like_sql = f"""SELECT d.doc_id,d.title,d.kind,d.zone,d.status,d.canonical_path,d.trust_level,d.updated_at,
                   CASE WHEN d.body IS NOT NULL AND d.body != ''
                        THEN substr(d.body, 1, 300)
                        ELSE ''
                   END AS body_preview,
                   '' AS snippet
            FROM documents d
            WHERE (lower(d.title) LIKE ? OR lower(d.canonical_path) LIKE ?) {domain_filter} {exclude_clause}
            ORDER BY length(d.canonical_path) LIMIT ?"""
        for term in _path_like_terms(raw_query):
            if len(rows) >= limit:
                break
            like_params = [f"%{term}%", f"%{term}%"]
            if domains:
                like_params.extend(domain_list)  # type: ignore[reportPossiblyUnboundVariable]
            like_params.append(limit - len(rows))  # type: ignore[arg-type]
            for row in conn.execute(like_sql, like_params).fetchall():
                if row["doc_id"] not in seen_doc_ids:
                    rows.append(row)
                    seen_doc_ids.add(row["doc_id"])
                    if len(rows) >= limit:
                        break
        params.append(limit)  # type: ignore[arg-type]
        sql = f"""SELECT d.doc_id,d.title,d.kind,d.zone,d.status,d.canonical_path,d.trust_level,d.updated_at,
                   CASE WHEN d.body IS NOT NULL AND d.body != ''
                        THEN substr(d.body, 1, 300)
                        ELSE snippet(documents_fts,1,'**','**','...',80)
                   END AS body_preview,
                   snippet(documents_fts,1,'**','**','...',80) AS snippet
            FROM documents_fts f JOIN documents d ON f.doc_id=d.doc_id
            WHERE documents_fts MATCH ? {domain_filter} {exclude_clause} ORDER BY rank LIMIT ?"""
        try:
            fts_rows = conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            fts_rows = []
        for row in fts_rows:
            if row["doc_id"] not in seen_doc_ids and len(rows) < limit:
                rows.append(row)
                seen_doc_ids.add(row["doc_id"])
        results = [dict(r) for r in rows]
        conn.close()
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "results": [], "count": 0}


def tool_get_knowledge(kos_id: str) -> dict[str, Any]:  # type: ignore[unused-ignore]
    if not KOS_READY:
        return KOS_INIT_ERROR
    try:
        from pathlib import Path

        db_path = get_artifact_path("retrievalDatabase")  # type: ignore[reportPossiblyUnboundVariable]
        if not Path(str(db_path)).exists():
            return {"error": "Retrieval database not found"}
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM documents WHERE doc_id=? OR canonical_path LIKE ?", (kos_id, f"%{kos_id}%")
        ).fetchone()
        if not row:
            conn.close()
            return {"error": f"Not found: {kos_id}"}
        result = dict(row)
        tags = conn.execute("SELECT tag FROM document_tags WHERE doc_id=?", (result["doc_id"],)).fetchall()
        result["tags"] = [t[0] for t in tags]
        conn.close()
        return result
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def tool_get_system_status() -> dict[str, Any]:  # type: ignore[unused-ignore]
    if not KOS_READY:
        return KOS_INIT_ERROR
    domains = tool_list_domains()  # type: ignore[no-untyped-call]
    retrieval_info = {"status": "not available", "path": "", "documents": 0}
    try:
        from pathlib import Path

        db_path = get_artifact_path("retrievalDatabase")  # type: ignore[reportPossiblyUnboundVariable]
        if Path(str(db_path)).exists():
            conn = sqlite3.connect(str(db_path))
            count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            zones = conn.execute("SELECT zone, COUNT(*) as cnt FROM documents GROUP BY zone").fetchall()
            retrieval_info = {
                "status": "active",
                "path": str(db_path),
                "documents": count,
                "by_zone": {z[0]: z[1] for z in zones},
            }
            conn.close()
    except Exception:  # noqa: BLE001
        pass
    # Collect background task status
    bg_tasks = {}
    with _bg_lock:
        for tid, tinfo in _bg_tasks.items():
            bg_tasks[tid] = {
                "status": tinfo.get("_status", "unknown"),
                "error": str(tinfo.get("_error", ""))[:200] if tinfo.get("_error") else None,
                "ts": tinfo.get("_ts", ""),
            }
    return {
        "kos_version": "1.1",
        "timestamp": datetime.now().isoformat(),
        "domains": domains,
        "retrieval": retrieval_info,
        "background_tasks": bg_tasks,
    }


def tool_onto(cmd: str, entity_type: str = "", confirmed: bool = False) -> dict[str, Any]:  # type: ignore[unused-ignore]
    if not KOS_READY:
        return KOS_INIT_ERROR
    """Ontology operations. 'rebuild' runs clear + extract + enrich via subprocess.
    'graph' generates Mermaid graph. 'clear' only clears entities."""
    if cmd in ("rebuild", "clear") and not confirmed:
        return _deny_unconfirmed_l2(f"ontology {cmd}")
    try:
        from pathlib import Path

        db_path = get_artifact_path("retrievalDatabase")  # type: ignore[reportPossiblyUnboundVariable]

        # ── Helper: init ontology schema if needed ──────────
        def _ensure_onto_schema(conn: Any) -> None:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS kos_entities (
                    entity_id   TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    label       TEXT NOT NULL,
                    aliases     TEXT,
                    description TEXT,
                    primary_zone TEXT,
                    source_file TEXT,
                    metadata    TEXT,
                    updated_at  TEXT
                );
                CREATE TABLE IF NOT EXISTS kos_relations (
                    source_id   TEXT,
                    predicate   TEXT,
                    target_id   TEXT,
                    confidence  REAL DEFAULT 1.0,
                    source_doc  TEXT,
                    relation_type TEXT DEFAULT 'explicit',
                    PRIMARY KEY (source_id, predicate, target_id)
                );
                CREATE TABLE IF NOT EXISTS kos_entity_docs (
                    entity_id TEXT,
                    doc_id    TEXT,
                    relevance REAL DEFAULT 1.0,
                    PRIMARY KEY (entity_id, doc_id)
                );
                CREATE TABLE IF NOT EXISTS kos_ontology_meta (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );
            """)
            conn.commit()

        # ── Helper: run ontology module via -m ──────────────
        def _run_onto_subcmd(subcmd: str, timeout: int = 120) -> sp.CompletedProcess:
            return sp.run(
                [sys.executable, "-m", "kos.ontology.engine", subcmd],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

        if cmd == "rebuild":
            # Step 0: ensure ontology schema exists
            conn = sqlite3.connect(str(db_path))
            _ensure_onto_schema(conn)
            conn.execute("DELETE FROM kos_relations")
            conn.execute("DELETE FROM kos_entities")
            conn.execute("DELETE FROM kos_entity_docs")
            conn.commit()
            conn.close()
            # Step 2: Run extract
            r1 = _run_onto_subcmd("extract", 120)
            # Step 3: Run enrich
            r2 = _run_onto_subcmd("enrich", 120)
            extract_ok = r1.returncode == 0
            enrich_ok = r2.returncode == 0
            return {
                "status": "completed" if (extract_ok and enrich_ok) else "partial",
                "extract": {"ok": extract_ok, "output": (r1.stdout[-500:] if r1.stdout else r1.stderr[-200:])},
                "enrich": {"ok": enrich_ok, "output": (r2.stdout[-500:] if r2.stdout else r2.stderr[-200:])},
            }
        elif cmd == "clear":
            conn = sqlite3.connect(str(db_path))
            _ensure_onto_schema(conn)
            conn.execute("DELETE FROM kos_relations")
            conn.execute("DELETE FROM kos_entities")
            conn.execute("DELETE FROM kos_entity_docs")
            conn.commit()
            conn.close()
            return {"status": "cleared", "message": "Entities cleared. Run rebuild to repopulate."}
        elif cmd == "graph":
            args = [sys.executable, "-m", "kos.ontology.engine", "graph"]
            if entity_type:
                args.extend(["--type", entity_type])
            r = sp.run(args, capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                return {"graph": r.stdout.strip()}
            return {"error": r.stderr or "Graph generation failed"}
        else:
            return {"error": f"Unknown onto command: {cmd}"}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _deny_unconfirmed_l2(action: str) -> dict[str, Any]:
    return {
        "status": "denied",
        "error": f"L2 operation requires explicit confirmation before {action}",
        "operation_level": "L2",
        "required_confirmation": True,
    }


def _indexer_env() -> dict[str, str]:
    env = os.environ.copy()
    src_dir = str(SCRIPT_DIR.parent.parent)
    existing = env.get("PYTHONPATH", "")
    paths = [src_dir]
    if existing:
        paths.extend(existing.split(os.pathsep))
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(paths))
    return env


def _path_like_terms(query: str) -> list[str]:
    raw = query.strip().strip('"').strip("'")
    candidates = [
        raw,
        raw.replace(" ", "_"),
        raw.replace(" ", "-"),
    ]
    for separator in (" ", "/", "-", "_", "."):
        candidates.extend(part for part in raw.split(separator) if part)
    return list(dict.fromkeys(term.lower() for term in candidates if len(term.strip()) >= 2))


def tool_run_indexer(
    incremental: bool = True,
    domain: str = "",
    background: bool = True,
    confirmed: bool = False,
) -> dict[str, Any]:
    if not KOS_READY:
        return KOS_INIT_ERROR
    """Run kos-indexer.py as a subprocess (host-side, bypasses sandbox SQLite restriction).
    Default: incremental mode. Set incremental=False for full rebuild.
    Default: background=True returns immediately with task_id."""
    if not incremental and not confirmed:
        return _deny_unconfirmed_l2("full KOS reindex")
    # ── Background mode ──────────────────────────────────
    if background:
        task_id = f"idx_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        with _bg_lock:
            _bg_tasks[task_id] = {"_status": "running", "_ts": datetime.now().isoformat()}
        t = threading.Thread(
            target=_bg_run,
            args=(
                task_id,
                lambda: tool_run_indexer(
                    incremental=incremental,
                    domain=domain,
                    background=False,
                    confirmed=confirmed,
                ),
            ),
            daemon=True,
        )
        t.start()
        return {
            "status": "started",
            "task_id": task_id,
            "mode": "incremental" if incremental else "full",
            "domain": domain or "all",
            "operation_level": "L1" if incremental else "L2",
            "message": "Indexer started in background. Check get_system_status or use task_id to track progress.",
        }

    # ── Synchronous mode ────────────────────────────────
    try:
        indexer_path = SCRIPT_DIR.parent.parent / "kos-indexer.py"
        if not indexer_path.exists():
            args = [sys.executable, "-c", "from kos.indexer import main; main()", "index"]
        else:
            args = [sys.executable, str(indexer_path), "index"]
        if incremental:
            args.append("--incremental")
        if domain:
            args.extend(["--domain", domain])
        r = sp.run(args, capture_output=True, text=True, timeout=300, cwd=str(SCRIPT_DIR), env=_indexer_env())
        return {
            "status": "completed" if r.returncode == 0 else "failed",
            "returncode": r.returncode,
            "output": r.stdout[-2000:] if r.stdout else "",
            "errors": r.stderr[-1000:] if r.stderr else "",
            "mode": "incremental" if incremental else "full",
            "domain": domain or "all",
            "operation_level": "L1" if incremental else "L2",
        }
    except sp.TimeoutExpired:
        return {"status": "timeout", "error": "Indexer timed out after 300s"}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": str(e)}


def tool_full_sync(background: bool = True, confirmed: bool = False) -> dict[str, Any]:
    """Run indexer + ontology rebuild end-to-end. One-command full KOS refresh.
    Default: background=True returns immediately with task_id."""
    if not confirmed:
        return _deny_unconfirmed_l2("full KOS sync (indexer + ontology rebuild)")
    # ── Background mode ──────────────────────────────────
    if background:
        task_id = f"sync_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        with _bg_lock:
            _bg_tasks[task_id] = {"_status": "running", "_ts": datetime.now().isoformat()}
        t = threading.Thread(
            target=_bg_run,
            args=(task_id, lambda: tool_full_sync(background=False)),
            daemon=True,
        )
        t.start()
        return {
            "status": "started",
            "task_id": task_id,
            "message": "Full sync started in background. Check get_system_status to track progress.",
        }

    # ── Synchronous mode ────────────────────────────────
    result: dict[str, Any] = {"indexer": None, "ontology": None}
    idx = tool_run_indexer(incremental=True, background=False)
    result["indexer"] = idx
    if idx.get("status") != "completed":
        result["status"] = "indexer_failed"
        return result
    onto = tool_onto("rebuild", confirmed=True)
    result["ontology"] = onto
    result["status"] = "completed" if onto.get("status") == "completed" else "ontology_partial"
    return result


def _deny_unconfirmed_l3(action: str, cool_down_hours: int = 0) -> dict[str, Any]:
    return {
        "status": "denied",
        "error": f"L3 operation requires _confirmed=true AND _cool_down_hours>=24 before {action}",
        "operation_level": "L3",
        "required_confirmation": True,
        "required_cooldown_hours": 24,
        "actual_cooldown_hours": cool_down_hours,
    }


def tool_db_vacuum(
    confirmed: bool = False,
    cool_down_hours: int = 0,
) -> dict[str, Any]:
    """VACUUM the retrieval database. Irreversible space reclamation — L3 operation."""
    if not confirmed or cool_down_hours < 24:
        return _deny_unconfirmed_l3("db_vacuum", cool_down_hours)
    if not KOS_READY:
        return KOS_INIT_ERROR
    try:
        from pathlib import Path

        db_path = get_artifact_path("retrievalDatabase")  # type: ignore[reportPossiblyUnboundVariable]
        if not Path(str(db_path)).exists():
            return {"error": "Retrieval database not found"}
        conn = sqlite3.connect(str(db_path))
        conn.execute("VACUUM")
        conn.close()
        return {"status": "completed", "operation": "vacuum", "operation_level": "L3"}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def tool_get_entity(entity_id: str) -> dict[str, Any]:  # type: ignore[unused-ignore]
    try:
        r = sp.run(
            [sys.executable, "-m", "kos.ontology.engine", "card", entity_id], capture_output=True, text=True, timeout=10
        )
        return json.loads(r.stdout) if r.stdout else {"error": "Entity not found"}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def tool_search_entity(query: str, entity_type: str = "", limit: int = 10) -> dict[str, Any]:  # type: ignore[unused-ignore]
    try:
        from pathlib import Path

        db_path = get_artifact_path("retrievalDatabase")  # type: ignore[reportPossiblyUnboundVariable]
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        params = [f"%{query}%", limit]
        type_filter = ""
        if entity_type:
            type_filter = "AND entity_type = ?"
            params.insert(1, entity_type.capitalize())
        rows = conn.execute(
            f"SELECT entity_id,entity_type,label,description,primary_zone FROM kos_entities WHERE label LIKE ? {type_filter} LIMIT ?",
            params,
        ).fetchall()
        conn.close()
        return {"results": [dict(r) for r in rows], "count": len(rows)}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e), "results": []}


def tool_research_now(query: str, level: str = "auto", max_cost: float = 1.0) -> dict:  # type: ignore[type-arg]
    """Execute deep research via Minerva. Returns structured report."""
    adapter = _get_minerva()  # type: ignore[no-untyped-call]
    if not adapter.health()["available"]:
        return {"error": "Minerva not available. Install: pip install minerva", "status": "unavailable"}
    return cast("dict", adapter.research(query, level=level, max_cost=max_cost, timeout=600, cwd=str(SCRIPT_DIR)))


def tool_semantic_search(query: str, limit: int = 10) -> dict:  # type: ignore[type-arg]
    """Search via KOS LanceDB vector similarity, fallback to KOS FTS5."""
    try:
        semantic_script = SCRIPT_DIR / "kos-semantic.py"
        if semantic_script.exists():
            r = sp.run(
                [sys.executable, str(semantic_script), "search", query, "--limit", str(limit)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                if data.get("results"):
                    return cast("dict", data)
    except Exception:  # noqa: BLE001
        pass
    # Fallback to KOS FTS5
    return tool_search_knowledge(query, limit=limit)  # type: ignore[Any, Any]


def tool_semantic_scholar(query: str, limit: int = 5) -> dict[str, Any]:  # type: ignore[unused-ignore]
    if not KOS_READY:
        return KOS_INIT_ERROR
    return _get_s2().search(query, limit=limit)  # type: ignore[no-untyped-call]


# ── Context Engine MCP Tools ─────────────────────────────


def tool_build_context(query: str, mode: str = "balanced", persona: str = "", max_tokens: int = 0) -> dict:
    """Build LLM-ready context from knowledge base with budget control."""
    try:
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        ctx = engine.build_context(
            query,
            mode=mode if mode in ContextEngine.MODES else "balanced",
            persona=persona or None,
            max_tokens=max_tokens if max_tokens > 0 else None,
        )
        engine.close()

        # Add formatted prompt
        ctx["prompt"] = engine._format_prompt(ctx)
        return ctx
    except Exception as e:
        return {"error": str(e)}


def tool_verify_claim(claim: str) -> dict:
    """Verify a claim against the knowledge base. Returns supporting/contradicting evidence."""
    try:
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        result = engine.search(claim, mode="hybrid", limit=10)
        engine.close()

        evidence = []
        for r in result.get("results", []):
            snippet = r.get("snippet", "")
            evidence.append(
                {
                    "title": r.get("title", ""),
                    "snippet": snippet[:300] if snippet else "",
                    "source": r.get("source", ""),
                    "canonical_path": r.get("canonical_path", ""),
                }
            )

        return {
            "claim": claim,
            "evidence_count": len(evidence),
            "evidence": evidence,
            "verdict": "supported" if len(evidence) >= 3 else ("partial" if len(evidence) >= 1 else "no_evidence"),
        }
    except Exception as e:
        return {"error": str(e)}


def tool_research_pipeline(question: str, level: str = "auto", max_cost: float = 1.0) -> dict:
    """Full research pipeline: KOS search → context → Minerva research → fact check."""
    try:
        from kos.minerva.bridge import cmd_research

        return cmd_research(question, level, max_cost)
    except Exception as e:
        return {"error": str(e)}


def tool_graph_search(query: str, max_hops: int = 3, limit: int = 10) -> dict:
    """Multi-hop graph search with reasoning paths."""
    try:
        from kos.graphrag_engine.reasoner import GraphRAGReasoner

        reasoner = GraphRAGReasoner()
        result = reasoner.reason(query, max_hops=max_hops, max_evidence=limit)
        reasoner.close()
        return result
    except Exception as e:
        return {"error": str(e)}


def tool_entity_explore(entity_id: str, depth: int = 2) -> dict:
    """Explore an entity: relations, documents, and connected entities."""
    try:
        conn = get_connection()
        entity = conn.execute("SELECT * FROM kos_entities WHERE entity_id = ?", (entity_id,)).fetchone()
        if not entity:
            return {"error": f"Entity not found: {entity_id}"}

        # Outgoing relations
        outgoing = conn.execute(
            "SELECT predicate, target_id, confidence FROM kos_relations WHERE source_id = ?", (entity_id,)
        ).fetchall()

        # Incoming relations
        incoming = conn.execute(
            "SELECT source_id, predicate, confidence FROM kos_relations WHERE target_id = ?", (entity_id,)
        ).fetchall()

        # Documents
        docs = conn.execute(
            """SELECT d.title, d.canonical_path, ed.relevance
               FROM kos_entity_docs ed JOIN documents d ON ed.doc_id = d.doc_id
               WHERE ed.entity_id = ? ORDER BY ed.relevance DESC LIMIT 10""",
            (entity_id,),
        ).fetchall()

        # Connected entities (neighbors)
        connected = set()
        for r in outgoing:
            connected.add(r["target_id"])
        for r in incoming:
            connected.add(r["source_id"])
        connected.discard(entity_id)

        conn.close()

        return {
            "entity": {
                "id": entity["entity_id"],
                "type": entity["entity_type"],
                "label": entity["label"],
                "description": entity["description"],
            },
            "outgoing_relations": [
                {"predicate": r["predicate"], "target": r["target_id"], "confidence": r["confidence"]} for r in outgoing
            ],
            "incoming_relations": [
                {"source": r["source_id"], "predicate": r["predicate"], "confidence": r["confidence"]} for r in incoming
            ],
            "documents": [dict(d) for d in docs],
            "connected_entities": list(connected)[:20],
        }
    except Exception as e:
        return {"error": str(e)}


def tool_knowledge_ask(question: str, include_paths: bool = True) -> dict:
    """Ask a question using GraphRAG reasoning."""
    try:
        from kos.graphrag_engine.reasoner import GraphRAGReasoner

        reasoner = GraphRAGReasoner()
        result = reasoner.reason(question, max_hops=3, max_evidence=5)
        reasoner.close()

        if not include_paths:
            result.pop("reasoning_paths", None)
            result.pop("prompt", None)

        return result
    except Exception as e:
        return {"error": str(e)}


def tool_fact_check(claim: str) -> dict:
    """Verify a factual claim against KOS knowledge base."""
    try:
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        result = engine.search(claim, mode="hybrid", limit=10)
        engine.close()

        evidence = []
        for r in result.get("results", []):
            evidence.append(
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", "")[:300],
                    "source": r.get("source", ""),
                }
            )

        return {
            "claim": claim,
            "evidence_count": len(evidence),
            "evidence": evidence,
            "verdict": "supported" if len(evidence) >= 3 else ("partial" if len(evidence) >= 1 else "no_evidence"),
        }
    except Exception as e:
        return {"error": str(e)}


def tool_sync_gbrain(direction: str = "both", limit: int = 100) -> dict:
    """Sync KOS documents with gbrain memory graph."""
    try:
        from kos.gbrain_bridge import GbrainBridge

        bridge = GbrainBridge()
        result = {}

        if direction in ("export", "both"):
            result["export"] = bridge.export_to_gbrain(limit=limit)
        if direction in ("import", "both"):
            result["import"] = bridge.import_from_gbrain(limit=limit)

        bridge.close()
        return result
    except Exception as e:
        return {"error": str(e)}


def tool_memory_stats() -> dict:
    """Get memory tier statistics (session/history/ontology)."""
    try:
        from kos.memory_tier import MemoryTier

        memory = MemoryTier()
        stats = memory.get_stats()
        memory.clear_session()
        return stats
    except Exception as e:
        return {"error": str(e)}


def tool_get_stats() -> dict:
    """Get quick knowledge base statistics."""
    try:
        conn = get_connection()
        stats = {
            "documents": conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            "entities": conn.execute("SELECT COUNT(*) FROM kos_entities").fetchone()[0],
            "relations": conn.execute("SELECT COUNT(*) FROM kos_relations").fetchone()[0],
            "domains": conn.execute("SELECT COUNT(DISTINCT zone) FROM documents").fetchone()[0],
        }
        conn.close()
        return stats
    except Exception as e:
        return {"error": str(e)}


def tool_subscribe_topic(topic: str, subscriber_id: str = "mcp-agent") -> dict:
    """Subscribe to a topic for new document notifications."""
    try:
        from kos.agent.subscription import SubscriptionService

        service = SubscriptionService()
        service.init_table(get_artifact_path("retrievalDatabase"))  # type: ignore[reportPossiblyUnboundVariable]
        return service.subscribe(topic, subscriber_id)
    except Exception as e:
        return {"error": str(e)}


def tool_check_subscription(sub_id: str) -> dict:
    """Check a subscription for new matches."""
    try:
        from kos.agent.subscription import SubscriptionService

        service = SubscriptionService()
        return service.check_matches(sub_id)
    except Exception as e:
        return {"error": str(e)}


def tool_get_entity_timeline(entity_id: str) -> dict:
    """Get entity timeline (related documents sorted by date)."""
    try:
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT d.title, d.zone, d.canonical_path, d.created_at, d.updated_at, ed.relevance
            FROM kos_entity_docs ed
            JOIN documents d ON ed.doc_id = d.doc_id
            WHERE ed.entity_id = ?
            ORDER BY d.updated_at DESC LIMIT 20
        """,
            (entity_id,),
        ).fetchall()
        conn.close()

        return {
            "entity_id": entity_id,
            "total_docs": len(rows),
            "timeline": [
                {
                    "title": r["title"],
                    "zone": r["zone"],
                    "canonical_path": r["canonical_path"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                    "relevance": r["relevance"],
                }
                for r in rows
            ],
        }
    except Exception as e:
        return {"error": str(e)}


def tool_mcp_market_discover(source: str | None = None) -> dict:
    """G3: 发现 MCP 外部工具市场 (本地 configs + agora backends + registries)."""
    try:
        from forge.discover_mcp import discover_all, probe_agora_backends, probe_local_mcp_configs
    except ImportError:
        return {"error": "forge package not available", "status": "unavailable"}
    if source == "local":
        found = probe_local_mcp_configs()
        return {"local_configs": found, "count": len(found)}
    if source == "agora":
        found = probe_agora_backends()
        return {"agora_backends": found, "count": len(found)}
    return discover_all()


def tool_viz_render(viz_type: str = "ontology", entity_type: str | None = None) -> dict:
    """G4: 渲染统一 Mermaid 可视化 (ontology/class/state/pipeline/memory)."""
    try:
        from kos.viz_unified import list_viz_types, render_all, render_unified
    except ImportError:
        return {"error": "viz_unified not available", "status": "unavailable"}
    if viz_type == "all":
        return {"viz_types": list_viz_types(), "graphs": render_all(entity_type)}
    mermaid = render_unified(viz_type, entity_type=entity_type)
    return {"viz_type": viz_type, "mermaid": mermaid}


# ── MCP Server main loop ─────────────────────────────────


def run_stdio() -> None:  # type: ignore[unused-ignore]
    init_msg = read_jsonrpc()
    if init_msg.get("method") != "initialize":
        send_jsonrpc(
            {"jsonrpc": "2.0", "id": init_msg.get("id"), "error": {"code": -32600, "message": "Expected initialize"}}
        )
        return

    client_params = init_msg.get("params", {})
    client_version = client_params.get("protocolVersion")
    negotiated = negotiate_mcp_protocol(client_version)

    send_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": init_msg["id"],
            "result": {
                "protocolVersion": negotiated,
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "capabilities": {"tools": {}},
            },
        }
    )
    read_jsonrpc()  # initialized notification

    TOOLS = dict(TOOLS_SCHEMA)  # 从 tools_schema.py import (wave 6, 替代内联 312 行)
    TOOLS.update(SELF_TOOLS)
    TOOLS.update(COLLAB_TOOLS)
    TOOLS.update(CONSENSUS_TOOLS)

    while True:
        msg = read_jsonrpc()
        if msg.get("method") == "tools/list":
            tool_list = [
                {"name": n, "description": i["description"], "inputSchema": i["inputSchema"]} for n, i in TOOLS.items()
            ]
            send_jsonrpc({"jsonrpc": "2.0", "id": msg["id"], "result": {"tools": tool_list}})
        elif msg.get("method") == "tools/call":
            p = msg.get("params", {})
            tn = p.get("name", "")
            a = p.get("arguments", {})
            handlers = {
                "search_knowledge": lambda: tool_search_knowledge(
                    a.get("query", ""), a.get("domains", ""), a.get("limit", 10), a.get("match_mode", "OR")
                ),
                "get_knowledge": lambda: tool_get_knowledge(a.get("kos_id", "")),
                "get_system_status": tool_get_system_status,
                "list_domains": tool_list_domains,
                "cross_domain_sync": lambda: tool_run_indexer(incremental=True, background=True),
                "get_entity": lambda: tool_get_entity(a.get("entity_id", "")),
                "search_entity": lambda: tool_search_entity(
                    a.get("query", ""), a.get("entity_type", ""), a.get("limit", 10)
                ),
                "ontology_rebuild": lambda: tool_onto("rebuild", confirmed=a.get("confirmed", False)),
                "ontology_graph": lambda: tool_onto("graph", a.get("entity_type", "")),
                "run_indexer": lambda: tool_run_indexer(
                    a.get("incremental", True),
                    a.get("domain", ""),
                    a.get("background", True),
                    a.get("confirmed", False),
                ),
                "full_sync": lambda: tool_full_sync(a.get("background", True), a.get("confirmed", False)),
                "db_vacuum": lambda: tool_db_vacuum(
                    a.get("confirmed", False),
                    a.get("cool_down_hours", 0),
                ),
                "research_now": lambda: tool_research_now(
                    a.get("query", ""), a.get("level", "auto"), a.get("max_cost", 1.0)
                ),
                "semantic_search": lambda: tool_semantic_search(a.get("query", ""), a.get("limit", 10)),
                "semantic_scholar": lambda: tool_semantic_scholar(a.get("query", ""), a.get("limit", 5)),
                "build_context": lambda: tool_build_context(
                    a.get("query", ""), a.get("mode", "balanced"), a.get("persona", ""), a.get("max_tokens", 0)
                ),
                "verify_claim": lambda: tool_verify_claim(a.get("claim", "")),
                "memory_stats": tool_memory_stats,
                "get_stats": tool_get_stats,
                "subscribe_topic": lambda: tool_subscribe_topic(
                    a.get("topic", ""), a.get("subscriber_id", "mcp-agent")
                ),
                "check_subscription": lambda: tool_check_subscription(a.get("sub_id", "")),
                "get_entity_timeline": lambda: tool_get_entity_timeline(a.get("entity_id", "")),
                "self.get_profile": lambda: SELF_HANDLERS["self.get_profile"](),
                "self.get_current_role": lambda: SELF_HANDLERS["self.get_current_role"](a),
                "self.get_vision_summary": lambda: SELF_HANDLERS["self.get_vision_summary"](),
                "collab.create_task": lambda: COLLAB_HANDLERS["collab.create_task"](a),
                "collab.get_task": lambda: COLLAB_HANDLERS["collab.get_task"](a),
                "collab.list_tasks": lambda: COLLAB_HANDLERS["collab.list_tasks"](a),
                "collab.update_task": lambda: COLLAB_HANDLERS["collab.update_task"](a),
                "collab.claim_subtask": lambda: COLLAB_HANDLERS["collab.claim_subtask"](a),
                "collab.add_artifact": lambda: COLLAB_HANDLERS["collab.add_artifact"](a),
                "consensus.create": lambda: CONSENSUS_HANDLERS["consensus.create"](a),
                "consensus.get": lambda: CONSENSUS_HANDLERS["consensus.get"](a),
                "consensus.list_expired": lambda: CONSENSUS_HANDLERS["consensus.list_expired"](a),
                "consensus.renew": lambda: CONSENSUS_HANDLERS["consensus.renew"](a),
                "research_pipeline": lambda: tool_research_pipeline(
                    a.get("question", ""), a.get("level", "auto"), a.get("max_cost", 1.0)
                ),
                "fact_check": lambda: tool_fact_check(a.get("claim", "")),
                "sync_gbrain": lambda: tool_sync_gbrain(a.get("direction", "both"), a.get("limit", 100)),
                "graph_search": lambda: tool_graph_search(a.get("query", ""), a.get("max_hops", 3), a.get("limit", 10)),
                "entity_explore": lambda: tool_entity_explore(a.get("entity_id", ""), a.get("depth", 2)),
                "knowledge_ask": lambda: tool_knowledge_ask(a.get("question", ""), a.get("include_paths", True)),
                "mcp_market_discover": lambda: tool_mcp_market_discover(a.get("source")),
                "viz_render": lambda: tool_viz_render(a.get("viz_type", "ontology"), a.get("entity_type")),
            }
            h = handlers.get(tn)
            if h:
                try:
                    r = h()  # type: ignore[no-untyped-call]
                    send_jsonrpc(
                        {
                            "jsonrpc": "2.0",
                            "id": msg["id"],
                            "result": {
                                "content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False, indent=2)}]
                            },
                        }
                    )
                except Exception as e:  # noqa: BLE001
                    send_jsonrpc(
                        {
                            "jsonrpc": "2.0",
                            "id": msg["id"],
                            "result": {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]},
                        }
                    )
            else:
                send_jsonrpc(
                    {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -32601, "message": f"Unknown tool: {tn}"}}
                )
        elif msg.get("method") == "notifications/cancelled":
            pass
        else:
            send_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": msg.get("id"),
                    "error": {"code": -32601, "message": f"Unknown: {msg.get('method')}"},
                }
            )


def main() -> None:
    """Entry point for kos MCP server (FastMCP stdio).

    协议统一 (2026-07-13): 走 fastmcp_app._create_fastmcp_app().run() (42 工具 @app.tool).
    run_stdio (手写 stdio) 保留为独立函数 (兼容/测试引用), main 不再调它.
    延迟 import fastmcp_app 解循环 (fastmcp_app 顶层 import server tool_ 函数).
    """
    from kos.mcp.fastmcp_app import _create_fastmcp_app

    app = _create_fastmcp_app()
    if app is None:
        print("FastMCP required. Install: uv sync --extra mcp (or pip install fastmcp)", file=sys.stderr)
        sys.exit(1)
    app.run()


if __name__ == "__main__":
    main()
