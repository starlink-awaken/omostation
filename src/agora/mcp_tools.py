from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Mcp Tools ≡ Tool
# 内涵 ≝ {Mcp, Tools}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, McpTools)}
# 功能 ⊢ {Mcp_Tools, Init_Mcp, Validate_Tools}
# =============================================================================

# ---
# domain: D-Gateway
# layer: organ
# status: active
# ---
"""Tool implementations and typed registry for the BOS MCP server."""


import dataclasses  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import sqlite3  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402
import uuid  # noqa: E402
from collections.abc import Callable  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

# TODO-migrate: from nucleus.Z_Spore.interfaces.surface_contract import SurfaceContract, SurfaceContractError, SurfaceIngressKind
SurfaceContract: Any = None
SurfaceContractError: Any = Exception
SurfaceIngressKind: Any = None

_log = logging.getLogger(__name__)

type JSONDict = dict[str, Any]
_ResultBus: Any | None = None
_TaskResult: Any | None = None
_NodeIdentityManager: Any | None = None
_SynapseLink: Any | None = None
_synapse_hello_handler: Any | None = None
_synapse_ping_handler: Any | None = None

try:
    import psutil as _psutil

    _HAS_PSUTIL = True
except ImportError:
    _psutil = None
    _HAS_PSUTIL = False
try:
    _TaskResult = __import__(
        "nucleus.Z_Spore.interfaces.swarm", fromlist=["TaskResult"]
    ).TaskResult
    _ResultBus = __import__(
        "organs.D_Execution.organs.engine.result_bus", fromlist=["ResultBus"]
    ).ResultBus
    _HAS_RESULT_BUS = True
except ImportError:
    _HAS_RESULT_BUS = False
    _ResultBus = None
    _TaskResult = None
try:
    _NodeIdentityManager = __import__(
        "organs.D_Gateway.organs.node_identity", fromlist=["NodeIdentityManager"]
    ).NodeIdentityManager
    _synapse_module = __import__(
        "organs.D_Gateway.organs.synapse_link",
        fromlist=["SynapseLink", "synapse_hello_handler", "synapse_ping_handler"],
    )
    _SynapseLink = _synapse_module.SynapseLink
    _synapse_hello_handler = _synapse_module.synapse_hello_handler
    _synapse_ping_handler = _synapse_module.synapse_ping_handler
    _HAS_SYNAPSE = True
except ImportError:
    _HAS_SYNAPSE = False
    _SynapseLink = None
    _NodeIdentityManager = None
    _synapse_hello_handler = None
    _synapse_ping_handler = None

_synapse_link: Any | None = None


def _get_synapse_link() -> Any | None:
    """Return (or lazily create) the module-level SynapseLink instance."""
    global _synapse_link
    if _synapse_link is not None:
        return _synapse_link
    if not _HAS_SYNAPSE or _SynapseLink is None or _NodeIdentityManager is None:
        return None
    try:
        mgr = _NodeIdentityManager()
        _synapse_link = _SynapseLink(mgr.load_or_create())
    except (OSError, ValueError) as exc:
        _log.warning("[MCPServer] Could not create SynapseLink: %s", exc)
        return None
    return _synapse_link


class _ParamError(ValueError):
    """Raised when a required JSON-RPC param is missing."""


def _require(params: JSONDict, key: str) -> Any:
    if key not in params:
        raise _ParamError(f"Missing required parameter: '{key}'")
    return params[key]


def _read_json_object(path: Path) -> JSONDict:
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return {str(key): value for key, value in raw.items()}


def _json_object(value: Any) -> JSONDict | None:
    if not isinstance(value, dict):
        return None
    return {str(key): item for key, item in value.items()}


def _surface_payload(surface: SurfaceContract) -> dict[str, Any]:
    """Return a serializable surface snapshot for tool responses."""
    return {"surface": surface.to_dict()}


