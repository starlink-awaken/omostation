"""Production composition root joining Task 5 runtime and Task 6 data plane."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4

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
    CapacityCoordinator,
    ChatExecution,
    DataPlaneOrchestrator,
    EmbeddingExecution,
    ExecutionError,
    ExecutionErrorCode,
    Reranker,
    RerankExecution,
    RerankRequest,
)
from omlxc.domain import (
    BackendKind,
    HealthSnapshot,
    Job,
    JobState,
    ModelSpec,
    Node,
    NodeState,
    PlacementRuntimeStatus,
    RiskLevel,
    RouteDecision,
    RouteRequest,
)
from omlxc.domain.protocols import (
    BackendAdapter,
    CapabilitySnapshot,
    ChatRequest,
    EmbeddingRequest,
    LifecycleResult,
    ModelRuntime,
    OperationStatus,
    StreamEvent,
)
from omlxc.events import EventBus, EventSubscription
from omlxc.scheduler import PlacementSnapshot, RouteFailure, RoutePlanner, default_policies
from omlxc.storage import (
    DurableEventRecord,
    RunningRecoveryPolicy,
    SQLiteRuntimeStore,
    StoredJob,
)

from .runtime import DaemonRuntime


class StorageHandle:
    def __init__(self, config: AppConfig) -> None:
        self._path = config.storage.database_path
        self._store: SQLiteRuntimeStore | None = None

    @property
    def ready(self) -> bool:
        return self._store is not None and not self._store.degraded

    @property
    def diagnostic(self) -> str:
        return self._store.diagnostic if self._store is not None else "storage_not_started"

    def require(self) -> SQLiteRuntimeStore:
        if self._store is None:
            raise RuntimeError("daemon storage is not started")
        return self._store

    async def start(self) -> None:
        if self._store is None:
            self._store = await SQLiteRuntimeStore.open(self._path)

    async def close(self) -> None:
        store, self._store = self._store, None
        if store is not None:
            await store.close()


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

    def mark_loaded(self, placement_id: str, loaded: bool) -> None:
        snapshot = self._snapshots[placement_id]
        self._snapshots[placement_id] = replace(snapshot, loaded=loaded)

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
        self._nodes = {item.id: item for item in config.nodes}
        self._backend_nodes = {item.id: item.node_id for item in config.backends}
        self._task: asyncio.Task[None] | None = None

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
        authorization = (
            asyncio.create_task(self._refresh_tailscale(), name="omlxcd-tailscale-probe")
            if self._tailscale is not None
            else None
        )
        await asyncio.gather(
            *(self._probe_backend(backend, authorization) for backend in self._config.backends),
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
                adapter = self._adapters[backend.id]
                capability = await adapter.discover()
                if capability.backend_id != backend.id:
                    raise ValueError("backend discovery identity mismatch")
                models = await adapter.list_models()
            self._apply(backend, capability, models, authorized=authorized, local=local)
        except asyncio.CancelledError:
            raise
        except Exception:
            self._fail_closed(backend.id)

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
        for snapshot in self._catalog.get():
            if snapshot.backend_id != backend.id:
                continue
            placement = self._placements[snapshot.placement_id]
            model = inventory.get(snapshot.backend_model_id)
            capabilities = (
                capability.capabilities
                if model is None
                else (model.capabilities or capability.capabilities)
            )
            ready = (
                fresh
                and capability.reachable
                and capability.compatible
                and capability.generation_ready
                and model is not None
                and model.loaded is True
            )
            self._catalog.update(
                snapshot.placement_id,
                fresh=fresh,
                available=ready,
                authorized=authorized,
                capabilities=frozenset(item.value for item in capabilities),
                context_limit=(
                    model.context_limit
                    if model is not None and model.context_limit is not None
                    else placement.context_limit
                ),
                memory_admitted=self._memory_admitted(placement),
                loaded=model is not None and model.loaded is True,
                available_concurrency=1 if ready else 0,
                local=local,
                security_allowed=authorized and local,
            )

    def _memory_admitted(self, placement: PlacementConfig) -> bool | None:
        if placement.memory_gb is None:
            return True
        available = self._nodes[self._backend_nodes[placement.backend_id]].memory_gb
        return None if available is None else placement.memory_gb <= available

    def _fail_closed(self, backend_id: str) -> None:
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
        reranker: Reranker | None,
    ) -> None:
        self._orchestrator = orchestrator
        self._model_ids = tuple(sorted(model_ids))
        self._reranker = reranker

    async def list_openai_models(self) -> tuple[str, ...]:
        return self._model_ids

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
        adapters: Mapping[str, BackendAdapter],
        catalog: SnapshotCatalog,
        planner: RoutePlanner,
        bus: EventBus,
        id_factory: Callable[[], str],
        now: Callable[[], datetime],
        loaded_config_identity: str,
        worker_timeout: float = 120.0,
    ) -> None:
        self._config = config
        self._storage = storage
        self._adapters = dict(adapters)
        self._catalog = catalog
        self._planner = planner
        self._bus = bus
        self._id_factory = id_factory
        self._now = now
        self._config_identity = loaded_config_identity
        self._worker_timeout = worker_timeout
        self._tasks: dict[str, asyncio.Task[None]] = {}

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
            adapter = self._adapters[placement.backend_id]
            operation = adapter.load_model if job.kind == "load" else adapter.unload_model
            async with asyncio.timeout(self._worker_timeout):
                result = await operation(
                    placement.backend_model_id, idempotency_key=job.idempotency_key
                )
            await self._finish(job, placement.placement_id, result)
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

    async def _finish(self, job: StoredJob, placement_id: str, result: LifecycleResult) -> None:
        succeeded = result.status in {OperationStatus.SUCCEEDED, OperationStatus.UNCHANGED}
        if succeeded:
            self._catalog.mark_loaded(placement_id, job.kind == "load")
        await self._storage.require().transition_job(
            job.id,
            JobState.SUCCEEDED if succeeded else JobState.FAILED,
            progress=1.0 if succeeded else 0.2,
            observed_at=self._now(),
            event_id=f"job-{job.id}-terminal-{job.attempt}",
            error_code=None
            if succeeded
            else (result.error.code.value if result.error else "failed"),
        )

    def _placement_for_model(self, model_id: str) -> PlacementSnapshot:
        candidates = [item for item in self._catalog.get() if item.model_id == model_id]
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
    catalog = SnapshotCatalog(snapshots or _configured_snapshots(config), now=clock)
    planner = RoutePlanner(default_policies())
    storage = StorageHandle(config)
    bus = EventBus(capacity=128)
    control = ProductionControlService(
        config=config,
        storage=storage,
        adapters=bindings,
        catalog=catalog,
        planner=planner,
        bus=bus,
        id_factory=id_factory or (lambda: uuid4().hex),
        now=clock,
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
        ),
        tuple(model.id for model in config.models),
        reranker,
    )
    events = ProductionEventService(storage, bus)
    probe = (
        CatalogProbe(
            config=config,
            adapters=bindings,
            catalog=catalog,
            tailscale=configured_tailscale,
            now=clock,
        )
        if snapshots is None
        else None
    )
    resources = ResourceComponent(bus, bindings, probe)
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
        capabilities = {"chat", "streaming"}
        if model.role == "embedding":
            capabilities.add("embedding")
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
                capabilities=frozenset(capabilities),
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


def is_loopback_url(value: str) -> bool:
    try:
        host = urlsplit(value).hostname
        return host is not None and ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _runtime_ready(snapshot: PlacementSnapshot) -> bool:
    return (
        snapshot.fresh
        and snapshot.available
        and snapshot.authorized
        and snapshot.security_allowed
        and snapshot.memory_admitted is not False
        and snapshot.available_concurrency != 0
    )


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
