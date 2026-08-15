"""Production composition root joining Task 5 runtime and Task 6 data plane."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

import anyio
from fastapi import FastAPI

from omlxc.adapters import (
    LmsPlatform,
    LmStudioAdapter,
    OllamaAdapter,
    OmlxAppAdapter,
    TailscaleAdapter,
    TailscaleNodePolicy,
)
from omlxc.api import create_app
from omlxc.autonomy import (
    OperationTimeouts,
    PlacementOperationCoordinator,
    PlacementOperationOutcome,
    PlacementProbeFailure,
    PlacementProbeReason,
    PlacementTarget,
    PlacementWriteAction,
)
from omlxc.config import (
    AppConfig,
    BackendConfig,
    ModelConfig,
    NodeConfig,
    PlacementConfig,
    config_identity,
)
from omlxc.dataplane import (
    AdapterBinding,
    AdapterRegistry,
    BoundRouteTelemetry,
    CapacityCoordinator,
    ChatExecution,
    DataPlaneOrchestrator,
    EmbeddingExecution,
    ExecutionError,
    ExecutionErrorCode,
    Reranker,
    RerankExecution,
    RerankRequest,
    RouteTelemetryRecorder,
)
from omlxc.domain import (
    BackendKind,
    HealthSnapshot,
    Job,
    JobState,
    ModelSpec,
    Node,
    NodeDiagnosticCode,
    NodeDiagnosticOutcome,
    NodeDiagnosticReport,
    NodeState,
    PlacementRuntimeStatus,
    RiskLevel,
    RouteDecision,
    RouteRequest,
)
from omlxc.domain.protocols import (
    AdapterCapability,
    AdapterErrorCode,
    BackendAdapter,
    CapabilitySnapshot,
    ChatRequest,
    EmbeddingRequest,
    LifecycleResult,
    ModelRuntime,
    ModelRuntimeState,
    OperationStatus,
    StreamEvent,
)
from omlxc.events import EventBus, EventSubscription
from omlxc.scheduler import (
    PlacementSnapshot,
    RouteFailure,
    RoutePlanner,
    default_policies,
    is_static_eligible,
)
from omlxc.storage import (
    DurableEventRecord,
    MetricRecord,
    RouteAuditRecord,
    RouteAuditWrite,
    RunningRecoveryPolicy,
    SQLiteRuntimeStore,
    StoredJob,
)

from .runtime import DaemonRuntime


class StorageHandle:
    def __init__(self, config: AppConfig, *, metric_flush_interval_seconds: float) -> None:
        if metric_flush_interval_seconds <= 0:
            raise ValueError("metric flush interval must be positive")
        self._path = config.storage.database_path
        self._metric_flush_interval_seconds = metric_flush_interval_seconds
        self._store: SQLiteRuntimeStore | None = None
        self._metric_flush_task: asyncio.Task[None] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._metric_flush_wake = asyncio.Event()
        self._metric_flush_failures = 0
        self._metric_buffer_rejections = 0

    @property
    def ready(self) -> bool:
        return self._store is not None and not self._store.degraded

    @property
    def diagnostic(self) -> str:
        return self._store.diagnostic if self._store is not None else "storage_not_started"

    @property
    def task_settled(self) -> bool:
        flush_settled = self._metric_flush_task is None or self._metric_flush_task.done()
        close_settled = self._close_task is None or self._close_task.done()
        return flush_settled and close_settled

    @property
    def metric_flush_failures(self) -> int:
        return self._metric_flush_failures

    @property
    def metric_buffer_rejections(self) -> int:
        return self._metric_buffer_rejections

    def require(self) -> SQLiteRuntimeStore:
        if self._store is None:
            raise RuntimeError("daemon storage is not started")
        return self._store

    async def start(self) -> None:
        if self._store is None:
            if self._close_task is not None and not self._close_task.done():
                raise RuntimeError("daemon storage is still closing")
            self._close_task = None
            self._metric_flush_wake = asyncio.Event()
            self._metric_flush_failures = 0
            self._metric_buffer_rejections = 0
            self._store = await SQLiteRuntimeStore.open(self._path)
            self._metric_flush_task = asyncio.create_task(
                self._flush_metrics_periodically(), name="omlxcd-metric-flush"
            )

    async def close(self) -> None:
        task = self._close_task
        if task is None:
            task = asyncio.create_task(self._close_impl(), name="omlxcd-storage-handle-close")
            self._close_task = task
        interrupted = False
        with anyio.CancelScope(shield=True):
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    interrupted = True
                    current = asyncio.current_task()
                    if current is not None:
                        current.uncancel()
        task.result()
        if interrupted:
            raise asyncio.CancelledError

    async def _close_impl(self) -> None:
        task, self._metric_flush_task = self._metric_flush_task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        store, self._store = self._store, None
        if store is not None:
            await store.close()

    async def _flush_metrics_periodically(self) -> None:
        while True:
            with suppress(TimeoutError):
                await asyncio.wait_for(
                    self._metric_flush_wake.wait(),
                    timeout=self._metric_flush_interval_seconds,
                )
            self._metric_flush_wake.clear()
            store = self._store
            if store is None:
                return
            try:
                await store.flush_metrics()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._metric_flush_failures += 1

    async def append_route_audit(self, record: RouteAuditWrite) -> RouteAuditRecord:
        return await self.require().append_route_audit(record)

    def accept_metric(self, metric: MetricRecord) -> bool:
        accepted = self.require().accept_metric(metric)
        if not accepted:
            self._metric_buffer_rejections += 1
        self._metric_flush_wake.set()
        return accepted


class SnapshotCatalog:
    def __init__(
        self, snapshots: tuple[PlacementSnapshot, ...], *, now: Callable[[], datetime]
    ) -> None:
        self._snapshots = {snapshot.placement_id: snapshot for snapshot in snapshots}
        observed_at = now()
        self._observed_at = {snapshot.placement_id: observed_at for snapshot in snapshots}
        self._now = now

    def get(self) -> tuple[PlacementSnapshot, ...]:
        return tuple(self._snapshots[key] for key in sorted(self._snapshots))

    def get_one(self, placement_id: str) -> PlacementSnapshot:
        return self._snapshots[placement_id]

    def update(self, placement_id: str, **changes: object) -> None:
        self._snapshots[placement_id] = replace(self._snapshots[placement_id], **changes)
        self._observed_at[placement_id] = self._now()

    def observed_at(self, placement_id: str) -> datetime:
        return self._observed_at[placement_id]


@dataclass(frozen=True, slots=True)
class _RuntimeSummary:
    fresh: bool | None
    authorized: bool | None
    available: bool | None
    loaded: bool | None
    ready: bool | None
    last_observed_at: datetime | None


class CatalogProbe:
    def __init__(
        self,
        *,
        config: AppConfig,
        adapters: Mapping[str, BackendAdapter],
        catalog: SnapshotCatalog,
        tailscale: TailscaleAdapter | None,
        now: Callable[[], datetime],
    ) -> None:
        self._config = config
        self._adapters = dict(adapters)
        self._catalog = catalog
        self._tailscale = tailscale
        self._now = now
        self._interval = config.daemon.probe_interval_seconds
        self._timeout = min(max(self._interval, 0.1), 5.0)
        self._placements = {item.id: item for item in config.placements}
        self._models = {item.id: item for item in config.models}
        self._nodes = {item.id: item for item in config.nodes}
        self._backends = {item.id: item for item in config.backends}
        self._backend_nodes = {item.id: item.node_id for item in config.backends}
        self._diagnostics = {item.id: NodeDiagnosticCode.NOT_PROBED for item in config.backends}
        self._task: asyncio.Task[None] | None = None
        self._refresh_lock = asyncio.Lock()

    @property
    def task_settled(self) -> bool:
        return self._task is None or self._task.done()

    async def start(self) -> None:
        await self._refresh()
        self._task = asyncio.create_task(self._run(), name="omlxcd-catalog-probe")

    async def close(self) -> None:
        task, self._task = self._task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._refresh()

    async def _refresh(self) -> None:
        await self._refresh_backends(self._config.backends, task_name="omlxcd-tailscale-probe")

    async def refresh_backend(self, backend_id: str) -> None:
        await self._refresh_backends(
            (self._backends[backend_id],), task_name="omlxcd-tailscale-write-probe"
        )

    async def refresh_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        await self._refresh_backends(
            tuple(backend for backend in self._config.backends if backend.node_id == node_id),
            task_name="omlxcd-tailscale-node-probe",
        )
        return True

    async def _refresh_backends(
        self, backends: tuple[BackendConfig, ...], *, task_name: str
    ) -> None:
        async with self._refresh_lock:
            authorization = (
                asyncio.create_task(self._refresh_tailscale(), name=task_name)
                if self._tailscale is not None
                else None
            )
            await asyncio.gather(
                *(self._probe_backend(backend, authorization) for backend in backends),
                return_exceptions=True,
            )
            if authorization is not None:
                await asyncio.gather(authorization, return_exceptions=True)

    async def _refresh_tailscale(self) -> None:
        assert self._tailscale is not None
        async with asyncio.timeout(self._timeout):
            await self._tailscale.snapshot()

    async def _probe_backend(
        self, backend: BackendConfig, authorization: asyncio.Task[None] | None
    ) -> None:
        try:
            async with asyncio.timeout(self._timeout):
                authorized, local = await self._authorize(backend, authorization)
                if not authorized or not local:
                    raise PermissionError("backend endpoint is not authorized")
        except asyncio.CancelledError:
            raise
        except Exception:
            self._fail_authorization(backend.id)
            self._diagnostics[backend.id] = NodeDiagnosticCode.AUTHORIZATION_DENIED
            return
        try:
            async with asyncio.timeout(self._timeout):
                adapter = self._adapters[backend.id]
                capability = await adapter.discover()
                if capability.backend_id != backend.id:
                    raise ValueError("backend discovery identity mismatch")
                models = await adapter.list_models()
            self._apply(backend, capability, models, authorized=authorized, local=local)
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            self._fail_stale(backend.id, authorized=authorized, local=local)
            self._diagnostics[backend.id] = NodeDiagnosticCode.TIMEOUT
        except Exception:
            self._fail_stale(backend.id, authorized=authorized, local=local)
            self._diagnostics[backend.id] = NodeDiagnosticCode.PROBE_FAILED

    async def _authorize(
        self, backend: BackendConfig, authorization: asyncio.Task[None] | None
    ) -> tuple[bool, bool]:
        if is_loopback_url(backend.base_url):
            return True, True
        node = self._nodes[backend.node_id]
        if node.tailscale is None or self._tailscale is None or authorization is None:
            return False, False
        await authorization
        self._tailscale.authorize_http(backend.node_id, backend.base_url)
        if (
            backend.kind in {BackendKind.LM_STUDIO, BackendKind.LM_LINK}
            and backend.control_endpoint is not None
        ):
            authorized_ssh = self._tailscale.authorize_ssh(
                backend.node_id, backend.control_endpoint
            )
            if authorized_ssh.target != backend.control_endpoint:
                raise PermissionError("SSH control endpoint is not canonical")
        return True, True

    def _apply(
        self,
        backend: BackendConfig,
        capability: CapabilitySnapshot,
        models: tuple[ModelRuntime, ...],
        *,
        authorized: bool,
        local: bool,
    ) -> None:
        observed_age = (self._now() - capability.observed_at).total_seconds()
        fresh = 0 <= observed_age <= max(self._interval * 2, 1.0)
        inventory = {model.id: model for model in models}
        loadable_any = False
        saw_model = False
        saw_known_model = False
        generation_blocked = False
        for snapshot in self._catalog.get():
            if snapshot.backend_id != backend.id:
                continue
            placement = self._placements[snapshot.placement_id]
            model = inventory.get(snapshot.backend_model_id)
            capabilities = _model_capabilities(
                configured=_configured_model_capabilities(self._models[placement.model_id]),
                backend=capability.capabilities,
                runtime=(frozenset() if model is None else model.capabilities),
            )
            loaded = model is not None and model.state is ModelRuntimeState.LOADED
            saw_model = saw_model or model is not None
            saw_known_model = saw_known_model or (
                model is not None and model.state is not ModelRuntimeState.UNKNOWN
            )
            generation_blocked = generation_blocked or (
                loaded
                and not capability.generation_ready
                and not capabilities.isdisjoint(_GENERATION_MODEL_CAPABILITIES)
            )
            loadable = (
                fresh
                and capability.reachable
                and capability.compatible
                and capability.model_available
                and model is not None
                and model.state is not ModelRuntimeState.UNKNOWN
                and (
                    not loaded
                    or capability.generation_ready
                    or capabilities.isdisjoint(_GENERATION_MODEL_CAPABILITIES)
                )
            )
            loadable_any = loadable_any or loadable
            self._catalog.update(
                snapshot.placement_id,
                fresh=fresh,
                available=loadable,
                authorized=authorized,
                capabilities=frozenset(item.value for item in capabilities),
                context_limit=(
                    model.context_limit
                    if model is not None and model.context_limit is not None
                    else placement.context_limit
                ),
                memory_admitted=self._memory_admitted(placement),
                loaded=loaded,
                available_concurrency=1 if loadable else 0,
                local=local,
                security_allowed=authorized and local,
            )
        self._diagnostics[backend.id] = _node_diagnostic_code(
            capability=capability,
            fresh=fresh,
            loadable=loadable_any,
            saw_model=saw_model,
            saw_known_model=saw_known_model,
            generation_blocked=generation_blocked,
        )

    def diagnostics_for_node(self, node_id: str) -> tuple[NodeDiagnosticOutcome, ...]:
        counts: dict[NodeDiagnosticCode, int] = {}
        for backend in self._config.backends:
            if backend.node_id != node_id:
                continue
            code = self._diagnostics[backend.id]
            counts[code] = counts.get(code, 0) + 1
        return tuple(
            NodeDiagnosticOutcome(code=code, count=count)
            for code, count in sorted(counts.items(), key=lambda item: item[0].value)
        )

    def _memory_admitted(self, placement: PlacementConfig) -> bool | None:
        if placement.memory_gb is None:
            return None
        available = self._nodes[self._backend_nodes[placement.backend_id]].memory_gb
        return None if available is None else placement.memory_gb <= available

    def _fail_authorization(self, backend_id: str) -> None:
        for snapshot in self._catalog.get():
            if snapshot.backend_id == backend_id:
                self._catalog.update(
                    snapshot.placement_id,
                    fresh=False,
                    available=False,
                    authorized=False,
                    memory_admitted=None,
                    available_concurrency=0,
                    security_allowed=False,
                )

    def _fail_stale(self, backend_id: str, *, authorized: bool, local: bool) -> None:
        for snapshot in self._catalog.get():
            if snapshot.backend_id == backend_id:
                self._catalog.update(
                    snapshot.placement_id,
                    fresh=False,
                    available=False,
                    authorized=authorized,
                    memory_admitted=None,
                    available_concurrency=0,
                    security_allowed=authorized and local,
                )


class PlacementTargetFactory:
    def __init__(
        self,
        config: AppConfig,
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._placements = {item.id: item for item in config.placements}
        self._backends = {item.id: item for item in config.backends}
        self._monotonic = monotonic

    def __call__(self, snapshot: PlacementSnapshot) -> PlacementTarget:
        placement = self._placements[snapshot.placement_id]
        backend = self._backends[placement.backend_id]
        expected = (
            placement.model_id,
            placement.backend_id,
            placement.backend_model_id,
            backend.node_id,
        )
        actual = (
            snapshot.model_id,
            snapshot.backend_id,
            snapshot.backend_model_id,
            snapshot.node_id,
        )
        if actual != expected:
            raise ValueError("placement runtime binding differs from configuration")
        if placement.memory_gb is None:
            raise ValueError("placement memory budget is required for lifecycle operations")
        return PlacementTarget(
            id=placement.id,
            node_id=backend.node_id,
            model_id=placement.backend_model_id,
            resident=placement.resident,
            memory_gb=placement.memory_gb,
            idle_unload_seconds=0,
            last_used_monotonic=self._monotonic(),
            rollback_reference=f"placement:{placement.id}",
        )


class ProductionPlacementOperator:
    """Adapter lifecycle boundary whose catalog state always comes from fresh probes."""

    def __init__(
        self,
        *,
        config: AppConfig,
        adapters: Mapping[str, BackendAdapter],
        catalog: SnapshotCatalog,
        probe: CatalogProbe,
    ) -> None:
        self._adapters = dict(adapters)
        self._catalog = catalog
        self._probe = probe
        self._backend_by_placement = {
            placement.id: placement.backend_id for placement in config.placements
        }

    async def fresh_for_write(
        self, target: PlacementTarget, *, action: PlacementWriteAction
    ) -> bool:
        snapshot = self._catalog.get_one(target.id)
        if action is PlacementWriteAction.LOAD:
            return is_static_eligible(snapshot)
        return (
            snapshot.fresh
            and snapshot.available
            and snapshot.authorized
            and snapshot.local
            and snapshot.security_allowed
        )

    async def is_loaded(self, target: PlacementTarget) -> bool:
        await self._probe.refresh_backend(self._backend_by_placement[target.id])
        snapshot = self._catalog.get_one(target.id)
        if not snapshot.authorized:
            raise PlacementProbeFailure(target.id, PlacementProbeReason.AUTHORIZATION)
        if not snapshot.fresh:
            raise PlacementProbeFailure(target.id, PlacementProbeReason.STALE)
        if not snapshot.local or not snapshot.security_allowed:
            raise PlacementProbeFailure(target.id, PlacementProbeReason.LOCAL_SECURITY)
        if snapshot.loaded:
            return True
        if not snapshot.available:
            raise PlacementProbeFailure(target.id, PlacementProbeReason.UNAVAILABLE)
        return False

    async def load(self, target: PlacementTarget, *, idempotency_key: str) -> LifecycleResult:
        backend_id = self._backend_by_placement[target.id]
        return await self._adapters[backend_id].load_model(
            target.model_id, idempotency_key=idempotency_key
        )

    async def unload(self, target: PlacementTarget, *, idempotency_key: str) -> LifecycleResult:
        backend_id = self._backend_by_placement[target.id]
        return await self._adapters[backend_id].unload_model(
            target.model_id, idempotency_key=idempotency_key
        )


class ProductionEventService:
    def __init__(self, storage: StorageHandle, bus: EventBus) -> None:
        self._storage = storage
        self._bus = bus

    async def replay_events(
        self, *, after_sequence: int, limit: int
    ) -> tuple[DurableEventRecord, ...]:
        return await self._storage.require().replay_durable_events(
            after_sequence=after_sequence, limit=limit
        )

    def subscribe_events(self) -> EventSubscription:
        return self._bus.subscribe()


class ProductionInferenceService:
    def __init__(
        self,
        orchestrator: DataPlaneOrchestrator,
        model_ids: tuple[str, ...],
        model_aliases: Mapping[str, str] | None = None,
        reranker: Reranker | None,
    ) -> None:
        self._orchestrator = orchestrator
        self._model_ids = tuple(sorted(model_ids))
        self._model_aliases = dict(model_aliases or {})
        self._reranker = reranker

    def _normalized_model_id(self, model_id: str) -> str:
        return self._model_aliases.get(model_id, model_id)

    def _normalized_model_ids(self) -> tuple[str, ...]:
        return tuple(sorted({self._normalized_model_id(model_id) for model_id in self._model_ids}))

    async def list_openai_models(self) -> tuple[str, ...]:
        return self._normalized_model_ids()

    async def chat(
        self, route: RouteRequest, request: ChatRequest, *, deadline: float
    ) -> ChatExecution:
        return await self._orchestrator.chat(route, request, deadline=deadline)

    def stream_chat(
        self, route: RouteRequest, request: ChatRequest, *, deadline: float
    ) -> AsyncIterator[StreamEvent]:
        return self._orchestrator.stream_chat(route, request, deadline=deadline)

    async def embed(
        self, route: RouteRequest, request: EmbeddingRequest, *, deadline: float
    ) -> EmbeddingExecution:
        return await self._orchestrator.embed(route, request, deadline=deadline)

    async def rerank(
        self, *, request_id: str, query: str, documents: tuple[str, ...]
    ) -> RerankExecution:
        if self._reranker is None:
            return RerankExecution(
                request_id,
                (),
                ExecutionError(ExecutionErrorCode.UNSUPPORTED, False, reason="reranker_unset"),
            )
        return await self._orchestrator.rerank(
            self._reranker, RerankRequest(request_id, query, documents)
        )


class ProductionControlService:
    def __init__(
        self,
        *,
        config: AppConfig,
        storage: StorageHandle,
        catalog: SnapshotCatalog,
        probe: CatalogProbe,
        planner: RoutePlanner,
        coordinator: PlacementOperationCoordinator,
        target_factory: PlacementTargetFactory,
        bus: EventBus,
        id_factory: Callable[[], str],
        now: Callable[[], datetime],
        model_aliases: Mapping[str, str] | None = None,
        loaded_config_identity: str,
        worker_timeout: float = 120.0,
    ) -> None:
        self._config = config
        self._storage = storage
        self._catalog = catalog
        self._probe = probe
        self._planner = planner
        self._coordinator = coordinator
        self._target_factory = target_factory
        self._bus = bus
        self._id_factory = id_factory
        self._now = now
        self._model_aliases = dict(model_aliases or {})
        self._config_identity = loaded_config_identity
        self._worker_timeout = worker_timeout
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def _normalized_model_id(self, model_id: str) -> str:
        return self._model_aliases.get(model_id, model_id)

    @property
    def task_settled(self) -> bool:
        return all(task.done() for task in self._tasks.values())

    async def start(self) -> None:
        recovered = await self._storage.require().recover_jobs(
            {"load": RunningRecoveryPolicy.REQUEUE, "unload": RunningRecoveryPolicy.REQUEUE},
            observed_at=self._now(),
        )
        for job in recovered:
            if job.state is JobState.PENDING:
                self._schedule(job)

    async def close(self) -> None:
        tasks = tuple(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            done, pending = await asyncio.wait(tasks, timeout=1.0)
            del done
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()

    async def health(self) -> Mapping[str, object]:
        return {
            "status": "ready" if self._storage.ready else "degraded",
            "degraded": not self._storage.ready,
            "diagnostic": self._storage.diagnostic,
            "config_identity": self._config_identity,
        }

    async def list_nodes(self, *, after: str | None, limit: int) -> tuple[Node, ...]:
        snapshots = self._catalog.get()
        nodes = tuple(
            self._node_view(
                item,
                tuple(snapshot for snapshot in snapshots if snapshot.node_id == item.id),
            )
            for item in sorted(self._config.nodes, key=lambda node: node.id)
            if after is None or item.id > after
        )
        return nodes[:limit]

    async def probe_node(self, node_id: str) -> Node | None:
        node = next((item for item in self._config.nodes if item.id == node_id), None)
        if node is None or not await self._probe.refresh_node(node_id):
            return None
        snapshots = tuple(
            snapshot for snapshot in self._catalog.get() if snapshot.node_id == node.id
        )
        return self._node_view(node, snapshots)

    async def diagnose_node(self, node_id: str) -> NodeDiagnosticReport | None:
        node = next((item for item in self._config.nodes if item.id == node_id), None)
        if node is None:
            return None
        snapshots = tuple(
            snapshot for snapshot in self._catalog.get() if snapshot.node_id == node.id
        )
        return NodeDiagnosticReport(
            node=self._node_view(node, snapshots),
            outcomes=self._probe.diagnostics_for_node(node.id),
        )

    async def list_models(self, *, after: str | None, limit: int) -> tuple[ModelSpec, ...]:
        snapshots = self._catalog.get()
        models = tuple(
            self._model_view(
                item,
                tuple(snapshot for snapshot in snapshots if snapshot.model_id == item.id),
            )
            for item in sorted(self._config.models, key=lambda model: model.id)
            if after is None or item.id > after
        )
        return models[:limit]

    async def resolve_model(self, alias: str) -> ModelSpec | None:
        models = await self.list_models(after=None, limit=10000)
        normalized = self._normalized_model_id(alias)
        for m in models:
            if m.id == normalized or alias in m.aliases:
                return m
        return None

    def _node_view(self, node: NodeConfig, snapshots: tuple[PlacementSnapshot, ...]) -> Node:
        runtime = self._runtime_summary(snapshots)
        state = (
            NodeState.HEALTHY
            if runtime.ready is True
            else NodeState.DEGRADED
            if snapshots
            else NodeState.UNKNOWN
        )
        return Node(
            id=node.id,
            display_name=node.display_name,
            platform=node.platform,
            # Catalog views expose runtime health, never configured network identity.
            tailscale_identity=None,
            memory_gb=node.memory_gb,
            capabilities=frozenset(
                capability for snapshot in snapshots for capability in snapshot.capabilities
            ),
            health=HealthSnapshot(
                state=state,
                observed_at=runtime.last_observed_at or self._now(),
                stale=runtime.fresh is not True,
                detail="catalog_runtime" if snapshots else "configured_not_probed",
            ),
            fresh=runtime.fresh,
            authorized=runtime.authorized,
            available=runtime.available,
            loaded=runtime.loaded,
            ready=runtime.ready,
            last_observed_at=runtime.last_observed_at,
        )

    def _model_view(
        self, model: ModelConfig, snapshots: tuple[PlacementSnapshot, ...]
    ) -> ModelSpec:
        runtime = self._runtime_summary(snapshots)
        states = tuple(
            PlacementRuntimeStatus(
                placement_id=snapshot.placement_id,
                node_id=snapshot.node_id,
                backend_id=snapshot.backend_id,
                context_limit=snapshot.context_limit,
                fresh=snapshot.fresh,
                stale=not snapshot.fresh,
                authorized=snapshot.authorized,
                available=snapshot.available,
                loaded=snapshot.loaded,
                ready=_runtime_ready(snapshot),
                last_observed_at=self._catalog.observed_at(snapshot.placement_id),
            )
            for snapshot in snapshots
        )
        return ModelSpec(
            id=model.id,
            role=model.role,
            reasoning=model.reasoning,
            aliases=frozenset(model.aliases),
            capabilities=frozenset(
                capability for snapshot in snapshots for capability in snapshot.capabilities
            ),
            placement_states=states,
            fresh=runtime.fresh,
            authorized=runtime.authorized,
            available=runtime.available,
            loaded=runtime.loaded,
            ready=runtime.ready,
            last_observed_at=runtime.last_observed_at,
        )

    def _runtime_summary(self, snapshots: tuple[PlacementSnapshot, ...]) -> _RuntimeSummary:
        if not snapshots:
            return _RuntimeSummary(None, None, None, None, None, None)
        return _RuntimeSummary(
            fresh=any(item.fresh for item in snapshots),
            authorized=any(item.authorized for item in snapshots),
            available=any(item.available for item in snapshots),
            loaded=any(item.loaded for item in snapshots),
            ready=any(_runtime_ready(item) for item in snapshots),
            last_observed_at=max(
                self._catalog.observed_at(item.placement_id) for item in snapshots
            ),
        )

    async def plan_route(self, request: RouteRequest) -> RouteDecision | RouteFailure:
        return self._planner.plan(request, self._catalog.get())

    async def list_jobs(self, *, after: str | None, limit: int) -> tuple[Job, ...]:
        stored = await self._storage.require().list_jobs(after_job_id=after, limit=limit)
        return tuple(_job(item) for item in stored)

    async def get_job(self, job_id: str) -> Job | None:
        stored = await self._storage.require().get_job(job_id)
        return _job(stored) if stored is not None else None

    async def load_model(self, model_id: str, *, idempotency_key: str) -> Job:
        return await self._create_operation("load", model_id, idempotency_key)

    async def unload_model(self, model_id: str, *, idempotency_key: str) -> Job:
        return await self._create_operation("unload", model_id, idempotency_key)

    async def cancel_job(self, job_id: str) -> Job | None:
        store = self._storage.require()
        if await store.get_job(job_id) is None:
            return None
        stored = await store.request_job_cancel(
            job_id,
            observed_at=self._now(),
            event_id=f"job-{job_id}-cancel-requested",
        )
        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            task.cancel()
        return _job(stored)

    async def metrics_summary(self) -> Mapping[str, object]:
        return {
            "requests": await self._storage.require().metric_count(),
            "metric_flush_failures": self._storage.metric_flush_failures,
            "metric_buffer_rejections": self._storage.metric_buffer_rejections,
            "event_drops": self._bus.dropped_low_priority,
        }

    async def _create_operation(self, kind: str, model_id: str, key: str) -> Job:
        placement = self._placement_for_model(model_id)
        fingerprint = hashlib.sha256(
            json.dumps(
                {"kind": kind, "model_id": model_id}, separators=(",", ":"), sort_keys=True
            ).encode()
        ).hexdigest()
        now = self._now()
        created = await self._storage.require().create_job(
            Job(
                id=self._id_factory(),
                kind=kind,
                initiator="api",
                risk=RiskLevel.R1,
                state=JobState.PENDING,
                progress=0,
                created_at=now,
                updated_at=now,
                rollback_reference=f"placement:{placement.placement_id}",
            ),
            idempotency_key=key,
            payload_fingerprint=fingerprint,
        )
        if created.state is JobState.PENDING:
            self._schedule(created)
        return _job(created)

    def _schedule(self, job: StoredJob) -> None:
        existing = self._tasks.get(job.id)
        if existing is None or existing.done():
            task = asyncio.create_task(self._run_job(job), name=f"omlxcd-job-{job.id}")
            self._tasks[job.id] = task
            task.add_done_callback(lambda _task, job_id=job.id: self._tasks.pop(job_id, None))

    async def _run_job(self, job: StoredJob) -> None:
        store = self._storage.require()
        try:
            planning = await store.transition_job(
                job.id,
                JobState.PLANNING,
                progress=max(job.progress, 0.1),
                observed_at=self._now(),
                event_id=f"job-{job.id}-planning-{job.attempt}",
            )
            await store.transition_job(
                job.id,
                JobState.RUNNING,
                progress=max(planning.progress, 0.2),
                observed_at=self._now(),
                event_id=f"job-{job.id}-running-{job.attempt}",
            )
            placement = self._placement_from_reference(planning.rollback_reference)
            target = self._target_factory(placement)
            operation = (
                self._coordinator.ensure_loaded
                if job.kind == "load"
                else self._coordinator.ensure_unloaded
            )
            async with asyncio.timeout(self._worker_timeout):
                outcome = await operation(target)
            await self._finish(job, outcome)
        except asyncio.CancelledError:
            current = await store.get_job(job.id)
            if current is not None and current.state is JobState.CANCELLING:
                await store.transition_job(
                    job.id,
                    JobState.CANCELLED,
                    progress=current.progress,
                    observed_at=self._now(),
                    event_id=f"job-{job.id}-cancelled-{job.attempt}",
                )
            raise
        except PlacementProbeFailure as failure:
            current = await store.get_job(job.id)
            if current is not None and current.state in {JobState.PLANNING, JobState.RUNNING}:
                await store.transition_job(
                    job.id,
                    JobState.FAILED,
                    progress=current.progress,
                    observed_at=self._now(),
                    event_id=f"job-{job.id}-failed-{job.attempt}",
                    error_code=failure.reason.value,
                )
        except Exception:
            current = await store.get_job(job.id)
            if current is not None and current.state in {JobState.PLANNING, JobState.RUNNING}:
                await store.transition_job(
                    job.id,
                    JobState.FAILED,
                    progress=current.progress,
                    observed_at=self._now(),
                    event_id=f"job-{job.id}-failed-{job.attempt}",
                    error_code="operation_failed",
                )

    async def _finish(self, job: StoredJob, outcome: PlacementOperationOutcome) -> None:
        desired_loaded = job.kind == "load"
        result_succeeded = outcome.result is None or outcome.result.status in {
            OperationStatus.SUCCEEDED,
            OperationStatus.UNCHANGED,
        }
        succeeded = (
            outcome.authorized and outcome.actual_loaded is desired_loaded and result_succeeded
        )
        await self._storage.require().transition_job(
            job.id,
            JobState.SUCCEEDED if succeeded else JobState.FAILED,
            progress=1.0 if succeeded else 0.2,
            observed_at=self._now(),
            event_id=f"job-{job.id}-terminal-{job.attempt}",
            error_code=(
                None
                if succeeded
                else "authorization_denied"
                if not outcome.authorized
                else outcome.result.error.code.value
                if outcome.result is not None and outcome.result.error is not None
                else "postverify_failed"
            ),
        )

    def _placement_for_model(self, model_id: str) -> PlacementSnapshot:
        canonical_model_id = self._normalized_model_id(model_id)
        candidates = [
            item for item in self._catalog.get() if item.model_id == canonical_model_id
        ]
        if not candidates:
            raise KeyError("model has no configured placement")
        return candidates[0]

    def _placement_from_reference(self, reference: str | None) -> PlacementSnapshot:
        if reference is None or not reference.startswith("placement:"):
            raise ValueError("job placement reference is invalid")
        placement_id = reference.removeprefix("placement:")
        return next(item for item in self._catalog.get() if item.placement_id == placement_id)


class ResourceComponent:
    def __init__(
        self,
        bus: EventBus,
        adapters: Mapping[str, BackendAdapter],
        probe: CatalogProbe | None,
    ) -> None:
        self._bus = bus
        self._adapters = tuple(adapters.values())
        self._probe = probe

    @property
    def task_settled(self) -> bool:
        return self._probe is None or self._probe.task_settled

    async def start(self) -> None:
        if self._probe is not None:
            await self._probe.start()

    async def close(self) -> None:
        if self._probe is not None:
            await self._probe.close()
        await self._bus.close()
        for adapter in self._adapters:
            close = getattr(adapter, "aclose", None)
            if close is not None:
                await close()


@dataclass(frozen=True, slots=True)
class ProductionComposition:
    app: FastAPI
    runtime: DaemonRuntime
    control: ProductionControlService
    inference: ProductionInferenceService
    events: ProductionEventService


def build_production_daemon(
    config: AppConfig,
    *,
    adapters: Mapping[str, BackendAdapter] | None = None,
    snapshots: tuple[PlacementSnapshot, ...] | None = None,
    reranker: Reranker | None = None,
    tailscale: TailscaleAdapter | None = None,
    id_factory: Callable[[], str] | None = None,
    now: Callable[[], datetime] | None = None,
    metric_flush_interval_seconds: float = 0.25,
) -> ProductionComposition:
    """Build the real daemon graph without starting network or model operations."""
    clock = now or (lambda: datetime.now(UTC))
    configured_tailscale = (
        tailscale if tailscale is not None else build_configured_tailscale(config)
    )
    bindings = (
        dict(adapters)
        if adapters is not None
        else build_configured_adapters(config, tailscale=configured_tailscale)
    )
    model_aliases = _model_aliases(config)
    catalog = SnapshotCatalog(snapshots or _configured_snapshots(config), now=clock)
    planner = RoutePlanner(default_policies())
    storage = StorageHandle(config, metric_flush_interval_seconds=metric_flush_interval_seconds)
    bus = EventBus(capacity=128)
    probe = CatalogProbe(
        config=config,
        adapters=bindings,
        catalog=catalog,
        tailscale=configured_tailscale,
        now=clock,
    )
    target_factory = PlacementTargetFactory(config)
    placement_operator = ProductionPlacementOperator(
        config=config,
        adapters=bindings,
        catalog=catalog,
        probe=probe,
    )
    coordinator = PlacementOperationCoordinator(
        placement_operator,
        timeouts=OperationTimeouts.uniform(120.0),
        global_limit=4,
        per_node_limit=2,
    )
    control = ProductionControlService(
        config=config,
        storage=storage,
        catalog=catalog,
        probe=probe,
        planner=planner,
        coordinator=coordinator,
        target_factory=target_factory,
        bus=bus,
        id_factory=id_factory or (lambda: uuid4().hex),
        now=clock,
        model_aliases=model_aliases,
        loaded_config_identity=config_identity(config),
    )
    inference = ProductionInferenceService(
        DataPlaneOrchestrator(
            planner=planner,
            snapshot_provider=catalog.get,
            registry=AdapterRegistry(
                tuple(
                    AdapterBinding(backend_id, adapter) for backend_id, adapter in bindings.items()
                )
            ),
            capacity=CapacityCoordinator(global_limit=8, per_node=4, per_backend=4),
            loader=coordinator,
            load_target=target_factory,
            telemetry=BoundRouteTelemetry(storage, RouteTelemetryRecorder(now=clock)),
        ),
        tuple(model.id for model in config.models),
        model_aliases=model_aliases,
        reranker,
    )
    events = ProductionEventService(storage, bus)
    resources = ResourceComponent(bus, bindings, probe if snapshots is None else None)
    runtime = DaemonRuntime(
        config_runtime=storage,
        recovery=control,
        event_runtime=resources,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await runtime.start()
        try:
            yield
        finally:
            await runtime.close()

    app = create_app(control=control, inference=inference, events=events, lifespan=lifespan)
    return ProductionComposition(app, runtime, control, inference, events)


def build_configured_adapters(
    config: AppConfig,
    *,
    tailscale: TailscaleAdapter | None = None,
) -> dict[str, BackendAdapter]:
    return {
        backend.id: build_configured_adapter(backend, tailscale=tailscale)
        for backend in config.backends
    }


def build_configured_adapter(
    backend: BackendConfig,
    *,
    tailscale: TailscaleAdapter | None = None,
) -> BackendAdapter:
    if backend.kind is BackendKind.OMLX_APP:
        adapter: object = OmlxAppAdapter(backend_id=backend.id, base_url=backend.base_url)
    elif backend.kind is BackendKind.OLLAMA:
        adapter = OllamaAdapter(backend_id=backend.id, base_url=backend.base_url)
    else:
        control_authorizer = (
            _lm_control_authorizer(backend, tailscale)
            if backend.control_endpoint is not None and not is_loopback_url(backend.base_url)
            else None
        )
        adapter = LmStudioAdapter(
            backend_id=backend.id,
            base_url=backend.base_url,
            probe_model_id=backend.probe_model_id,
            ssh_target=backend.control_endpoint,
            known_hosts_file=backend.known_hosts_file,
            platform=LmsPlatform(backend.lms_platform),
            control_authorizer=control_authorizer,
        )
    return cast(BackendAdapter, adapter)


def _lm_control_authorizer(
    backend: BackendConfig,
    tailscale: TailscaleAdapter | None,
) -> Callable[[str], Awaitable[None]]:
    async def authorize(target: str) -> None:
        # Request-path control never performs an implicit status refresh. The
        # bounded periodic catalog probe owns refresh; stale state fails closed.
        if tailscale is None:
            raise PermissionError("Tailscale authorization is unavailable")
        accepted = tailscale.authorize_ssh(backend.node_id, target)
        if accepted.target != target:
            raise PermissionError("SSH control endpoint is not canonical")

    return authorize


def _model_aliases(config: AppConfig) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for model in config.models:
        aliases[model.id] = model.id
        for alias in model.aliases:
            aliases.setdefault(alias, model.id)
    return aliases


def build_configured_tailscale(config: AppConfig) -> TailscaleAdapter | None:
    if config.tailscale is None:
        return None
    policies = tuple(
        TailscaleNodePolicy(
            node_id=node.id,
            expected_peer_id=policy.peer_id,
            expected_public_key=policy.public_key,
            magic_dns_name=policy.magic_dns_name,
            allowed_ips=frozenset(policy.allowed_ips),
            allowed_http_ports=frozenset(policy.allowed_http_ports),
            allowed_ssh_users=frozenset(policy.allowed_ssh_users),
        )
        for node in config.nodes
        if (policy := node.tailscale) is not None
    )
    if not policies:
        return None
    try:
        return TailscaleAdapter(
            policies=policies,
            tailscale_executable=config.tailscale.executable,
            snapshot_ttl_seconds=config.tailscale.snapshot_ttl_seconds,
        )
    except ValueError:
        # Local backends remain available; every remote backend still fails closed.
        return None


def _configured_snapshots(config: AppConfig) -> tuple[PlacementSnapshot, ...]:
    backends = {backend.id: backend for backend in config.backends}
    models = {model.id: model for model in config.models}
    result: list[PlacementSnapshot] = []
    for placement in config.placements:
        backend = backends[placement.backend_id]
        model = models[placement.model_id]
        capabilities = _configured_model_capabilities(model)
        result.append(
            PlacementSnapshot(
                placement_id=placement.id,
                model_id=placement.model_id,
                backend_id=placement.backend_id,
                backend_model_id=placement.backend_model_id,
                node_id=backend.node_id,
                fresh=False,
                available=False,
                authorized=False,
                capabilities=frozenset(item.value for item in capabilities),
                context_limit=placement.context_limit,
                memory_admitted=None,
                loaded=placement.resident,
                ttft_ms=None,
                throughput_tps=None,
                queue_depth=0,
                error_rate=0,
                network_cost_ms=None,
                affinity=0,
                available_concurrency=1,
                local=True,
                security_allowed=True,
            )
        )
    return tuple(result)


_ROUTABLE_MODEL_CAPABILITIES = frozenset(
    {
        AdapterCapability.CHAT,
        AdapterCapability.STREAMING,
        AdapterCapability.VISION,
        AdapterCapability.EMBEDDING,
    }
)

_GENERATION_MODEL_CAPABILITIES = frozenset(
    {
        AdapterCapability.CHAT,
        AdapterCapability.STREAMING,
        AdapterCapability.VISION,
    }
)


def _node_diagnostic_code(
    *,
    capability: CapabilitySnapshot,
    fresh: bool,
    loadable: bool,
    saw_model: bool,
    saw_known_model: bool,
    generation_blocked: bool,
) -> NodeDiagnosticCode:
    """Reduce catalog facts to a stable, non-sensitive backend outcome."""
    if loadable:
        return NodeDiagnosticCode.AVAILABLE
    for error in capability.errors:
        if error.code is AdapterErrorCode.UNREACHABLE:
            return NodeDiagnosticCode.UNREACHABLE
        if error.code is AdapterErrorCode.TIMEOUT:
            return NodeDiagnosticCode.TIMEOUT
        if error.code is AdapterErrorCode.INCOMPATIBLE:
            return NodeDiagnosticCode.INCOMPATIBLE
        if error.code is AdapterErrorCode.MODEL_UNAVAILABLE:
            return NodeDiagnosticCode.MODEL_UNAVAILABLE
        return NodeDiagnosticCode.PROBE_FAILED
    if not capability.reachable:
        return NodeDiagnosticCode.UNREACHABLE
    if not capability.compatible:
        return NodeDiagnosticCode.INCOMPATIBLE
    if not capability.model_available or not saw_model:
        return NodeDiagnosticCode.MODEL_UNAVAILABLE
    if not fresh:
        return NodeDiagnosticCode.STALE
    if not saw_known_model:
        return NodeDiagnosticCode.RUNTIME_UNKNOWN
    if generation_blocked:
        return NodeDiagnosticCode.GENERATION_NOT_READY
    return NodeDiagnosticCode.PROBE_FAILED


def _configured_model_capabilities(model: ModelConfig) -> frozenset[AdapterCapability]:
    role = model.role.strip().lower()
    if role == "embedding":
        return frozenset({AdapterCapability.EMBEDDING})
    if role == "vision":
        return frozenset(
            {
                AdapterCapability.CHAT,
                AdapterCapability.STREAMING,
                AdapterCapability.VISION,
            }
        )
    if role == "chat":
        return frozenset({AdapterCapability.CHAT, AdapterCapability.STREAMING})
    return frozenset()


def _model_capabilities(
    *,
    configured: frozenset[AdapterCapability],
    backend: frozenset[AdapterCapability],
    runtime: frozenset[AdapterCapability],
) -> frozenset[AdapterCapability]:
    if not runtime:
        return configured
    return runtime & backend & _ROUTABLE_MODEL_CAPABILITIES


def is_loopback_url(value: str) -> bool:
    try:
        host = urlsplit(value).hostname
        return host is not None and ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _runtime_ready(snapshot: PlacementSnapshot) -> bool:
    return is_static_eligible(snapshot)


def _job(stored: StoredJob) -> Job:
    return Job(
        id=stored.id,
        kind=stored.kind,
        initiator=stored.initiator,
        risk=stored.risk,
        state=stored.state,
        progress=stored.progress,
        created_at=stored.created_at,
        updated_at=stored.updated_at,
        rollback_reference=stored.rollback_reference,
    )