def _mcp_surface_contract(
    params: JSONDict,
    *,
    operation: str,
    default_kind: SurfaceIngressKind,
) -> SurfaceContract:
    """Construct a typed MCP ingress contract from tool params."""
    control_plane = str(params.get("control_plane", "mcp") or "mcp")
    raw_kind = str(params.get("surface_kind", default_kind.value) or default_kind.value)
    try:
        ingress_kind = SurfaceIngressKind(raw_kind)
    except ValueError as exc:
        raise SurfaceContractError(
            f"{operation} received invalid surface_kind '{raw_kind}'"
        ) from exc
    if control_plane == "cockpit":
        ingress_kind = SurfaceIngressKind.SOVEREIGN_CONTROL
    return SurfaceContract.mcp(
        ingress_kind=ingress_kind,
        session_id=str(params.get("session_id", "")),
        node_id=str(params.get("controller_node_id", params.get("node_id", ""))),
        owner_id=str(params.get("owner_id", "")),
        hive_id=str(params.get("hive_id", "")),
        governance_scope=str(params.get("governance_scope", "")),
        sovereignty_level=str(params.get("sovereignty_level", "")),
        risk_tier=str(params.get("risk_tier", "standard")),
        control_plane=control_plane,
        metadata={
            key: params[key]
            for key in ("controller_session_id", "operation")
            if key in params and params[key] not in (None, "")
        }
        | {"operation": operation},
    )


@dataclasses.dataclass
class ToolContext:
    """Shared context passed to every tool handler function."""

    data_dir: str
    start_time: float
    file_lock: threading.Lock


type ToolHandler = Callable[[JSONDict, ToolContext], JSONDict]
type RegistryEntry = tuple[str, ToolHandler, str]


@dataclasses.dataclass(frozen=True)
class ToolEntry:
    """A registered tool with its handler and category."""

    name: str
    handler: ToolHandler
    category: str


class MCPToolRegistry:
    """Typed registry replacing the string-based dispatch dict."""

    def __init__(self) -> None:
        self._entries: dict[str, ToolEntry] = {}

    def register(self, name: str, handler: ToolHandler, category: str) -> None:
        self._entries[name] = ToolEntry(name=name, handler=handler, category=category)

    def get(self, name: str) -> ToolEntry | None:
        return self._entries.get(name)

    def dispatch(self, method: str, params: JSONDict, ctx: ToolContext) -> JSONDict:
        entry = self._entries.get(method)
        if entry is None:
            raise KeyError(method)
        return entry.handler(params, ctx)

    def methods(self) -> list[str]:
        return list(self._entries.keys())


def tool_ping(params: JSONDict, ctx: ToolContext) -> JSONDict:
    return {"pong": True, "worker_id": "server"}


def tool_post_result(params: JSONDict, ctx: ToolContext) -> JSONDict:
    task_id = str(_require(params, "task_id"))
    worker_id = str(_require(params, "worker_id"))
    if not (_HAS_RESULT_BUS and _TaskResult is not None and _ResultBus is not None):
        return {
            "accepted": False,
            "task_id": task_id,
            "error": "result_bus_unavailable",
        }

    result = _TaskResult(
        task_id=task_id,
        worker_id=worker_id,
        success=bool(params.get("success", False)),
        output=str(params.get("output", "")),
        quality_score=float(params.get("quality_score", 0.0)),
        eu_consumed=float(params.get("eu_consumed", 0.0)),
        duration_s=float(params.get("duration_s", 0.0)),
        error=str(params.get("error", "")),
    )
    try:
        _ResultBus.get_instance().post_result(result)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        _log.warning("[MCPServer] ResultBus post failed: %s", exc)
        return {
            "accepted": False,
            "task_id": task_id,
            "error": f"result_bus_delivery_failed: {exc}",
        }
    return {"accepted": True, "task_id": task_id}


def tool_get_task_info(params: JSONDict, ctx: ToolContext) -> JSONDict:
    worker_id = str(_require(params, "worker_id"))
    registry_path = Path(ctx.data_dir) / "worker_registry.json"
    if not registry_path.exists():
        return {"error": f"Worker '{worker_id}' not found — registry missing"}
    with ctx.file_lock:
        try:
            registry = _read_json_object(registry_path)
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            return {"error": f"Registry read error: {exc}"}
    worker_info = _json_object(registry.get(worker_id))
    if worker_info is None:
        return {"error": f"Worker '{worker_id}' not found"}
    return worker_info


