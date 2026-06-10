"""Agora Web Dashboard — FastAPI server with embedded UI.

Start: agora web
Access: http://localhost:7430

Features:
- Service status overview (circuit breaker states)
- Quick actions (discover, health check, register)
- Pipeline runner
- JSON API for programmatic access
- WebSocket real-time push (/ws)
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, Form, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from prometheus_client import REGISTRY, Gauge, generate_latest  # type: ignore[import-not-found]

from agora.agent_card import service_to_agent_card  # type: ignore[import-not-found]
from agora.audit_subscriber import AuditSubscriber  # type: ignore[import-not-found]
from agora.core.discovery import DiscoveryEngine  # type: ignore[import-not-found]
from agora.core.service_base import (  # type: ignore[import-not-found]
    Service,
    is_safe_url,
    parse_protocol_config,
    parse_tags,
)
from agora.core.state import get_event_bus, get_registry, get_router  # type: ignore[import-not-found]
from agora.pipeline import Pipeline  # type: ignore[import-not-found]
from agora.web import workspace_research  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from agora.a2a.task_manager import TaskManager  # type: ignore[import-not-found]

FORMAT_VERSION = "agora-v1"
API_KEY = os.environ.get("AGORA_API_KEY", "")


def _error_resp(message: str, status_code: int = 400) -> JSONResponse:
    """返回统一格式的错误响应."""
    return JSONResponse(
        {"status": "error", "error": message, "format_version": FORMAT_VERSION},
        status_code=status_code,
    )


async def _auth_middleware(request: Request, call_next):
    """Simple API Key auth for write endpoints."""
    # Allow read-only and preflight without auth
    if request.method in ("GET", "OPTIONS"):
        return await call_next(request)
    # Fail-closed: reject writes when no API key configured
    if not API_KEY:
        return _error_resp("Unauthorized: AGORA_API_KEY not configured", 401)
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return _error_resp("Unauthorized", 401)
    return await call_next(request)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    if not API_KEY:
        logger.warning(
            "AGORA_API_KEY not set — POST/PUT/DELETE requests will be rejected. Set AGORA_API_KEY to enable write access."
        )
    yield
    await router.close()


app = FastAPI(title="Agora Dashboard", version="1.5.0", lifespan=_lifespan)

# CORS — configurable via AGORA_CORS_ORIGINS env var (comma-separated)
_origins_str = os.environ.get("AGORA_CORS_ORIGINS", "http://localhost:8090,http://127.0.0.1:8090")
_allow_origins = [o.strip() for o in _origins_str.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.middleware("http")(_auth_middleware)

# Rate limiting — simple sliding window per IP (max 60 req/min)
_rate_limits: dict[str, list[float]] = {}
_RATE_LIMIT_MAX = int(os.environ.get("AGORA_RATE_LIMIT", "60"))
_RATE_LIMIT_WINDOW = 60.0  # seconds
_RATE_LIMIT_CLEANUP_AT = 500  # entries before cleanup


async def _rate_limit_middleware(request: Request, call_next):
    if _RATE_LIMIT_MAX <= 0:
        return await call_next(request)
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _rate_limits.setdefault(client, [])
    window[:] = [t for t in window if now - t < _RATE_LIMIT_WINDOW]
    if len(window) >= _RATE_LIMIT_MAX:
        return _error_resp("Rate limit exceeded", 429)
    window.append(now)
    # Periodic cleanup
    if len(_rate_limits) > _RATE_LIMIT_CLEANUP_AT:
        for k in list(_rate_limits):
            _rate_limits[k] = [t for t in _rate_limits.get(k, []) if now - t < _RATE_LIMIT_WINDOW]
            if not _rate_limits[k]:
                del _rate_limits[k]
    return await call_next(request)


app.middleware("http")(_rate_limit_middleware)

registry = get_registry()
_bus = get_event_bus(registry)
_auditor = AuditSubscriber(_bus, registry)
_bus.register_hook(_auditor.on_event)
router = get_router(registry, _bus)
discovery = DiscoveryEngine()
pipeline = Pipeline(registry, router)
_task_manager: TaskManager | None = None


def _get_tm() -> TaskManager:
    """Lazy-init and return the global TaskManager instance."""
    global _task_manager
    if _task_manager is None:
        from agora.a2a.task_manager import TaskManager

        _task_manager = TaskManager(router)
    return _task_manager


_proxy_manager = None

async def get_proxy_manager():
    global _proxy_manager
    if _proxy_manager is None:
        from agora.mcp_proxy.manager import ProxyManager
        import os
        _proxy_manager = ProxyManager()
        workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        gbrain_svc = {
            "name": "gbrain",
            "command": "bun",
            "args": ["run", "src/cli.ts", "serve"],
            "cwd": os.path.join(workspace_root, "projects/gbrain")
        }
        await _proxy_manager.start([gbrain_svc])
    return _proxy_manager



def _get_dashboard_html() -> str:
    """Lazy-load dashboard HTML to avoid import-time crash if file missing."""
    html_path = Path(__file__).parent / "dashboard.html"
    if html_path.exists():
        return html_path.read_text()
    return "<html><body><h1>Dashboard not found</h1><p>Run: agora web</p></body></html>"


# Prometheus gauges — created once at module level (not per scrape)
_METRIC_SVC_TOTAL = Gauge("agora_services_total", "Total registered services", registry=REGISTRY)
_METRIC_SVC_HEALTHY = Gauge("agora_services_healthy", "Healthy services", registry=REGISTRY)
_METRIC_SVC_DEGRADED = Gauge("agora_services_degraded", "Degraded/offline services", registry=REGISTRY)


# ── Pages ──────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _get_dashboard_html()


# ── WebSocket ──────────────────────────────────────────────────


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            svcs = registry.list_all()
            data = {
                "services": [
                    {
                        "name": s.name,
                        "circuit": s.circuit_state,
                        "healthy": s.healthy,
                        "failure_count": s.failure_count,
                        "protocol": s.protocol,
                    }
                    for s in svcs
                ],
                "healthy": len(registry.list_healthy()),
                "total": len(svcs),
            }
            await websocket.send_json(data)
            await asyncio.sleep(2)
    except Exception:
        pass


# ── API ────────────────────────────────────────────────────────


@app.get("/api/services")
async def api_services():
    return [
        {
            "name": s.name,
            "description": s.description,
            "protocol": s.protocol,
            "protocol_config": s.protocol_config,
            "mcp_endpoint": s.mcp_endpoint,
            "health_endpoint": s.health_endpoint,
            "circuit": s.circuit_state,
            "healthy": s.healthy,
            "failure_count": s.failure_count,
            "port": s.port,
            "tags": s.tags,
            "instances": len(s.instances) + 1,
        }
        for s in registry.list_all()
    ]


@app.get("/api/research")
async def api_research(limit: int = 10, q: str = "", status: str = "active", tag: str = ""):
    """Return workspace research. Supports ?q=keyword, ?status=active|archived|quarantined|all, ?tag=label."""
    if limit <= 0:
        return _error_resp("limit 必须大于 0", 400)
    allowed_statuses = {"active", "archived", "quarantined", "all"}
    if status not in allowed_statuses:
        return _error_resp(f"无效状态：{status}", 400)
    if q or tag or status != "active":
        return workspace_research.search_research(q=q, status=status, tag=tag, limit=limit)
    return workspace_research.list_recent_research(limit=limit)


@app.get("/api/research/{research_id}")
async def api_research_detail(research_id: int):
    """Return dossier/timeline/publications for a workspace research record."""
    detail = workspace_research.get_research_detail(research_id)
    if detail is None:
        return _error_resp("Research not found", 404)
    return detail


@app.post("/api/research/{research_id}/archive")
async def api_research_archive(research_id: int):
    """Archive a research record from the dashboard."""
    ok = workspace_research.archive_research(research_id)
    if not ok:
        return _error_resp("无法归档：研究不存在或已被归档", 400)
    return {"status": "ok", "id": research_id, "message": "已归档"}


@app.post("/api/research/{research_id}/publish")
async def api_research_publish(research_id: int):
    """Publish a research record as brief from the dashboard."""
    path = workspace_research.publish_brief(research_id)
    if path is None:
        return _error_resp("无法发布：研究不存在", 400)
    return {"status": "ok", "id": research_id, "path": path, "message": "已发布为 brief"}


@app.post("/api/research/{research_id}/sync")
async def api_research_sync(research_id: int, target: str = ""):
    """Sync published report to target directory."""
    path = workspace_research.sync_published(research_id, target_dir=target)
    if path is None:
        return _error_resp("同步失败：没有可同步的发布产物", 400)
    return {"status": "ok", "id": research_id, "path": path, "message": f"已同步到 {path}"}


@app.post("/api/research/{research_id}/unarchive")
async def api_research_unarchive(research_id: int):
    """Unarchive a research record from the dashboard."""
    ok = workspace_research.unarchive_research(research_id)
    if not ok:
        return _error_resp("恢复归档失败：研究不存在或未被归档", 400)
    return {"status": "ok", "id": research_id, "message": "已恢复归档"}


@app.post("/api/research/{research_id}/tag")
async def api_research_tag(research_id: int, tags: str = ""):
    """Tag a research record from the dashboard."""
    if not tags:
        return _error_resp("请提供标签", 400)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    ok = workspace_research.tag_research(research_id, tag_list)
    if not ok:
        return _error_resp("标签更新失败：研究不存在", 400)
    return {"status": "ok", "id": research_id, "tags": tag_list, "message": "标签已更新"}


@app.post("/api/research/{research_id}/rename")
async def api_research_rename(research_id: int, title: str = ""):
    """Rename a research record from the dashboard."""
    if not title:
        return _error_resp("请提供新标题", 400)
    ok = workspace_research.rename_research(research_id, title)
    if not ok:
        return _error_resp("重命名失败：研究不存在", 400)
    return {"status": "ok", "id": research_id, "title": title, "message": "已重命名"}


@app.post("/api/research/{research_id}/ask")
async def api_research_ask(research_id: int, question: str = ""):
    """Ask a follow-up question from the dashboard via CLI."""
    if not question:
        return _error_resp("请输入追问内容", 400)
    import subprocess
    from pathlib import Path as _Path

    # Resolve workspace CLI from project root
    workspace_cli = str(_Path(__file__).resolve().parent.parent.parent.parent / "bin" / "workspace")
    if not _Path(workspace_cli).exists():
        workspace_cli = "workspace"  # fallback to PATH
    result = subprocess.run(
        [workspace_cli, "research", "--ask", str(research_id), question],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        error_message = (result.stderr or "追问执行失败").strip()
        if "不存在" in error_message or "not found" in error_message.lower():
            return _error_resp(error_message, 400)
        return _error_resp(error_message, 500)
    return {"status": "ok", "id": research_id, "question": question, "output": result.stdout[-2000:]}


@app.get("/healthz")
async def healthz():
    """Unified health check (HP-01)."""
    await registry.health_check_all()
    healthy = registry.list_healthy()
    total = len(registry.list_all())
    overall = "ok" if len(healthy) == total else ("degraded" if len(healthy) > 0 else "down")
    deps = [{"name": s.name, "status": "ok" if s.healthy else "down"} for s in registry.list_all()]
    return {
        "status": overall,
        "service": "agora",
        "version": "1.5.0",
        "dependencies": deps,
    }


@app.get("/api/health")
async def api_health():
    await registry.health_check_all()
    healthy = registry.list_healthy()
    return {
        "status": "ok",
        "services": len(registry.list_all()),
        "healthy": len(healthy),
        "circuits": {s.name: registry.get_circuit_status(s.name) for s in registry.list_all()},
    }


@app.get("/api/pipeline/{name}/dag")
async def api_pipeline_dag(name: str):
    """Return pipeline dependency graph as node/edge data."""
    steps = pipeline.get_pipeline(name)
    if not steps:
        return {"status": "error", "error": f"Pipeline not found: {name}", "format_version": FORMAT_VERSION}
    nodes = []
    edges = []
    for i, step in enumerate(steps):
        node_id = f"step_{i}"
        tool = step["tool"]
        label = step.get("output_as", f"Step {i + 1}")
        deps = step.get("depends_on", [])
        nodes.append({"id": node_id, "label": label, "tool": tool, "index": i})
        for dep in deps:
            # Find which step produces this dependency
            for j, s in enumerate(steps):
                if s.get("output_as") == dep:
                    edges.append({"source": f"step_{j}", "target": node_id, "label": dep})
                    break
    return {"name": name, "nodes": nodes, "edges": edges}


@app.get("/api/pipelines")
async def api_pipelines():
    """List all available pipeline names."""
    return {"pipelines": pipeline.list_pipelines()}


@app.post("/api/discover")
async def api_discover():
    count = discovery.auto_register(registry)
    return {"discovered": count, "total": len(registry.list_all())}


@app.post("/api/register")
async def api_register(
    name: str = Form(...),
    protocol: str = Form("mcp"),
    protocol_config: str = Form("{}"),
    mcp_endpoint: str = Form(""),
    health_endpoint: str = Form(""),
    port: int = Form(0),
    tags: str = Form(""),
):
    # Parse protocol config JSON
    proto_cfg, err = parse_protocol_config(protocol_config)
    if err:
        return _error_resp(f"protocol_config is not valid JSON: {err}", 400)

    svc = Service(
        name=name,
        protocol=protocol,
        protocol_config=proto_cfg,
        mcp_endpoint=mcp_endpoint,
        health_endpoint=health_endpoint,
        port=port,
        tags=parse_tags(tags),
    )
    registry.register(svc)
    return {"status": "registered", "name": name, "protocol": protocol}


@app.post("/api/pipeline")
async def api_run_pipeline(
    name: str = Form(...),
    goal: str = Form(""),
    context: str = Form(""),
    project: str = Form("."),
    mode: str = Form("sequential"),
):
    variables = {"goal": goal, "context": context, "project": project}

    start = time.monotonic()
    if mode == "parallel":
        result = await pipeline.run_parallel(name, variables)
    else:
        result = await pipeline.run(name, variables)
    elapsed = time.monotonic() - start

    return {"pipeline": name, "mode": mode, "elapsed_s": round(elapsed, 3), **result}


@app.post("/api/clear")
async def api_clear():
    count = registry.clear_all()
    return {"status": "cleared", "removed": count}


@app.post("/api/sandbox/execute")
async def api_sandbox_execute(request_data: dict):
    """Execute arbitrary python code securely inside the KEI sandbox."""
    code = request_data.get("code", "")
    if not code:
        return _error_resp("Code is required", 400)
    
    try:
        from runtime.kei_sandbox import enable_sandbox
        from runtime.executor.sandbox import Sandbox
        # Enable sandbox (idempotent hook registration)
        enable_sandbox()
        # Execute the untrusted code
        res = Sandbox.execute(code)
        return {
            "success": res.success,
            "stdout": res.stdout,
            "duration_ms": res.duration_ms,
            "error": res.error,
            "output": res.output,
        }
    except Exception as e:
        return _error_resp(f"Sandbox execution failed: {e}", 500)


@app.post("/api/knowledge/put")
async def api_knowledge_put(request_data: dict):
    pm = await get_proxy_manager()
    slug = request_data.get("slug")
    title = request_data.get("title")
    content = request_data.get("content")
    if not slug or not title or not content:
        return _error_resp("slug, title, and content are required", 400)
    
    args = {
        "slug": slug,
        "title": title,
        "content": content,
        "tags": request_data.get("tags", [])
    }
    
    try:
        res = await pm.dispatch("gbrain.put_page", args)
        return {"status": "ok", "result": res}
    except Exception as e:
        return _error_resp(str(e), 500)


@app.post("/api/knowledge/search")
async def api_knowledge_search(request_data: dict):
    pm = await get_proxy_manager()
    query = request_data.get("query")
    if not query:
        return _error_resp("query is required", 400)
    
    try:
        res = await pm.dispatch("gbrain.search", {"query": query})
        return {"status": "ok", "result": res}
    except Exception as e:
        return _error_resp(str(e), 500)





@app.post("/api/instance")
async def api_add_instance(data: dict):
    """Add a load-balanced instance to a service."""
    svc_name = data.get("service", "")
    mcp_endpoint = data.get("mcp_endpoint", "")
    if not svc_name or not mcp_endpoint:
        return {"status": "error", "error": "service and mcp_endpoint required", "format_version": FORMAT_VERSION}
    # P1: Validate URL against SSRF before adding instance
    if mcp_endpoint.startswith("http") and not is_safe_url(mcp_endpoint):
        return {"status": "error", "error": "MCP endpoint URL blocked by SSRF policy", "format_version": FORMAT_VERSION}
    router._add_instance(svc_name, mcp_endpoint)
    return {"status": "ok", "service": svc_name, "instance": mcp_endpoint}


@app.get("/api/metrics/history")
async def api_metrics_history():
    """Return P50/P90/P99 latency history for dashboards."""
    pct = router.get_percentiles()
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "latency": pct,
        "services": len(registry.list_all()),
        "healthy": len(registry.list_healthy()),
    }


@app.get("/api/event-log")
async def api_event_log(limit: int = 20):
    """Return recent events from the event bus."""
    return _bus.get_event_log(limit)


@app.post("/api/event-publish")
async def api_event_publish(
    event_type: str = Form(...),
    payload: str = Form("{}"),
    source: str = Form("dashboard"),
):
    """Publish an event via the web dashboard."""
    import json as _json

    try:
        data = _json.loads(payload)
    except _json.JSONDecodeError:
        data = {"raw": payload}
    eid = _bus.publish(event_type, data, source)
    return {"event_id": eid, "status": "published"}


@app.get("/metrics")
async def api_metrics():
    """Prometheus-compatible metrics endpoint."""
    total = len(registry.list_all())
    healthy = len(registry.list_healthy())

    _METRIC_SVC_TOTAL.set(total)
    _METRIC_SVC_HEALTHY.set(healthy)
    _METRIC_SVC_DEGRADED.set(total - healthy)

    from fastapi.responses import PlainTextResponse

    return PlainTextResponse(content=generate_latest(REGISTRY), media_type="text/plain; version=0.0.4")


# ── State Transition endpoints (A2A-compatible) ──────────────────────


@app.get("/api/transitions")
async def api_transitions(since: str = "", limit: int = 50):
    """Get state transition history for all services."""
    return {"transitions": registry.get_transitions(since=since, limit=limit), "count": len(registry.get_transitions())}


@app.get("/api/transitions/{service}")
async def api_service_transitions(service: str, since: str = "", limit: int = 50):
    """Get state transition history for a specific service."""
    transitions = registry.get_transitions(service=service, since=since, limit=limit)
    return {"service": service, "transitions": transitions, "count": len(transitions)}


# ── Push Notification / Webhook endpoints (A2A-compatible) ────────────


@app.post("/api/webhook/events")
async def webhook_receive(request: Request):
    """Receive external events and inject them into the Agora event bus.

    Expected JSON body:
        {"event_type": "index:done", "payload": {...}, "source": "external"}

    Requires X-API-Key if authentication is configured.
    """
    body = await request.json()
    event_type = body.get("event_type", "")
    payload = body.get("payload", {})
    source = body.get("source", "webhook")

    if not event_type:
        return _error_resp("event_type is required", 400)

    event_id = _bus.publish(event_type, payload, source)
    return {"status": "ok", "event_id": event_id, "action": "received"}


@app.post("/api/a2a/push-notification")
async def a2a_push_notification(request: Request):
    """Register a push notification callback (A2A-compatible).

    Expected JSON body:
        {"callback_url": "http://example.com/events", "event_types": ["registry:*", "route:call.failed"]}
    """
    body = await request.json()
    callback_url = body.get("callback_url", "")
    event_types = body.get("event_types", ["*"])

    if not callback_url:
        return _error_resp("callback_url is required", 400)

    results = {}
    for pattern in event_types:
        sub_id = _bus.subscribe("a2a-push", pattern, callback_url)
        results[pattern] = sub_id

    return {
        "status": "ok",
        "subscriptions": results,
        "callback_url": callback_url,
    }


# ── A2A Task API endpoints ──────────────────────────────────────────


@app.post("/api/a2a/tasks/send")
async def a2a_tasks_send(request: Request):
    """Submit an A2A task and execute it synchronously.

    Expected JSON body:
        {
            "tool_name": "minerva.research_now",
            "arguments": {"topic": "quantum computing"},
            "session_id": ""
        }

    Returns the completed task with result.
    """
    body = await request.json()
    tool_name = body.get("tool_name", "")
    arguments = body.get("arguments", {})
    session_id = body.get("session_id", "")
    caller_identity = body.get("caller_identity", {})

    if not tool_name:
        return _error_resp("tool_name is required", 400)

    tm = _get_tm()
    task = tm.create_task("", tool_name, arguments, session_id, caller_identity=caller_identity)
    result = await tm.execute_task(task.id)

    if result is None:
        return _error_resp("Task execution returned no result", 500)

    return {"status": "ok", "task": result.to_dict()}


@app.get("/api/a2a/tasks/{task_id}")
async def a2a_tasks_get(task_id: str):
    """Get an A2A task's current status and result."""
    tm = _get_tm()
    task = tm.get_task(task_id)
    if task is None:
        return _error_resp(f"Task '{task_id}' not found", 404)
    return {"status": "ok", "task": task.to_dict()}


