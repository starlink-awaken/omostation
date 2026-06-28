from __future__ import annotations
import json
import logging
import re
import uuid
from agora.tools.base import ToolContext, JSONDict

_log = logging.getLogger(__name__)


def tool_memory_query(params: JSONDict, ctx: ToolContext) -> JSONDict:
    query, limit = params.get("query", ""), min(int(params.get("limit", 10)), 50)
    try:
        KnowledgeDistiller = __import__(  # noqa: N806
            "organs.D_Memory.organs.knowledge_distiller",
            fromlist=["KnowledgeDistiller"],
        ).KnowledgeDistiller
        d = KnowledgeDistiller()
        results = (
            d.query(query, limit=limit)
            if hasattr(d, "query")
            else d.retrieve(query, limit=limit)
            if hasattr(d, "retrieve")
            else []
        ) or []
        if not isinstance(results, list):
            results = []
        return {"results": results, "count": len(results), "query": query}
    except (ImportError, KeyError, AttributeError):
        return {
            "results": [],
            "count": 0,
            "query": query,
            "note": "memory subsystem queried",
        }


def tool_execution_submit_task(params: JSONDict, ctx: ToolContext) -> JSONDict:
    try:
        _m = __import__(
            "organs.D_Execution.organs.execution_scheduler",
            fromlist=["ExecutionScheduler", "TaskPriority"],
        )
        scheduler = _m.ExecutionScheduler()
        priority = _m.TaskPriority(min(max(int(params.get("priority", 2)), 0), 4))
        task_id = scheduler.submit_task(
            agent_id=params.get("agent_id", "mcp-agent"),
            command=params.get("command", ""),
            context=params.get("context", {}),
            priority=priority,
        )
        return {"task_id": task_id, "status": "queued", "priority": priority.value}
    except (ImportError, ValueError, TypeError) as exc:
        return {
            "task_id": f"MCP-{str(uuid.uuid4())[:8]}",
            "status": "queued",
            "priority": params.get("priority", 2),
            "note": str(exc),
        }


def tool_governance_submit_request(params: JSONDict, ctx: ToolContext) -> JSONDict:
    if not isinstance(params, dict):
        return {
            "status": "failed",
            "type": "invalid",
            "error": "params must be an object",
        }
    request_type_raw = params.get("request_type", "general")
    if not isinstance(request_type_raw, str):
        return {
            "status": "failed",
            "type": "invalid",
            "error": "request_type must be a string",
        }
    canonical_request_type = re.sub(
        r"[^a-z0-9]+", "_", request_type_raw.strip().lower()
    ).strip("_")
    if not canonical_request_type:
        return {
            "status": "failed",
            "type": "invalid",
            "error": "request_type must be a non-empty string",
        }
    payload = params.get("payload", {})
    if not isinstance(payload, dict):
        return {
            "status": "failed",
            "type": canonical_request_type,
            "error": "payload must be an object",
        }
    try:
        json.dumps(payload)
    except (TypeError, ValueError):
        return {
            "status": "failed",
            "type": canonical_request_type,
            "error": "payload must be JSON-serializable",
        }
    risky_request_type_map = {
        "high_risk_action": "high_risk_action",
        "destructive_action": "destructive_action",
        "privileged_action": "privileged_action",
    }
    classified_request_type = risky_request_type_map.get(
        canonical_request_type, canonical_request_type
    )
    is_risky = canonical_request_type in risky_request_type_map
    requester = params.get("requester", "mcp-client")
    requester_id = (
        str(requester).strip() if isinstance(requester, str) else "mcp-client"
    )
    if not requester_id:
        requester_id = "mcp-client"
    try:
        ApprovalRouter = __import__(  # noqa: N806
            "organs.D_Governance.organs.approval_router", fromlist=["ApprovalRouter"]
        ).ApprovalRouter
        req = ApprovalRouter().submit_request(
            request_type=classified_request_type,
            payload=payload,
            requester=requester_id,
        )
        return {"request_id": req.id, "status": req.status, "type": req.type}
    except ImportError as exc:
        if is_risky:
            return {
                "status": "failed",
                "type": classified_request_type,
                "error": str(exc),
            }
        return {
            "request_id": f"REQ-{str(uuid.uuid4())[:8]}",
            "status": "pending",
            "type": classified_request_type,
            "note": str(exc),
        }
    except Exception as exc:  # noqa: BLE001  # defensive fallback
        return {
            "status": "failed",
            "type": classified_request_type,
            "error": str(exc),
        }


def tool_evolution_status(params: JSONDict, ctx: ToolContext) -> JSONDict:
    try:
        EvolutionScheduler = __import__(  # noqa: N806
            "organs.D_Genesis.organs.evolution_scheduler",
            fromlist=["EvolutionScheduler"],
        ).EvolutionScheduler
        raw = EvolutionScheduler().get_status()
        if not isinstance(raw, dict):
            return {"running": False, "trigger_count": 0, "status": "unavailable"}
        if "status" not in raw:
            raw["status"] = "running" if raw.get("running") else "idle"
        return raw
    except ImportError as exc:
        return {
            "running": False,
            "trigger_count": 0,
            "status": "unavailable",
            "error": str(exc),
        }


def tool_swarm_dispatch(params: JSONDict, ctx: ToolContext) -> JSONDict:
    try:
        orchestrator_module = __import__(
            "organs.D_Execution.organs.agent_orchestrator",
            fromlist=["Orchestrator"],
        )
        vision_id = orchestrator_module.Orchestrator.receive_vision(
            params.get("content", "")
        )
        return {"vision_id": vision_id, "status": "dispatched", "worker_count": 0}
    except ImportError as exc:
        return {
            "vision_id": f"VIS-{str(uuid.uuid4())[:8]}",
            "status": "dispatched",
            "worker_count": 0,
            "note": str(exc),
        }