def tool_broadcast_event(params: JSONDict, ctx: ToolContext) -> JSONDict:
    event_type = str(_require(params, "event_type"))
    source_worker_id = str(_require(params, "source_worker_id"))
    payload = params.get("payload", {})
    event_id, timestamp = str(uuid.uuid4()), time.time()
    record = {
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": event_type,
        "source_worker_id": source_worker_id,
        "payload": payload,
    }
    data_dir = Path(ctx.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    with ctx.file_lock:
        with (data_dir / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    return {"event_id": event_id, "timestamp": timestamp}


def tool_get_swarm_health(params: JSONDict, ctx: ToolContext) -> JSONDict:
    uptime = time.time() - ctx.start_time
    try:
        eu_balance = float(os.environ.get("BOS_EU_BALANCE", "0"))
    except ValueError:
        eu_balance = 0.0
    workers: list[JSONDict] = []
    registry_path = Path(ctx.data_dir) / "worker_registry.json"
    if registry_path.exists():
        try:
            with ctx.file_lock:
                registry = _read_json_object(registry_path)
            for wid, info in registry.items():
                worker_info = _json_object(info)
                if worker_info is None:
                    continue
                workers.append(
                    {
                        "id": wid,
                        "role": worker_info.get("role", "unknown"),
                        "status": worker_info.get("status", "unknown"),
                        "eu_usage": float(worker_info.get("eu_usage", 0.0)),
                    }
                )
        except (ValueError, json.JSONDecodeError, OSError) as exc:
            _log.warning("[MCPServer] worker registry read failed: %s", exc)
    wc, active = len(workers), sum(1 for w in workers if w.get("status") == "active")
    overall = (
        "healthy"
        if wc and active == wc
        else ("degraded" if wc == 0 or active > 0 else "unhealthy")
    )
    return {
        "overall": overall,
        "worker_count": wc,
        "workers": workers,
        "eu_balance": eu_balance,
        "mcp_server_uptime": round(uptime, 3),
    }


def tool_get_system_resources(params: JSONDict, ctx: ToolContext) -> JSONDict:
    uptime = time.time() - ctx.start_time
    if _HAS_PSUTIL and _psutil is not None:
        try:
            cpu, vm, disk = (
                _psutil.cpu_percent(interval=None),
                _psutil.virtual_memory(),
                _psutil.disk_usage("/"),
            )
            return {
                "cpu_percent": round(cpu, 2),
                "memory_used_mb": round(vm.used / 1_048_576, 2),
                "memory_total_mb": round(vm.total / 1_048_576, 2),
                "disk_used_gb": round(disk.used / 1_073_741_824, 2),
                "uptime_seconds": round(uptime, 3),
            }
        except (OSError, ValueError) as exc:
            _log.warning("[MCPServer] psutil read failed: %s", exc)
    return {
        "cpu_percent": 0.0,
        "memory_used_mb": 0.0,
        "memory_total_mb": 0.0,
        "disk_used_gb": 0.0,
        "uptime_seconds": round(uptime, 3),
    }


def tool_get_metrics_snapshot(params: JSONDict, ctx: ToolContext) -> JSONDict:
    try:
        eu_balance = float(os.environ.get("BOS_EU_BALANCE", "0"))
    except ValueError:
        eu_balance = 0.0
    daemon_port = int(os.environ.get("BOS_API_PORT", "7420"))
    tasks_total = tasks_success = active_workers = p99_latency_ms = 0.0
    try:
        req = urllib.request.Request(
            f"http://localhost:{daemon_port}/metrics", headers={"Accept": "text/plain"}
        )
        with urllib.request.urlopen(req, timeout=2) as resp:  # noqa: S310
            text = resp.read().decode("utf-8")
        for line in text.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            try:
                val = float(line.split()[-1])
            except ValueError:
                continue
            if line.startswith("bos_tasks_total"):
                tasks_total += val
                if 'status="success"' in line:
                    tasks_success = val
            elif line.startswith("bos_workers_active "):
                active_workers = val
            elif line.startswith("bos_eu_balance "):
                eu_balance = val
            elif (
                'quantile="0.99"' in line
                and "bos_http_request_duration_seconds" in line
            ):
                p99_latency_ms = val * 1000
    except (OSError, ValueError, TypeError):
        pass
    success_rate = (tasks_success / tasks_total) if tasks_total > 0 else 0.0
    return {
        "eu_balance": eu_balance,
        "active_workers": active_workers,
        "tasks_total": tasks_total,
        "tasks_success_rate": round(success_rate, 4),
        "p99_latency_ms": round(p99_latency_ms, 3),
    }


def tool_synapse_hello(params: JSONDict, ctx: ToolContext) -> JSONDict:
    link = _get_synapse_link()
    if link is None:
        return {"error": "SynapseLink not available"}
    if _synapse_hello_handler is None:
        return {"error": "Synapse hello handler not available"}
    response = _json_object(_synapse_hello_handler(link, params))
    if response is None:
        return {"error": "Synapse hello handler returned invalid payload"}
    return response


def tool_synapse_ping(params: JSONDict, ctx: ToolContext) -> JSONDict:
    link = _get_synapse_link()
    if link is None:
        return {"pong": True, "node_id": "unknown", "timestamp": time.time()}
    remote_id = params.get("node_id", "unknown")
    node = link.get_node(remote_id)
    if node is not None:
        from datetime import UTC, datetime

        node.last_seen = datetime.now(UTC)
    return {"pong": True, "node_id": link._identity.node_id, "timestamp": time.time()}


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
    except Exception as exc:
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


def tool_mail_handler(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for all mail_inbox actions — wraps MailTool."""
    try:
        from organs.D_Gateway.tools.mail_tool import MailTool  # type: ignore[import-not-found]
    except ImportError:
        return {
            "error": "MailTool not available (missing mail_tool.py)",
            "success": False,
        }

    try:
        tool = MailTool()
        action = params.pop("action", "list_mailboxes")
        request = __import__(
            "organs.D_Gateway.interfaces.tool_interface_contract",
            fromlist=["ToolRequest"],
        ).ToolRequest(
            tool_name="mail_inbox",
            action=action,
            params=params,
        )
        result = tool.execute(request)
        return {
            "success": result.success,
            "data": result.data,
            "error": result.error,
            "status": result.status.value,
        }
    except Exception as exc:
        _log.error("[MCPToolRegistry] mail handler error: %s", exc)
        return {"error": str(exc), "success": False}


def tool_tasks_list(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for tasks_list — wraps TasksTool via tool_tasks_handler."""
    from organs.D_Gateway.interfaces.tools.tasks_tool import tool_tasks_handler  # type: ignore[import-not-found]

    return tool_tasks_handler(params, ctx)


def tool_voice_speak(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for voice/speak — synthesize and play text as speech."""
    surface: SurfaceContract | None = None
    try:
        from organs.D_Voice.interfaces.voice_io import VoiceConfig  # type: ignore[import-not-found]
        from organs.D_Voice.tts.tts_provider import TTSProviderFactory  # type: ignore[import-not-found]
    except ImportError:
        return {"error": "D-Voice TTS not available", "success": False}

    try:
        surface = _mcp_surface_contract(
            params,
            operation="voice/speak",
            default_kind=SurfaceIngressKind.OBSERVABILITY,
        )
        surface.require(SurfaceIngressKind.SOVEREIGN_CONTROL, operation="voice/speak")
    except SurfaceContractError as exc:
        payload: dict[str, Any] = (
            _surface_payload(surface) if surface is not None else {}
        )
        error = str(exc)
        if (
            surface is not None
            and surface.ingress_kind is not SurfaceIngressKind.SOVEREIGN_CONTROL
        ):
            error = f"{error}; cockpit control_plane is required"
        return {"error": error, "success": False, **payload}

    try:
        provider_type = params.get("provider", "elevenlabs")
        config = VoiceConfig(
            provider_type=provider_type, metadata=params.get("config", {})
        )
        factory = TTSProviderFactory()
        tts = factory.create(provider_type, config)
        text = params.get("text", "")
        audio = tts.synthesize(text)
        if audio:
            tts.stream_audio(audio)
        return {
            "success": True,
            "provider": provider_type,
            "text_length": len(text),
            **_surface_payload(surface),
        }
    except Exception as exc:
        _log.error("[MCPToolRegistry] voice/speak error: %s", exc)
        return {"error": str(exc), "success": False, **_surface_payload(surface)}


def tool_voice_session_info(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for voice/session_info — return current voice session state."""
    surface: SurfaceContract | None = None
    try:
        surface = _mcp_surface_contract(
            params,
            operation="voice/session_info",
            default_kind=SurfaceIngressKind.OBSERVABILITY,
        )
        surface.require(
            SurfaceIngressKind.OBSERVABILITY,
            SurfaceIngressKind.SOVEREIGN_CONTROL,
            operation="voice/session_info",
        )
    except SurfaceContractError as exc:
        payload: dict[str, Any] = (
            _surface_payload(surface) if surface is not None else {}
        )
        return {"error": str(exc), "success": False, **payload}

    try:
        from organs.D_Voice.voice_session_manager import VoiceSessionManager  # type: ignore[import-not-found]
    except ImportError:
        return {
            "error": "VoiceSessionManager not available",
            "success": False,
            **_surface_payload(surface),
        }

    try:
        session = VoiceSessionManager()
        return {
            "success": True,
            "authoritative": False,
            "truth_owner": "D-Execution",
            **session.get_session_info(),
            **_surface_payload(surface),
        }
    except Exception as exc:
        return {"error": str(exc), "success": False, **_surface_payload(surface)}


def tool_voice_intent_digest(params: JSONDict, ctx: ToolContext) -> JSONDict:
    """MCP handler for voice/intent_digest — convert transcribed text to intent."""
    surface: SurfaceContract | None = None
    try:
        from organs.D_Voice.interfaces.voice_io import VoiceResult
        from organs.D_Voice.voice_intent_digestor import VoiceIntentDigestor  # type: ignore[import-not-found]
    except ImportError:
        return {"error": "VoiceIntentDigestor not available", "success": False}

    try:
        surface = _mcp_surface_contract(
            params,
            operation="voice/intent_digest",
            default_kind=SurfaceIngressKind.PERCEPTION,
        )
        surface.require(
            SurfaceIngressKind.PERCEPTION,
            SurfaceIngressKind.SOVEREIGN_CONTROL,
            operation="voice/intent_digest",
        )
    except SurfaceContractError as exc:
        payload: dict[str, Any] = (
            _surface_payload(surface) if surface is not None else {}
        )
        return {"error": str(exc), "success": False, **payload}

    try:
        text = params.get("text", "")
        result = VoiceResult(text=text, confidence=params.get("confidence", 1.0))
        digestor = VoiceIntentDigestor()
        intent_data = digestor.digest(result)
        return {
            "success": True,
            **intent_data,
            "surface": intent_data.get("surface", surface.to_dict()),
        }
    except Exception as exc:
        _log.error("[MCPToolRegistry] voice/intent_digest error: %s", exc)
        return {"error": str(exc), "success": False, **_surface_payload(surface)}


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


def build_default_registry() -> MCPToolRegistry:
    """Build the default MCP tool registry with all standard tools."""
    reg = MCPToolRegistry()
    # --- P5: digital_twin tool namespace ---
    # Tool implementations are provided by organs/D-Gateway/interfaces/base_tool.py
    # and registered here when their concrete adapters (mail, calendar, tasks) are ready.
    # Expected tool names: mail_inbox, calendar_events, tasks_list
    _dt_tool_registry: list[RegistryEntry] = []

    # --- Calendar Tool registration ---
    try:
        from organs.D_Gateway.tools.calendar_tool import (  # type: ignore[import-not-found]
            tool_calendar_check_conflicts,
            tool_calendar_create_event,
            tool_calendar_delete_event,
            tool_calendar_get_events,
            tool_calendar_list_calendars,
            tool_calendar_update_event,
        )

        _dt_tool_registry.extend(
            [
                (
                    "calendar/list_calendars",
                    tool_calendar_list_calendars,
                    "calendar_events",
                ),
                ("calendar/get_events", tool_calendar_get_events, "calendar_events"),
                (
                    "calendar/create_event",
                    tool_calendar_create_event,
                    "calendar_events",
                ),
                (
                    "calendar/update_event",
                    tool_calendar_update_event,
                    "calendar_events",
                ),
                (
                    "calendar/delete_event",
                    tool_calendar_delete_event,
                    "calendar_events",
                ),
                (
                    "calendar/check_conflicts",
                    tool_calendar_check_conflicts,
                    "calendar_events",
                ),
            ]
        )
    except ImportError:
        _log.warning(
            "[MCPToolRegistry] Calendar tool could not be loaded (missing dependencies)"
        )

    # --- Mail Tool registration ---
    _dt_tool_registry.extend(
        [
            ("mail/list_mailboxes", tool_mail_handler, "mail_inbox"),
            ("mail/fetch_emails", tool_mail_handler, "mail_inbox"),
            ("mail/send_email", tool_mail_handler, "mail_inbox"),
            ("mail/mark_read", tool_mail_handler, "mail_inbox"),
            ("mail/search_emails", tool_mail_handler, "mail_inbox"),
        ]
    )

    # --- Mail Tool registration ---
    _dt_tool_registry.extend(
        [
            ("mail/list_mailboxes", tool_mail_handler, "mail_inbox"),
            ("mail/fetch_emails", tool_mail_handler, "mail_inbox"),
            ("mail/send_email", tool_mail_handler, "mail_inbox"),
            ("mail/mark_read", tool_mail_handler, "mail_inbox"),
            ("mail/search_emails", tool_mail_handler, "mail_inbox"),
        ]
    )

    # --- Tasks Tool registration ---
    _dt_tool_registry.extend(
        [
            ("tasks/list", tool_tasks_list, "tasks_list"),
            ("tasks/get", tool_tasks_list, "tasks_list"),
            ("tasks/create", tool_tasks_list, "tasks_list"),
            ("tasks/update", tool_tasks_list, "tasks_list"),
            ("tasks/complete", tool_tasks_list, "tasks_list"),
            ("tasks/delete", tool_tasks_list, "tasks_list"),
            ("tasks/sources", tool_tasks_list, "tasks_list"),
        ]
    )

    for name, handler, cat in _dt_tool_registry + [
        ("ping", tool_ping, "core"),
        ("post_result", tool_post_result, "core"),
        ("get_task_info", tool_get_task_info, "core"),
        ("broadcast_event", tool_broadcast_event, "core"),
        ("get_swarm_health", tool_get_swarm_health, "monitoring"),
        ("get_system_resources", tool_get_system_resources, "monitoring"),
        ("get_metrics_snapshot", tool_get_metrics_snapshot, "monitoring"),
        ("synapse/hello", tool_synapse_hello, "synapse"),
        ("synapse/ping", tool_synapse_ping, "synapse"),
        ("memory/query", tool_memory_query, "domain"),
        ("execution/submit_task", tool_execution_submit_task, "domain"),
        ("governance/submit_request", tool_governance_submit_request, "domain"),
        ("evolution/status", tool_evolution_status, "domain"),
        ("swarm/dispatch", tool_swarm_dispatch, "domain"),
        # --- Voice Tool registration ---
        ("voice/speak", tool_voice_speak, "voice"),
        ("voice/session_info", tool_voice_session_info, "voice"),
        ("voice/intent_digest", tool_voice_intent_digest, "voice"),
    ]:
        reg.register(name, handler, cat)
    return reg