@app.post("/api/a2a/tasks/{task_id}/cancel")
async def a2a_tasks_cancel(task_id: str):
    """Cancel a submitted or in-progress A2A task."""
    tm = _get_tm()
    if tm.cancel_task(task_id):
        tm.get_task(task_id)
        return {"status": "ok", "action": "canceled", "task_id": task_id}
    return JSONResponse(
        {"status": "error", "error": f"Task '{task_id}' not found or already completed"}, status_code=400
    )


@app.get("/api/a2a/tasks")
async def a2a_tasks_list(request: Request):
    """List A2A tasks with optional filters.

    Query params:
        service: Filter by service name
        status: Filter by status (submitted|working|completed|failed|canceled)
        since: ISO timestamp lower bound
        limit: Max results (default 50)
    """
    service = request.query_params.get("service", "")
    status = request.query_params.get("status", "")
    since = request.query_params.get("since", "")
    limit = int(request.query_params.get("limit", 50))
    tm = _get_tm()
    tasks = tm.list_tasks(service=service, status=status, since=since, limit=limit)
    return {
        "status": "ok",
        "tasks": [t.to_dict() for t in tasks],
        "count": len(tasks),
    }


# ── A2A Agent Card endpoint ────────────────────────────────────────


@app.get("/.well-known/agent-card.json")
async def well_known_agent_card():
    """A2A-compatible Agent Card registry — all services as Agent Cards.

    Follows the A2A Agent Card spec:
      https://agent2agent.info/docs/concepts/agentcard/

    Returns a JSON object where keys are service names and values are
    Agent Cards with identity, capabilities, and skills.
    """
    services = registry.list_all()
    cards = {}
    from agora.governance import KeyManager  # type: ignore[import-not-found]

    has_auth = KeyManager().has_keys()

    for svc in services:
        try:
            tags = svc.tags if isinstance(svc.tags, list) else (svc.tags.split(",") if svc.tags else [])
            card = service_to_agent_card(
                name=svc.name,
                description=svc.description,
                protocol=svc.protocol,
                mcp_endpoint=svc.mcp_endpoint,
                port=svc.port,
                tags=tags,
                has_auth=has_auth,
                has_push_notifications=_bus.has_push_subscribers(),
                has_state_transitions=bool(registry.get_transitions(limit=1)),
                provider_info={"organization": "Agora Hub"},
                documentation_url="https://github.com/starlink-awaken/agora",
            )
            cards[svc.name] = card.to_dict()
        except Exception as e:
            cards[svc.name] = {"error": str(e)}

    return {
        "format_version": "a2a-v1",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "agents": cards,
        "count": len(cards),
    }


# ── CLI entry ──────────────────────────────────────────────────


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("COCKPIT_PORT", "8090")), log_level="info")  # noqa: S104


if __name__ == "__main__":
    main()
