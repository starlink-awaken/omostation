#!/usr/bin/env python3
# fastapi is optional; Query/Request degrade to None.
# pyright: reportOptionalCall=false
# ruff: noqa
import logging

logger = logging.getLogger(__name__)
"""
KOS Web UI — FastAPI knowledge dashboard.

Start: kos web → http://localhost:8766
"""

import re
import sqlite3
import sys
from pathlib import Path
from typing import Iterator, Any

SCRIPT_DIR = Path(__file__).resolve().parent
try:
    from kos.config import get_artifact_path, get_vault_ops_dir, get_workspace_manifest  # type: ignore[import-not-found]
except ImportError:
    from config import get_artifact_path, get_vault_ops_dir, get_workspace_manifest  # type: ignore[import-not-found, no-redef]

VAULT_OPS_DIR = get_vault_ops_dir()

try:
    import uvicorn
except ImportError:
    uvicorn = None  # type: ignore[assignment]

try:
    from fastapi import FastAPI, Query, Request
    from fastapi.responses import HTMLResponse, JSONResponse

    HAS_FASTAPI = True
except ImportError:
    FastAPI = None  # type: ignore[assignment,misc]
    Query = None  # type: ignore[assignment,misc]
    Request = None  # type: ignore[assignment,misc]
    from fastapi.responses import HTMLResponse, JSONResponse  # type: ignore[import-not-found]

    HAS_FASTAPI = False

app = FastAPI(title="KOS Dashboard", version="2.0")

# ── REST API v1 (for cross-project integration) ────────


