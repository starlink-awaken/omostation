"""兼容层 — 为 cockpit web/app.py 提供 agora 组件 stub 实现。

当 agora 包不可用时（或作为独立 web dashboard 启动），本模块提供轻量 stub，
让 app.py 的所有 API 端点正常工作并展示 workspace 真实数据。
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace")))
RUNTIME_HOME = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime")))
LLM_COST_LOG_PATH = RUNTIME_HOME / "data" / "llm_cost.jsonl"
LLM_QUOTA_SUMMARY_PATH = RUNTIME_HOME / "data" / "llm_quota_summary.json"
PROVIDER_PLANE_PATH = WORKSPACE_ROOT / ".omo" / "state" / "provider-plane.yaml"


# ── Service ──────────────────────────────────────────────────────────────────


class Service:
    """轻量 Service 对象，携带所有 app.py 需要的属性。"""

    def __init__(
        self,
        name: str = "",
        description: str = "",
        protocol: str = "mcp",
        protocol_config: dict | None = None,
        mcp_endpoint: str = "",
        health_endpoint: str = "",
        port: int = 0,
        tags: list[str] | None = None,
        healthy: bool = True,
        circuit_state: str = "正常",
        failure_count: int = 0,
        instances: list[str] | None = None,
    ):
        self.name = name
        self.description = description
        self.protocol = protocol
        self.protocol_config = protocol_config or {}
        self.mcp_endpoint = mcp_endpoint
        self.health_endpoint = health_endpoint
        self.port = port
        self.tags = tags or []
        self.healthy = healthy
        self.circuit_state = circuit_state
        self.failure_count = failure_count
        self.instances = instances or []


def service_to_agent_card(
    name: str = "",
    description: str = "",
    protocol: str = "mcp",
    mcp_endpoint: str = "",
    port: int = 0,
    tags: list[str] | None = None,
    has_auth: bool = False,
    has_push_notifications: bool = False,
    has_state_transitions: bool = False,
    provider_info: dict | None = None,
    documentation_url: str = "",
):
    """返回 A2A Agent Card dict。"""

    class _Card:
        def __init__(self):
            self.name = name
            self.description = description
            self.protocol = protocol
            self.mcp_endpoint = mcp_endpoint
            self.port = port
            self.tags = tags or []
            self.has_auth = has_auth
            self.has_push_notifications = has_push_notifications
            self.has_state_transitions = has_state_transitions
            self.provider_info = provider_info or {}
            self.documentation_url = documentation_url

        def to_dict(self):
            return {
                "name": self.name,
                "description": self.description,
                "protocol": self.protocol,
                "mcp_endpoint": self.mcp_endpoint,
                "port": self.port,
                "tags": self.tags,
                "capabilities": {
                    "auth": self.has_auth,
                    "push_notifications": self.has_push_notifications,
                    "state_transitions": self.has_state_transitions,
                },
                "provider": self.provider_info,
                "documentation_url": self.documentation_url,
            }

    return _Card()


# ── EventBus ─────────────────────────────────────────────────────────────────


class EventBus:
    """兼容 EventBus，支持 publish/subscribe/emit/get_event_log/has_push_subscribers。"""

    def __init__(self):
        self._hooks: list = []
        self._event_log: list[dict] = []
        self._subscriptions: dict[str, list[dict]] = {}
        self._event_counter = 0

    def register_hook(self, hook):
        self._hooks.append(hook)

    def emit(self, event: dict):
        self._event_log.append(event)
        for hook in self._hooks:
            try:
                hook(event)
            except Exception:
                pass

    def publish(self, event_type: str, payload: dict, source: str = "system") -> str:
        self._event_counter += 1
        eid = f"evt-{self._event_counter}"
        event = {
            "id": eid,
            "type": event_type,
            "payload": payload,
            "source": source,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.emit(event)
        return eid

    def get_event_log(self, limit: int = 100) -> list[dict]:
        return list(reversed(self._event_log[-limit:]))

    def subscribe(self, subscriber_id: str, pattern: str, callback_url: str) -> str:
        sub_id = f"sub-{len(self._subscriptions) + 1}"
        self._subscriptions.setdefault(pattern, []).append(
            {"id": sub_id, "subscriber": subscriber_id, "callback": callback_url}
        )
        return sub_id

    def has_push_subscribers(self) -> bool:
        return bool(self._subscriptions)


# ── ServiceRegistry ──────────────────────────────────────────────────────────


class ServiceRegistry:
    """兼容 ServiceRegistry，支持 register/list_all/list_healthy/health_check_all/get_circuit_status/get_transitions/clear_all。"""

    def __init__(self):
        self._services: dict[str, Service] = {}
        self._transitions: list[dict] = []
        self._circuit_states: dict[str, str] = {}

    def register(self, name_or_service, service: Service | None = None):
        if service is None and isinstance(name_or_service, Service):
            svc = name_or_service
            name = svc.name
        else:
            name = str(name_or_service)
            svc = service or Service(name=name)
        self._services[name] = svc
        self._circuit_states.setdefault(name, "正常")
        self._transitions.append(
            {
                "service": name,
                "from": "unknown",
                "to": "registered",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    def list_all(self) -> list[Service]:
        return list(self._services.values())

    def list_healthy(self) -> list[Service]:
        return [s for s in self._services.values() if s.healthy]

    async def health_check_all(self):
        pass

    def get_circuit_status(self, name: str) -> str:
        return self._circuit_states.get(name, "正常")

    def get_transitions(self, service: str = "", since: str = "", limit: int = 50) -> list[dict]:
        result = self._transitions
        if service:
            result = [t for t in result if t.get("service") == service]
        if since:
            result = [t for t in result if t.get("timestamp", "") >= since]
        return result[-limit:]

    def clear_all(self) -> int:
        count = len(self._services)
        self._services.clear()
        return count


# ── WorkspaceResearch ────────────────────────────────────────────────────────


class WorkspaceResearch:
    """兼容类 — workspace research"""

    @staticmethod
    def list_recent_research(limit: int = 10) -> list:
        return []

    @staticmethod
    def search_research(q: str = "", status: str = "", tag: str = "", limit: int = 10) -> list:
        return []

    @staticmethod
    def get_research_detail(research_id: int) -> dict | None:
        return None

    @staticmethod
    def archive_research(research_id: int) -> bool:
        return True

    @staticmethod
    def publish_brief(research_id: int) -> str:
        return ""

    @staticmethod
    def sync_published(research_id: int, target_dir: str = "") -> str:
        return ""

    @staticmethod
    def unarchive_research(research_id: int) -> bool:
        return True

    @staticmethod
    def tag_research(research_id: int, tag_list: list) -> bool:
        return True

    @staticmethod
    def rename_research(research_id: int, title: str) -> bool:
        return True


workspace_research = WorkspaceResearch


# ── AuditSubscriber ──────────────────────────────────────────────────────────


class AuditSubscriber:
    """兼容类 — audit subscriber"""

    def __init__(self, *args, **kwargs):
        pass

    def on_event(self, *args, **kwargs):
        pass


# ── DiscoveryEngine ──────────────────────────────────────────────────────────


class DiscoveryEngine:
    """兼容类 — discovery engine"""

    def __init__(self, *args, **kwargs):
        pass

    def auto_register(self, registry: ServiceRegistry) -> int:
        return 0


# ── Pipeline ─────────────────────────────────────────────────────────────────


class Pipeline:
    """兼容类 — pipeline"""

    def __init__(self, *args, **kwargs):
        pass

    def get_pipeline(self, name: str) -> list:
        return []

    def list_pipelines(self) -> list:
        return []

    async def run(self, name: str, variables: dict) -> dict:
        return {"status": "ok", "output": ""}

    async def run_parallel(self, name: str, variables: dict) -> dict:
        return {"status": "ok", "output": ""}


# ── Router ───────────────────────────────────────────────────────────────────


class Router:
    """兼容类 — router"""

    def __init__(self, *args, **kwargs):
        self._instances: dict[str, list[str]] = {}

    def add_route(self, *args, **kwargs):
        pass

    def _add_instance(self, service_name: str, mcp_endpoint: str):
        self._instances.setdefault(service_name, []).append(mcp_endpoint)

    def get_percentiles(self) -> dict:
        return {"p50": 0, "p90": 0, "p99": 0}

    async def close(self):
        pass


# ── Helper functions ─────────────────────────────────────────────────────────


def get_event_bus(*args, **kwargs) -> EventBus:
    return EventBus()


def get_registry(*args, **kwargs) -> ServiceRegistry:
    return ServiceRegistry()


def get_router(*args, **kwargs) -> Router:
    return Router()


def is_safe_url(url: str) -> bool:
    return True


def parse_protocol_config(config: str) -> tuple[dict, str | None]:
    try:
        return json.loads(config) if config else {}, None
    except json.JSONDecodeError as e:
        return {}, str(e)


def parse_tags(tags: str) -> list[str]:
    return [t.strip() for t in tags.split(",") if t.strip()]


# ── Workspace 服务种子 ────────────────────────────────────────────────────────

_KNOWN_SERVICES = [
    Service(
        name="agora",
        description="MCP Hub · 服务发现/路由/代理/治理",
        protocol="mcp",
        mcp_endpoint="http://localhost:7431",
        port=7431,
        tags=["l0", "mesh", "mcp"],
        healthy=True,
    ),
    Service(
        name="cockpit",
        description="统一入口 (CLI 27 + MCP 37 + Web)",
        protocol="http",
        mcp_endpoint="http://localhost:8090",
        port=8090,
        tags=["l3", "cli", "web"],
        healthy=True,
    ),
    Service(
        name="runtime",
        description="运行时 · KEI沙箱 · Matrix调度",
        protocol="mcp",
        port=7450,
        tags=["l1", "runtime", "sandbox"],
        healthy=True,
    ),
    Service(
        name="kairon",
        description="知识引擎 · 19 packages · 4157 tests",
        protocol="mcp",
        tags=["l2", "knowledge", "engine"],
        healthy=True,
    ),
    Service(
        name="gbrain",
        description="Postgres 知识数据库 · 67 MCP tools",
        protocol="mcp",
        port=3000,
        tags=["l2", "knowledge", "database"],
        healthy=True,
    ),
    Service(
        name="omo",
        description="治理面 · Agent OS 内核",
        protocol="mcp",
        tags=["l2", "governance"],
        healthy=True,
    ),
    Service(
        name="metaos",
        description="编排引擎 · 决策门控/免疫/路由",
        protocol="mcp",
        tags=["l2", "orchestration"],
        healthy=True,
    ),
    Service(
        name="ecos",
        description="L0 协议层 · SSB签名链 · MOF元模型",
        protocol="mcp",
        tags=["l0", "protocol"],
        healthy=True,
    ),
    Service(
        name="aetherforge",
        description="算力网格 + LLM 网关 + 群体智能",
        protocol="mcp",
        tags=["x", "compute", "llm"],
        healthy=True,
    ),
    Service(
        name="aetherforge-swarm",
        description="群体智能引擎 — 已并入 aetherforge/packages/swarm",
        protocol="mcp",
        tags=["x", "multi-agent", "swarm"],
        healthy=True,
    ),
    Service(
        name="l4-kernel",
        description="自我层管理面 · 21域 · 250 tests · 43 MCP tools",
        protocol="mcp",
        tags=["l4", "self", "kernel"],
        healthy=True,
    ),
]


def seed_registry(registry: ServiceRegistry) -> int:
    """注册所有已知 workspace 服务到 registry。返回注册数量。"""
    for svc in _KNOWN_SERVICES:
        registry.register(svc)
    return len(_KNOWN_SERVICES)
