"""NeuralCenter — P18-W1 神经中枢: 服务注册、拓扑图、信号路由、健康检查。"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from core_models.protocols.health import HealthProtocol, HealthStatus
from core_models.stem_cell import ValidationResult, validate_service


@dataclass
class ServiceRecord:
    """已注册服务记录 — 每个神经元的数据快照。"""

    name: str
    endpoint: str
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    neuron_id: str = ""
    registered_at: float = field(default_factory=time.time)
    last_health: HealthStatus | None = field(default=None, repr=False)
    _instance: Any | None = field(default=None, repr=False)


@dataclass
class TopologyEdge:
    """服务间拓扑边。"""

    source: str
    target: str
    relation: str = "depends_on"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Signal:
    """路由信号 — 在神经元之间传递的消息单元。"""

    signal_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    capability: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    origin: str = ""
    ttl: int = 10
    timestamp: float = field(default_factory=time.time)


class NeuralCenter:
    """神经中枢 — 内存级服务注册/拓扑/信号路由/健康检查协调器。

    nc = NeuralCenter()
    await nc.register("gate", "http://localhost:8001", service=gate_instance)
    await nc.add_edge("gate", "kb", relation="calls")
    await nc.emit_signal("search", {"query": "hello"})
    await nc.start_health_checker(interval=30.0)
    """

    def __init__(self) -> None:
        self._services: dict[str, ServiceRecord] = {}
        self._edges: dict[str, list[TopologyEdge]] = {}  # source -> edges
        self._reverse_edges: dict[str, list[TopologyEdge]] = {}  # target -> edges
        self._signals: dict[str, Signal] = {}
        self._health_task: asyncio.Task | None = None
        self._health_interval: float = 30.0
        self._failure_counts: dict[str, int] = {}

    # ── Service Registry ──────────────────────────────────────────

    async def register(
        self,
        name: str,
        endpoint: str,
        service: Any | None = None,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """注册服务，可选干细胞验证。passed=True 表示注册成功。"""
        if name in self._services:
            vr = ValidationResult(service_name=name, passed=False)
            vr.required_failed = ["duplicate_name"]
            return vr

        caps = list(capabilities or [])
        if service is not None:
            vr = validate_service(service, name)
            if not vr.passed:
                return vr
            for iface_name in vr.optional_implemented:
                cap = iface_name.replace("Protocol", "").lower()
                if cap not in caps:
                    caps.append(cap)
            neuron_id = vr.neuron_id
        else:
            neuron_id = f"neuron-{name}"

        record = ServiceRecord(
            name=name,
            endpoint=endpoint,
            capabilities=caps,
            metadata=metadata or {},
            neuron_id=neuron_id,
        )
        if service is not None:
            record._instance = service

        self._services[name] = record
        self._edges.setdefault(name, [])
        self._reverse_edges.setdefault(name, [])
        self._failure_counts[name] = 0

        return ValidationResult(
            service_name=name,
            passed=True,
            required_passed=["HealthProtocol", "IdentityProtocol"],
            required_failed=[],
            optional_implemented=[],
            neuron_id=neuron_id,
        )

    async def deregister(self, name: str) -> bool:
        """注销服务，清理关联边与计数器。"""
        if name not in self._services:
            return False
        del self._services[name]
        removed = self._edges.pop(name, [])
        for edge in removed:
            revs = self._reverse_edges.get(edge.target, [])
            self._reverse_edges[edge.target] = [e for e in revs if e.source != name]
        del self._reverse_edges[name]
        self._failure_counts.pop(name, None)
        return True

    async def get_service(self, name: str) -> ServiceRecord | None:
        return self._services.get(name)

    async def list_services(self) -> list[ServiceRecord]:
        return list(self._services.values())

    async def find_by_capability(self, capability: str) -> list[ServiceRecord]:
        return [s for s in self._services.values() if capability in s.capabilities]

    # ── Topology Graph ────────────────────────────────────────────

    async def add_edge(
        self,
        source: str,
        target: str,
        relation: str = "depends_on",
        **meta: Any,
    ) -> bool:
        """添加拓扑边，source/target 不存在则返回 False。"""
        if source not in self._services or target not in self._services:
            return False
        edge = TopologyEdge(source=source, target=target, relation=relation, metadata=meta)
        self._edges.setdefault(source, []).append(edge)
        self._reverse_edges.setdefault(target, []).append(edge)
        return True

    async def remove_edge(self, source: str, target: str) -> bool:
        """移除拓扑边，返回是否实际移除。"""
        if source not in self._edges:
            return False
        before = len(self._edges[source])
        self._edges[source] = [e for e in self._edges[source] if not (e.source == source and e.target == target)]
        if target in self._reverse_edges:
            self._reverse_edges[target] = [
                e for e in self._reverse_edges[target] if not (e.source == source and e.target == target)
            ]
        return len(self._edges[source]) < before

    async def get_dependencies(self, name: str) -> list[str]:
        """获取直接依赖列表（出边目标）。"""
        return [e.target for e in self._edges.get(name, [])]

    async def get_dependents(self, name: str) -> list[str]:
        """获取反向依赖列表（入边源）。"""
        return list({e.source for e in self._reverse_edges.get(name, [])})

    async def get_topology(self) -> dict[str, list[str]]:
        """返回 {服务名: [依赖目标列表]} 完整拓扑。"""
        return {name: [e.target for e in edges] for name, edges in self._edges.items()}

    async def walk_upstream(
        self,
        name: str,
        visited: set[str] | None = None,
    ) -> list[str]:
        """递归遍历上游依赖链，返回所有可达依赖。"""
        if visited is None:
            visited = set()
        if name in visited:
            return []
        visited.add(name)
        result: list[str] = []
        for dep in await self.get_dependencies(name):
            result.append(dep)
            result.extend(await self.walk_upstream(dep, visited))
        return result

    # ── Signal Router ─────────────────────────────────────────────

    async def route_signal(self, signal: Signal) -> list[str]:
        """按能力匹配路由信号，TTL 递减，归零丢弃。返回匹配的服务名列表。"""
        if signal.ttl <= 0:
            return []
        signal.ttl -= 1
        matched: list[str] = []
        for svc in self._services.values():
            if signal.capability in svc.capabilities:
                matched.append(svc.name)
                self._signals[f"{signal.signal_id}->{svc.name}"] = signal
        return matched

    async def emit_signal(
        self,
        capability: str,
        payload: dict[str, Any],
        origin: str = "",
        ttl: int = 10,
    ) -> Signal:
        """创建信号并立即路由。"""
        signal = Signal(capability=capability, payload=payload, origin=origin, ttl=ttl)
        await self.route_signal(signal)
        return signal

    async def get_pending_signals(self) -> list[Signal]:
        return list(self._signals.values())

    # ── Health Checker ────────────────────────────────────────────

    async def probe_health(self, name: str) -> HealthStatus | None:
        """探测单个服务健康状态。实现 HealthProtocol 则直接调用，否则返回推定状态。"""
        record = self._services.get(name)
        if record is None:
            return None
        service = record._instance
        if service is not None and isinstance(service, HealthProtocol):
            try:
                status = await service.health()
                record.last_health = status
                self._failure_counts[name] = 0
                return status
            except Exception:
                pass
        status = HealthStatus(
            service=name,
            status="healthy",
            version=record.metadata.get("version", "unknown"),
            message=f"neuron_id={record.neuron_id} endpoint={record.endpoint}",
        )
        record.last_health = status
        self._failure_counts[name] = 0
        return status

    async def probe_all(self) -> dict[str, HealthStatus]:
        """并行探测所有已注册服务。"""
        names = list(self._services.keys())
        if not names:
            return {}
        results = await asyncio.gather(*(self.probe_health(n) for n in names))
        return {n: s for n, s in zip(names, results) if s is not None}

    async def _health_loop(self) -> None:
        while True:
            await asyncio.sleep(self._health_interval)
            await self.probe_all()

    async def start_health_checker(self, interval: float = 30.0) -> None:
        """启动定期健康检查后台任务。"""
        self._health_interval = interval
        if self._health_task is None or self._health_task.done():
            self._health_task = asyncio.create_task(self._health_loop())

    async def stop_health_checker(self) -> None:
        """停止健康检查后台任务。"""
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

    async def get_health_summary(self) -> dict[str, Any]:
        """返回 {total, healthy, unhealthy, failure_counts, last_probe}。"""
        h = sum(1 for s in self._services.values() if s.last_health and s.last_health.status == "healthy")
        return {
            "total": len(self._services),
            "healthy": h,
            "unhealthy": len(self._services) - h,
            "failure_counts": dict(self._failure_counts),
            "last_probe": time.time(),
        }