@app.get("/api/v1/search")
async def api_search(q: str = Query(...), mode: str = "hybrid", limit: int = 10):
    """Search knowledge base. Used by cockpit proxy and other integrations."""
    try:
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        result = engine.search(q, mode=mode, limit=limit)
        engine.close()
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/v1/suggest")
async def api_suggest(prefix: str = Query(...), limit: int = 8):
    """Get search suggestions."""
    try:
        from kos.search_features import SearchFeatures

        features = SearchFeatures()
        result = features.suggest(prefix, limit=limit)
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/v1/context")
async def api_context(q: str = Query(...), mode: str = "balanced"):
    """Build LLM-ready context."""
    try:
        from kos.context_engine import ContextEngine

        engine = ContextEngine()
        result = engine.build_context(q, mode=mode)
        engine.close()
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/api/v1/verify")
async def api_verify(data: dict):
    """Verify a claim against knowledge base."""
    claim = data.get("claim", "")
    try:
        from kos.hybrid_search import HybridSearchEngine

        engine = HybridSearchEngine()
        result = engine.search(claim, mode="hybrid", limit=10)
        engine.close()
        return JSONResponse(
            content={
                "claim": claim,
                "evidence_count": result.get("count", 0),
                "results": result.get("results", []),
            }
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/v1/stats")
async def api_stats():
    """Get knowledge base statistics."""
    conn = None
    try:
        conn = sqlite3.connect(str(get_artifact_path("retrievalDatabase")))
        conn.row_factory = sqlite3.Row
        stats = {
            "documents": conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
            "entities": conn.execute("SELECT COUNT(*) FROM kos_entities").fetchone()[0],
            "relations": conn.execute("SELECT COUNT(*) FROM kos_relations").fetchone()[0],
        }
        return JSONResponse(content=stats)
    except sqlite3.OperationalError as e:
        return JSONResponse(
            content={
                "status": "unavailable",
                "data_quality": "unavailable",
                "error": str(e),
                "next_action": "初始化 KOS retrievalDatabase 后再刷新统计。",
            },
            status_code=503,
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    finally:
        if conn is not None:
            conn.close()


@app.get("/api/v1/health")
async def api_health():
    """Check knowledge base health."""
    try:
        from kos.monitoring import KosMonitor

        monitor = KosMonitor()
        result = monitor.index_health()
        return JSONResponse(content=result)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/api/v1/clusters")
async def api_clusters(q: str = Query(...), limit: int = 10):
    """Search and cluster results by topic."""
    try:
        from kos.hybrid_search import HybridSearchEngine
        from kos.search_features import SearchFeatures

        engine = HybridSearchEngine()
        result = engine.search(q, mode="hybrid", limit=limit)
        engine.close()
        features = SearchFeatures()
        clusters = features.cluster_by_topic(result.get("results", []))
        return JSONResponse(content=clusters)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font:14px/1.6 -apple-system,sans-serif;background:#0d1117;color:#c9d1d9;max-width:1200px;margin:0 auto;padding:20px}
h1{color:#58a6ff;font-size:20px;margin-bottom:16px}
h2{color:#58a6ff;font-size:16px;margin:16px 0 8px}
a{color:#58a6ff;text-decoration:none}
input,select,button{padding:8px 12px;border:1px solid #30363d;border-radius:6px;background:#21262d;color:#c9d1d9;font-size:14px}
input:focus,select:focus{outline:none;border-color:#58a6ff}
button{background:#238636;border-color:#238636;cursor:pointer;font-weight:600}
button:hover{background:#2ea043}
.result{border:1px solid #21262d;border-radius:8px;padding:12px;margin:8px 0;background:#161b22}
.result h3{font-size:15px;margin-bottom:4px}
.result .zone{font-size:11px;color:#8b949e;margin-bottom:4px}
.result .path{font-size:11px;color:#484f58;margin-bottom:6px;word-break:break-all}
.result .snippet{font-size:13px;color:#8b949e;line-height:1.5}
.nav{display:flex;gap:16px;margin-bottom:24px;border-bottom:1px solid #21262d;padding-bottom:12px}
.nav a{padding:4px 8px;border-radius:4px}
.nav a.active{background:#1f6feb}
.row{display:flex;gap:16px;margin-bottom:12px}
.row>*{flex:1}
.card{border:1px solid #21262d;border-radius:8px;padding:16px;background:#161b22;margin-bottom:12px}
.card h3{color:#58a6ff;font-size:14px;margin-bottom:8px}
.stat{font-size:28px;font-weight:700;color:#e6edf3}
.stat-label{font-size:12px;color:#8b949e}
.bar{height:8px;background:#21262d;border-radius:4px;margin:4px 0;overflow:hidden}
.bar-fill{height:100%;background:#238636;border-radius:4px}
.zone-row{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #21262d}
.zone-name{width:120px;font-weight:600}
.zone-count{width:60px;text-align:right;color:#8b949e}
.zone-bar{flex:1}
.rel-tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;margin:2px;
  background:#1f6feb;color:#fff}
.rel-tag.out{background:#238636}
.rel-tag.in{background:#8957e5}
.status-ok{color:#3fb950}.status-warn{color:#d29922}.status-err{color:#f85149}
.code{font-family:monospace;font-size:12px;background:#0d1117;padding:8px;border-radius:4px;margin:8px 0;max-height:300px;overflow:auto;white-space:pre-wrap}
.type-section{margin-bottom:12px}
.type-header{cursor:pointer;display:flex;align-items:center;gap:8px;padding:8px 12px;background:#21262d;border-radius:6px;font-weight:600;font-size:14px;user-select:none}
.type-header:hover{background:#30363d}
.type-count{color:#8b949e;font-size:12px;margin-left:auto}
.entity-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:6px;padding:8px 0}
.entity-card{border:1px solid #21262d;border-radius:8px;padding:10px 12px;background:#161b22;display:flex;flex-direction:column;gap:6px;transition:border-color .15s}
.entity-card:hover{border-color:#58a6ff}
.entity-card .ename{font-weight:600;color:#e6edf3;font-size:15px;line-height:1.3}
.entity-card .emeta{font-size:11px;color:#484f58;display:flex;gap:6px}
.entity-card .edesc{font-size:11px;color:#8b949e;line-height:1.4;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.entity-card .erels{margin-top:auto;display:flex;gap:4px;flex-wrap:wrap;align-items:center}
.erel-tag{font-size:11px;padding:2px 8px;border-radius:10px;background:#21262d;color:#8b949e;font-weight:500}
.erel-tag.out{background:#1a3a2a;color:#3fb950}
.erel-tag.in{background:#2a1a3a;color:#bc8cff}
.erel-tag.warn{background:#3a2a1a;color:#d29922}
.rel-link{display:inline-flex;align-items:center;gap:4px;padding:4px 10px;border:1px solid #30363d;border-radius:16px;font-size:12px;color:#c9d1d9;text-decoration:none;background:#161b22}
.rel-link:hover{border-color:#58a6ff;background:#1a2332}
.rel-key{font-size:10px;padding:1px 6px;border-radius:8px;background:#1f6feb;color:#fff;font-weight:600}
.erel-tag strong{font-weight:700}
details summary{list-style:none;cursor:pointer}
details summary::-webkit-details-marker{display:none}
"""


def get_db() -> sqlite3.Connection:  # type: ignore[no-untyped-def]
    db_path = get_artifact_path("retrievalDatabase")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_health_status() -> dict[str, object]:
    manifest = get_workspace_manifest() or {}
    db_path = Path(get_artifact_path("retrievalDatabase"))
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("SELECT 1")

    return {
        "status": "ok",
        "workspace": {
            "name": manifest.get("name", "kos-default"),
            "zones": len((manifest.get("zones") or {})),
        },
        "database": {
            "path": str(db_path),
            "reachable": True,
        },
    }


def render(template: str, **ctx) -> str:  # type: ignore[no-untyped-def]
    html = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>KOS Dashboard</title><style>{CSS}</style></head><body>
<nav class="nav">
<a href="/" class="{"active" if template == "search" else ""}">🔍 Search</a>
<a href="/ontology" class="{"active" if template == "ontology" else ""}">🕸 Ontology</a>
<a href="/health" class="{"active" if template == "health" else ""}">📊 Health</a>
<a href="/api/docs" target="_blank">📖 API</a>
</nav>"""
    for line in _render_content(template, ctx):  # type: ignore[no-untyped-call, func-returns-value, attr-defined]
        html += line + "\n"
    html += "</body></html>"
    return html


def _render_content(template, ctx) -> Iterator[str]:  # type: ignore[no-untyped-def]
    if template == "search":
        yield from _render_search(ctx)  # type: ignore[no-untyped-call, misc, func-returns-value]
    elif template == "ontology":
        yield from _render_ontology(ctx)  # type: ignore[no-untyped-call, misc, func-returns-value]
    elif template == "health":
        yield from _render_health(ctx)  # type: ignore[no-untyped-call, name-defined, misc, func-returns-value]
    elif template == "entity":
        yield from _render_entity(ctx)  # type: ignore[no-untyped-call, misc, func-returns-value]


def _render_search(ctx) -> Iterator[str]:  # type: ignore[no-untyped-def]
    q = ctx.get("q", "")
    zone = ctx.get("zone", "")
    results = ctx.get("results", [])
    count = ctx.get("count", 0)
    zones = ctx.get("zones", [])
    yield "<h1>🔍 Knowledge Search</h1>"
    yield '<form method="get"><div class="row">'
    yield f'<input name="q" value="{q}" placeholder="Search across 6 domains..." autofocus style="flex:3">'
    yield '<select name="zone" style="flex:1"><option value="">All zones</option>'
    for z in zones:
        sel = "selected" if z == zone else ""
        yield f'<option value="{z}" {sel}>{z}</option>'
    yield "</select>"
    yield '<button type="submit">Search</button></div></form>'
    if q:
        yield f'<p style="color:#8b949e;margin-bottom:12px">{count} results for <b>{q}</b></p>'
        for r in results:
            snippet = (r.get("snippet") or "").replace("<b>", "<b>").replace("</b>", "</b>")
            yield '<div class="result">'
            yield f'<h3><a href="/entity/{r.get("doc_id", "")}">{r["title"]}</a></h3>'
            yield f'<div class="zone">{r.get("zone", "")} · {r.get("kind", "")} · {r.get("trust_level", "")}</div>'
            yield f'<div class="path">{r.get("canonical_path", "")}</div>'
            if snippet:
                yield f'<div class="snippet">{snippet}</div>'
            yield "</div>"


def _render_ontology(ctx) -> Iterator[str]:  # type: ignore[no-untyped-def]
    entities = ctx.get("entities", [])
    q = ctx.get("q", "")
    yield "<h1>🕸 Knowledge Ontology</h1>"
    yield '<form method="get"><div class="row">'
    yield f'<input name="q" value="{q}" placeholder="Filter entities..." style="flex:3" autofocus>'
    yield '<button type="submit">Filter</button></div></form>'

    # Group by entity type
    type_order = ["Person", "Organization", "Project", "Concept", "Event", "Document"]
    type_icons = {
        "Person": "👤",
        "Organization": "🏢",
        "Project": "📋",
        "Concept": "💡",
        "Event": "📅",
        "Document": "📄",
    }
    grouped: dict[str, list[dict[str, Any]]] = {}
    for e in entities:
        t = e.get("entity_type", "Other")
        grouped.setdefault(t, []).append(e)

    total_with_rels = 0
    for t in type_order:
        if t not in grouped:
            continue
        items = grouped[t]
        icon = type_icons.get(t, "•")
        rel_count = sum(1 for e in items if e.get("rel_total", 0) > 0)
        total_with_rels += rel_count
        open_attr = "open" if t in ("Person", "Organization") else ""
        yield f'<div class="type-section"><details {open_attr}>'
        yield f'<summary class="type-header">{icon} {t} <span class="type-count">{len(items)} entities · {rel_count} with relations</span></summary>'
        yield '<div class="entity-grid">'
        for e in items:
            rcnt = e.get("rel_total", 0)
            yield f'<a href="/entity/{e["entity_id"]}" class="entity-card" style="text-decoration:none">'
            yield f'<div class="ename">{icon} {e["label"]}</div>'
            # Mini description snippet
            desc = (e.get("description") or "").replace("\n", " ")[:60]
            if desc and e.get("entity_type") != "Document":
                yield f'<div class="edesc">{desc}</div>'
            yield f'<div class="emeta"><span>{e.get("primary_zone", "")}</span></div>'
            yield '<div class="erels">'
            out_cnt = e.get("out_count", 0)
            in_cnt = e.get("in_count", 0)
            if rcnt > 0:
                if out_cnt:
                    yield f'<span class="erel-tag out"><strong>{out_cnt}</strong> 出</span>'
                if in_cnt:
                    yield f'<span class="erel-tag in"><strong>{in_cnt}</strong> 入</span>'
            else:
                yield '<span class="erel-tag warn">孤立</span>'
            yield "</div>"
            yield "</div>"
        yield "</div></details></div>"

    total = len(entities)
    orphan = total - total_with_rels
    yield f'<p style="color:#8b949e;margin-top:16px">{total} entities total · {orphan} orphans ({orphan * 100 // max(total, 1)}%)</p>'


def _render_entity(ctx) -> Iterator[str]:  # type: ignore[no-untyped-def]
    e = ctx.get("entity", {})
    outgoing = ctx.get("outgoing", [])
    incoming = ctx.get("incoming", [])
    doc_count = ctx.get("doc_count", 0)
    if not e:
        yield "<h1>Entity not found</h1>"
        return

    type_icon = {
        "Person": "👤",
        "Organization": "🏢",
        "Project": "📋",
        "Concept": "💡",
        "Event": "📅",
        "Document": "📄",
    }.get(e.get("entity_type", ""), "•")
    yield '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">'
    yield f'<span style="font-size:32px">{type_icon}</span>'
    yield "<div>"
    yield f'<h1 style="margin:0">{e.get("label", "")}</h1>'
    yield f'<span style="color:#8b949e;font-size:13px">{e.get("entity_type", "")} · {e.get("primary_zone", "")} · {doc_count} docs</span>'
    yield "</div></div>"

    desc = (e.get("description") or "").strip()
    if desc:
        yield '<div class="card" style="margin-bottom:16px">'
        for line in desc.split("\n")[:15]:
            line = line.strip()
            if not line:
                continue
            # Make entity references clickable
            line = re.sub(r"\[person-(\w+)\]\(#person-\w+\)", r'<a href="/entity/P:\1">P:\1</a>', line)
            line = re.sub(r"\[org-(\w+)\]\(#org-\w+\)", r'<a href="/entity/O:\1">O:\1</a>', line)
            yield f'<p style="margin:4px 0;font-size:13px;line-height:1.6;color:#c9d1d9">{line}</p>'
        yield "</div>"

    if outgoing:
        yield "<h2>▸ 对外关系</h2>"
        yield '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">'
        for r in outgoing:
            target = r.get("target_id", "")
            pred = r.get("predicate", "related_to")
            # Get target label
            t_label = _get_entity_label(target)
            yield f'<a href="/entity/{target}" class="rel-link"><span class="rel-key">{pred}</span> → {t_label or target}</a>'
        yield "</div>"

    if incoming:
        yield "<h2>▸ 被引用</h2>"
        yield '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px">'
        for r in incoming:
            source = r.get("source_id", "")
            pred = r.get("predicate", "related_to")
            s_label = _get_entity_label(source)
            yield f'<a href="/entity/{source}" class="rel-link">{s_label or source} <span class="rel-key">{pred}</span> →</a>'
        yield "</div>"

    yield '<p style="margin-top:24px"><a href="/ontology">← Back to Ontology</a></p>'


# Cache for entity labels (in-memory, resets on server restart)
_entity_label_cache: dict[str, str] = {}


def _get_entity_label(entity_id: str) -> str:
    if entity_id in _entity_label_cache:
        return _entity_label_cache[entity_id]  # type: ignore[no-any-return]
    return ""


@app.get("/", response_class=HTMLResponse, response_model=None)
async def search_page(q: str = "", zone: str = "", limit: int = 20) -> Any:
    """Search page (web UI)."""
    results: list[dict[str, Any]] = []
    count: int = 0
    zones: list[str] = []
    ctx = {"q": q, "zone": zone, "results": results, "zones": zones}
    return render("search", **ctx)


@app.get("/api/search")
async def api_search_legacy(q: str, zone: str = "", limit: int = 10):  # type: ignore[no-untyped-def]
    """Search API endpoint (legacy stub; primary is /api/v1/search)."""
    return {"results": []}


@app.get("/health")
async def health():  # type: ignore[no-untyped-def]
    """Minimal health endpoint for the KOS web surface."""
    return get_health_status()


@app.post("/api/collab/callback")
async def collab_callback(request: Request):  # type: ignore[no-untyped-def]
    """Webhook receiver: agentmesh task status callback → update KOS collab task.

    Expects JSON body: {agentmesh_task_id, status, output, error}
    """
    try:
        body = await request.json()
        agentmesh_task_id = body.get("agentmesh_task_id")
        if not agentmesh_task_id:
            return JSONResponse(
                {"error": "missing agentmesh_task_id"},
                status_code=400,
            )

        from kos.collab.api import update_task_by_agentmesh_id  # type: ignore[import-not-found]

        # Map agentmesh status to KOS collab status
        am_status = body.get("status", "")
        kos_status: str | None = None
        if am_status == "completed":
            kos_status = "done"
        elif am_status in ("failed", "cancelled"):
            kos_status = "failed"

        data: dict[str, object] = {}
        if kos_status:
            data["status"] = kos_status
        if body.get("output") is not None:
            data["resource_usage"] = str(body["output"])[:500]
        if body.get("error") is not None:
            data.setdefault("resource_usage", "")
            existing = data.get("resource_usage", "")
            data["resource_usage"] = f"{existing} | error: {body['error']}"[:500]

        updated = update_task_by_agentmesh_id(agentmesh_task_id, data) if data else None
        return {
            "status": "ok",
            "agentmesh_task_id": agentmesh_task_id,
            "updated": updated is not None,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("collab callback failed: %s", e)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=500)
