"""NeuronPool — 神经元池: 连接代理、多路复用与故障转移。

BaseNeuron: 管理多个 ServiceRef 后端，按优先级路由，支持健康探测与自动 failover。
NeuronPool: 管理命名的 Neuron 实例，提供 get/create/remove 方法。
预构建工厂: Identity / Knowledge / Monitoring / Economy / Genesis。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class ServiceRef:
    """后端服务引用。"""

    name: str
    endpoint: str
    priority: int = 1
    healthy_status: bool = True

    def __hash__(self) -> int:
        return hash((self.name, self.endpoint))


@dataclass
class SignalResult:
    """信号触发结果。status_code=0 表示网络层失败。"""

    status_code: int = 0
    body: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300 and not self.error


# ── BaseNeuron ───────────────────────────────────────────────────────────────


class BaseNeuron:
    """连接代理。

    管理一个逻辑服务的多个 ServiceRef，按 priority 排序选择健康后端。
    请求失败时自动标记 unhealthy 并 failover 到下一个。

    用法:
        neuron = BaseNeuron("identity", [
            ServiceRef("metaos-identity", "http://localhost:8400", 1),
        ])
        r = await neuron.fire("GET", "/health")
    """

    def __init__(
        self,
        name: str,
        backends: list[ServiceRef],
        *,
        session: aiohttp.ClientSession | None = None,
    ):
        self.name = name
        self._backends = sorted(backends, key=lambda b: b.priority)
        self._session = session
        self._owns_session = session is None
        self._lock = asyncio.Lock()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._session and self._owns_session and not self._session.closed:
            await self._session.close()
            self._session = None

    # ── Health ──────────────────────────────────────────────────────────

    async def _health_probe(self, backend: ServiceRef) -> bool:
        """探测 /health 端点。"""
        url = f"{backend.endpoint.rstrip('/')}/health"
        try:
            session = await self._ensure_session()
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning("Neuron %s: %s returned %s", self.name, backend.name, resp.status)
                return resp.status == 200
        except Exception:
            return False

    async def probe_all(self) -> dict[str, bool]:
        results = await asyncio.gather(*(self._health_probe(b) for b in self._backends), return_exceptions=True)
        status_map: dict[str, bool] = {}
        for backend, r in zip(self._backends, results):
            healthy = r if isinstance(r, bool) else False
            backend.healthy_status = healthy
            status_map[backend.name] = healthy
        return status_map

    # ── Selection ───────────────────────────────────────────────────────

    async def _select_healthy_backend(self) -> ServiceRef:
        async with self._lock:
            for b in self._backends:
                if b.healthy_status:
                    return b
            for b in self._backends:
                if await self._health_probe(b):
                    b.healthy_status = True
                    return b
            logger.error("Neuron %s: all backends unhealthy, fallback to first", self.name)
            return self._backends[0]

    # ── Fire ────────────────────────────────────────────────────────────

    async def fire(
        self,
        method: str,
        path: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: float = 10.0,
    ) -> SignalResult:
        """向后端发送 HTTP 请求，失败时自动 failover。"""
        session = await self._ensure_session()
        tried: list[str] = []

        for _ in range(len(self._backends)):
            backend = await self._select_healthy_backend()
            if backend.name in tried:
                break
            tried.append(backend.name)
            url = f"{backend.endpoint.rstrip('/')}{path}"
            try:
                async with session.request(
                    method.upper(),
                    url,
                    json=json_body,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    body = await resp.text()
                    if resp.status < 500:
                        return SignalResult(status_code=resp.status, body=body)
                    logger.warning("Neuron %s: %s → %s, mark unhealthy", self.name, backend.name, resp.status)
                    backend.healthy_status = False
            except (aiohttp.ClientError, TimeoutError):
                logger.debug("Neuron %s: %s request failed", self.name, backend.name)
                backend.healthy_status = False
            except Exception:
                logger.exception("Neuron %s: unexpected error on %s", self.name, backend.name)
                backend.healthy_status = False

        return SignalResult(error=f"all backends exhausted (tried {tried})")


# ── NeuronPool ───────────────────────────────────────────────────────────────


@dataclass
class NeuronPool:
    """神经元池：管理命名的 Neuron 实例。

    用法:
        pool = NeuronPool()
        await pool.create("identity", [ServiceRef("metaos-identity", "http://localhost:8400", 1)])
        neuron = pool.get("identity")
    """

    _neurons: dict[str, BaseNeuron] = field(default_factory=dict, init=False, repr=False)
    _session: aiohttp.ClientSession | None = field(default=None, init=False, repr=False)

    async def _shared_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self._session

    async def create(self, name: str, backends: list[ServiceRef]) -> BaseNeuron:
        """创建（或替换）神经元。backends 不可为空。"""
        if not backends:
            raise ValueError(f"Neuron {name}: backends must not be empty")
        session = await self._shared_session()
        neuron = BaseNeuron(name, backends, session=session)
        self._neurons[name] = neuron
        logger.info("NeuronPool: created neuron '%s' with %d backend(s)", name, len(backends))
        return neuron

    def get(self, name: str) -> BaseNeuron | None:
        return self._neurons.get(name)

    async def get_or_create(self, name: str, backends: list[ServiceRef]) -> BaseNeuron:
        """获取已有神经元，不存在则用给定 backends 创建。"""
        if name in self._neurons:
            return self._neurons[name]
        return await self.create(name, backends)

    def remove(self, name: str) -> bool:
        if name in self._neurons:
            del self._neurons[name]
            return True
        return False

    def list_names(self) -> list[str]:
        return sorted(self._neurons.keys())

    def list_backends(self) -> dict[str, list[dict[str, Any]]]:
        return {
            name: [
                {"name": b.name, "endpoint": b.endpoint, "priority": b.priority, "healthy": b.healthy_status}
                for b in n._backends
            ]
            for name, n in self._neurons.items()
        }

    async def health_check_all(self) -> dict[str, dict[str, bool]]:
        """对所有神经元的所有后端执行健康检查。"""
        names, coros = [], []
        for name, neuron in self._neurons.items():
            names.append(name)
            coros.append(neuron.probe_all())
        results = await asyncio.gather(*coros, return_exceptions=True)
        out: dict[str, dict[str, bool]] = {}
        for name, r in zip(names, results):
            out[name] = r if isinstance(r, dict) else {}
        return out

    async def close(self) -> None:
        for neuron in self._neurons.values():
            await neuron.close()
        if self._session and not self._session.closed:
            await self._session.close()
        self._neurons.clear()


# ── Pre-built neuron factories ──────────────────────────────────────────────


def _make_neuron(
    name: str, service: str, endpoint: str, priority: int = 1, extra: list[ServiceRef] | None = None
) -> BaseNeuron:
    """内部工厂辅助：创建带单个默认后端的神经元。"""
    backends = [ServiceRef(service, endpoint, priority)]
    if extra:
        backends.extend(extra)
    return BaseNeuron(name, backends)


def create_identity_neuron(
    endpoint: str = "http://localhost:8400", extra: list[ServiceRef] | None = None
) -> BaseNeuron:
    return _make_neuron("identity", "metaos-identity", endpoint, extra=extra)


def create_knowledge_neuron(
    endpoint: str = "http://localhost:8401", extra: list[ServiceRef] | None = None
) -> BaseNeuron:
    return _make_neuron("knowledge", "metaos-knowledge", endpoint, extra=extra)


def create_monitoring_neuron(
    endpoint: str = "http://localhost:8402", extra: list[ServiceRef] | None = None
) -> BaseNeuron:
    return _make_neuron("monitoring", "metaos-monitor", endpoint, extra=extra)


def create_economy_neuron(endpoint: str = "http://localhost:8403", extra: list[ServiceRef] | None = None) -> BaseNeuron:
    return _make_neuron("economy", "metaos-economy", endpoint, extra=extra)


def create_genesis_neuron(endpoint: str = "http://localhost:8404", extra: list[ServiceRef] | None = None) -> BaseNeuron:
    return _make_neuron("genesis", "metaos-genesis", endpoint, extra=extra)
