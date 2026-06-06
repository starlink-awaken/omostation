"""Gateway API route handlers and management endpoints.

Adapted from agentmesh gateway routes/api.ts.
Provides health, task, space, agent, model, and skill management endpoints
that can be registered with FastAPI.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from agora.core.circuit_breaker import registry  # type: ignore[import-not-found]
from agora.vectors import vector_store  # type: ignore[import-not-found]

try:
    from fastapi import HTTPException

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

logger = logging.getLogger(__name__)

# ── Lazy module references (set by register_routes or on-demand) ──────
_task_manager = None
_router = None
_context_manager = None
_scheduler = None
_pipeline = None


def _get_tm():
    global _task_manager
    if _task_manager is None:
        from agora.task_manager import task_manager as tm  # type: ignore[import-not-found]
        _task_manager = tm
    return _task_manager


def _get_router():
    global _router
    if _router is None:
        from agora.core.router import router as r  # type: ignore[import-not-found]
        _router = r
    return _router


def _get_cm():
    global _context_manager
    if _context_manager is None:
        from agora.context import context_manager as cm  # type: ignore[import-not-found]
        _context_manager = cm
    return _context_manager


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        from agora.core.scheduler import scheduler as s  # type: ignore[import-not-found]
        _scheduler = s
    return _scheduler


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        from agora.pipeline import agent_pipeline as p  # type: ignore[import-not-found]
        _pipeline = p
    return _pipeline


# ── Health ────────────────────────────────────────────────────────────────────


async def handle_health() -> dict:
    """Health check endpoint."""
    tasks = _get_tm().get_all_tasks() if _get_tm() else []
    agents = _get_router().get_all_agents() if _get_router() else []

    status_counts = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
    for t in tasks:
        s = getattr(t, "status", "pending")
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "status": "running",
        "timestamp": int(time.time() * 1000),
        "tasks": status_counts,
        "agents": {
            "total": len(agents),
            "online": sum(1 for a in agents if getattr(a, "status", "") == "online"),
        },
    }


async def handle_detailed_health() -> dict:
    """Detailed health check with circuit breaker and vector store status."""
    health = await handle_health()
    health["circuit_breakers"] = registry.get_status()
    health["vector_store_available"] = vector_store.is_available()
    return health


# ── Tasks ─────────────────────────────────────────────────────────────────────


async def handle_submit_task(body: dict) -> dict:
    """Submit a new task for processing."""
    from agora.types import AgentMessage  # type: ignore[import-not-found]

    msg = AgentMessage(
        id=str(uuid.uuid4()),
        type="request",
        source=body.get("source", "api"),
        target="gateway",
        correlation_id=body.get("correlation_id", str(uuid.uuid4())),
        timestamp=int(time.time() * 1000),
        payload=body.get("payload"),
    )
    task = await _get_tm().process_task(msg)
    return {"task_id": task.id, "status": task.status, "message": "Task submitted"}


async def handle_get_task(task_id: str) -> dict:
    """Get a specific task's status."""
    task = _get_tm().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": f"Task {task_id} not found"})
    return {
        "id": task.id,
        "status": task.status,
        "assigned_agents": task.assigned_agents,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


async def handle_list_tasks() -> list[dict]:
    """List all tasks."""
    tasks = _get_tm().get_all_tasks()
    return [
        {
            "id": t.id,
            "status": t.status,
            "assigned_agents": t.assigned_agents,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        for t in tasks
    ]


async def handle_cancel_task(task_id: str) -> dict:
    """Cancel a task."""
    ok = _get_tm().cancel_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail={"code": "CANCEL_FAILED", "message": "Task not found or already completed"})
    return {"task_id": task_id, "status": "cancelled"}


# ── Scheduler ──────────────────────────────────────────────────────────────────


async def handle_create_schedule(body: dict) -> dict:
    """Create a scheduled task."""
    name = body.get("name")
    cron = body.get("cron")
    task = body.get("task")
    if not name or not cron or not task:
        raise HTTPException(status_code=400, detail={"code": "MISSING_FIELDS", "message": "name, cron, and task are required"})
    sid = _get_scheduler().add(name, cron, task)
    return {"schedule_id": sid, "name": name, "cron": cron}


async def handle_list_schedules() -> list[dict]:
    """List all schedules."""
    jobs = _get_scheduler().list()
    return [
        {"id": j.id, "name": j.name, "cron": j.cron, "enabled": j.enabled}
        for j in jobs
    ]


async def handle_delete_schedule(schedule_id: str) -> dict:
    """Delete a schedule."""
    if not _get_scheduler().remove(schedule_id):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Schedule not found"})
    return {"status": "removed"}


async def handle_run_pipeline(body: dict) -> dict:
    """Execute an agent pipeline."""
    steps = body.get("steps", [])
    input_data = body.get("input", "")
    if not steps or not input_data:
        raise HTTPException(status_code=400, detail={"code": "MISSING_FIELDS", "message": "steps (array) and input (string) are required"})
    return await _get_pipeline().execute(steps, input_data)


async def handle_create_space(body: dict) -> dict:
    """Create a shared space."""
    space_id = await _get_cm().create_shared_space(body.get("metadata"))
    return {"space_id": space_id}


async def handle_get_space(space_id: str) -> dict:
    """Get a shared space."""
    context = await _get_cm().get_shared_space(space_id)
    if not context:
        raise HTTPException(status_code=404, detail={"code": "SPACE_NOT_FOUND", "message": f"Shared space {space_id} not found"})
    return {
        "shared_space_id": context.shared_space_id,
        "message_count": len(context.messages),
        "metadata": context.metadata,
    }


async def handle_list_agents() -> list[dict]:
    """List all registered agents."""
    return _get_router().get_all_agents()


async def handle_register_agent(body: dict) -> dict:
    """Register a new agent."""
    _get_router().register_agent({
        "id": body.get("id", "unknown"),
        "name": body.get("name", "Unknown"),
        "type": body.get("type", "process"),
        "capabilities": body.get("capabilities", []),
        "status": "online",
        "endpoint": body.get("endpoint"),
        "last_seen": int(time.time() * 1000),
    })
    return {"id": body.get("id"), "status": "registered"}


# ── Phase 34 Wave 3: SSE Event Bus ──────────────────────────────────────────────

async def handle_events(request: Any, replay: int = 50):
    """Phase 34 Wave 3: SSE Pub/Sub Event Bus endpoint.
    Includes historical ring-buffer replay.
    """
    from fastapi.responses import StreamingResponse
    import asyncio
    from agora.core.state import get_event_bus, get_registry  # type: ignore[import-not-found]
    
    bus = get_event_bus(get_registry())
    
    async def event_generator():
        queue = asyncio.Queue()
        seen_ids = set()
        
        def on_event(event: dict):
            queue.put_nowait(event)
            
        bus.register_hook(on_event)
        try:
            import json
            # 1. Replay historical events
            if replay > 0:
                history = bus.get_event_log(limit=replay)
                for event in history:
                    event_id = event.get("id")
                    if event_id:
                        seen_ids.add(event_id)
                    yield f"id: {event_id}\ndata: {json.dumps(event)}\n\n"
                    
            # 2. Stream live events
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    event_id = event.get("id")
                    # Deduplicate in case an event was caught both in history and hook
                    if event_id and event_id in seen_ids:
                        continue
                    if event_id:
                        seen_ids.add(event_id)
                        
                    yield f"id: {event_id}\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            try:
                bus.remove_hook(on_event)
            except Exception:
                pass
                
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Route Registration ────────────────────────────────────────────────────────


def register_routes(router: Any, prefix: str = "/v1") -> None:
    """Register all API routes on a FastAPI router or app.

    Args:
        router: A FastAPI APIRouter or FastAPI app instance.
        prefix: URL prefix (default /v1).
    """
    if not HAS_FASTAPI:
        logger.warning("FastAPI not installed; cannot register gateway routes")
        return

    # Health
    router.add_api_route(f"{prefix}/health", handle_health, methods=["GET"])
    router.add_api_route(f"{prefix}/health/detailed", handle_detailed_health, methods=["GET"])

    # Phase 34 Wave 3: Event Bus
    router.add_api_route(f"{prefix}/events", handle_events, methods=["GET"])

    # Tasks
    router.add_api_route(f"{prefix}/tasks", handle_submit_task, methods=["POST"])
    router.add_api_route(f"{prefix}/tasks", handle_list_tasks, methods=["GET"])
    router.add_api_route(f"{prefix}/tasks/{{task_id}}", handle_get_task, methods=["GET"])
    router.add_api_route(f"{prefix}/tasks/{{task_id}}/cancel", handle_cancel_task, methods=["POST"])

    # Scheduler
    router.add_api_route(f"{prefix}/scheduler", handle_create_schedule, methods=["POST"])
    router.add_api_route(f"{prefix}/scheduler", handle_list_schedules, methods=["GET"])
    router.add_api_route(f"{prefix}/scheduler/{{schedule_id}}", handle_delete_schedule, methods=["DELETE"])

    # Pipeline
    router.add_api_route(f"{prefix}/pipeline", handle_run_pipeline, methods=["POST"])

    # Spaces
    router.add_api_route(f"{prefix}/spaces", handle_create_space, methods=["POST"])
    router.add_api_route(f"{prefix}/spaces/{{space_id}}", handle_get_space, methods=["GET"])

    # Agents
    router.add_api_route(f"{prefix}/agents", handle_list_agents, methods=["GET"])
    router.add_api_route(f"{prefix}/agents", handle_register_agent, methods=["POST"])
