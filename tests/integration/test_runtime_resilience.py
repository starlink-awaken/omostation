from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from omlxc.adapters.process import ProcessOutput
from omlxc.adapters.tailscale import (
    TailscaleAdapter,
    TailscaleErrorCode,
    TailscaleFailure,
    TailscaleNodePolicy,
)
from omlxc.autonomy import (
    AutonomyStatus,
    MemoryAdmissionPolicy,
    MemorySnapshot,
    PlacementTarget,
    ReconciliationEngine,
)
from omlxc.domain.protocols import (
    AdapterError,
    AdapterErrorCode,
    LifecycleResult,
    OperationStatus,
)
from omlxc.storage import MetricRecord, SQLiteRuntimeStore, StorageDegradedError


@pytest.mark.asyncio
async def test_corrupt_database_is_quarantined_without_creating_fake_primary(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.db"
    database.write_bytes(b"not a sqlite database; api_key=must-not-appear")
    store = await SQLiteRuntimeStore.open(
        database, quarantine_suffix_factory=lambda: "deterministic"
    )
    assert store.degraded
    assert not database.exists()
    quarantine = tmp_path / "state.db.corrupt-deterministic"
    assert quarantine.exists()
    assert quarantine.stat().st_mode & 0o077 == 0
    assert "api_key" not in store.diagnostic
    with pytest.raises(StorageDegradedError):
        store.accept_metric(MetricRecord("req", datetime(2026, 8, 11, tzinfo=UTC), 1.0, True))
    await store.close()


@pytest.mark.asyncio
async def test_writer_close_restart_flushes_accepted_metrics(tmp_path: Path) -> None:
    database = tmp_path / "state.db"
    store = await SQLiteRuntimeStore.open(database)
    for index in range(20):
        assert store.accept_metric(
            MetricRecord(f"req-{index}", datetime(2026, 8, 11, tzinfo=UTC), float(index), True)
        )
    assert await store.close() == 20
    reopened = await SQLiteRuntimeStore.open(database)
    assert await reopened.metric_count() == 20
    await reopened.close()


def _target(identifier: str, node: str) -> PlacementTarget:
    return PlacementTarget(
        id=identifier,
        node_id=node,
        model_id=f"model-{identifier}",
        resident=True,
        memory_gb=1.0,
        idle_unload_seconds=60.0,
        last_used_monotonic=90.0,
        rollback_reference=f"rollback:{identifier}",
    )


class IsolatedOperator:
    def __init__(self) -> None:
        self.loaded: set[str] = set()

    async def fresh_for_write(self, target: PlacementTarget) -> bool:
        return target.node_id != "offline"

    async def is_loaded(self, target: PlacementTarget) -> bool:
        if target.node_id == "broken":
            raise TimeoutError("simulated typed offline node")
        return target.id in self.loaded

    async def load(self, target: PlacementTarget, *, idempotency_key: str) -> LifecycleResult:
        del idempotency_key
        self.loaded.add(target.id)
        return LifecycleResult(
            model_id=target.model_id, status=OperationStatus.SUCCEEDED, changed=True
        )

    async def unload(self, target: PlacementTarget, *, idempotency_key: str) -> LifecycleResult:
        del idempotency_key
        return LifecycleResult(
            model_id=target.model_id, status=OperationStatus.UNCHANGED, changed=False
        )


@pytest.mark.asyncio
async def test_offline_placement_failure_isolated_from_other_reconciliation() -> None:
    operator = IsolatedOperator()
    engine = ReconciliationEngine(
        operator,
        memory_policy=MemoryAdmissionPolicy(stale_seconds=10.0, safety_margin_gb=1.0),
        global_limit=2,
        per_node_limit=1,
    )
    results = await engine.reconcile_many(
        (_target("bad", "broken"), _target("good", "healthy")),
        MemorySnapshot(16.0, 8.0, 100.0),
        now_monotonic=100.0,
    )
    assert results["bad"].status is AutonomyStatus.FAILED
    assert results["good"].status is AutonomyStatus.SUCCEEDED


class PartialOperator(IsolatedOperator):
    async def load(self, target: PlacementTarget, *, idempotency_key: str) -> LifecycleResult:
        del idempotency_key
        self.loaded.add(target.id)
        return LifecycleResult(
            model_id=target.model_id,
            status=OperationStatus.FAILED,
            changed=False,
            error=AdapterError(
                code=AdapterErrorCode.PARTIAL_FAILURE,
                message="sanitized partial effect",
            ),
        )


@pytest.mark.asyncio
async def test_adapter_partial_effect_returns_executable_rollback_reference() -> None:
    engine = ReconciliationEngine(
        PartialOperator(),
        memory_policy=MemoryAdmissionPolicy(stale_seconds=10.0, safety_margin_gb=1.0),
        global_limit=1,
        per_node_limit=1,
    )
    result = await engine.reconcile(
        _target("partial", "healthy"),
        MemorySnapshot(16.0, 8.0, 100.0),
        now_monotonic=100.0,
    )
    assert result.status is AutonomyStatus.PARTIAL
    assert result.rollback_reference == "rollback:partial"


def _trusted_executable(tmp_path: Path) -> Path:
    directory = tmp_path / "trusted"
    directory.mkdir(mode=0o700)
    executable = directory / "tailscale-fixture"
    executable.write_text("never executed\n", encoding="utf-8")
    executable.chmod(0o700)
    return executable


def _conflicting_policy(node_id: str) -> TailscaleNodePolicy:
    return TailscaleNodePolicy(
        node_id=node_id,
        expected_peer_id="peeridFAKE000000000000000000000001",
        expected_public_key="nodekey:FAKEPEER000000000000000000000001",
        magic_dns_name=f"{node_id}.example.test",
        allowed_ips=frozenset({"100.64.0.10"}),
        allowed_http_ports=frozenset({1234}),
        allowed_ssh_users=frozenset({"operator"}),
    )


@pytest.mark.asyncio
async def test_policy_conflict_refresh_marks_http_and_ssh_authorization_typed_stale(
    tmp_path: Path,
) -> None:
    async def runner(argv: tuple[str, ...], timeout: float) -> ProcessOutput:
        del argv, timeout
        raise AssertionError("conflicting policy must fail before process execution")

    adapter = TailscaleAdapter(
        policies=(_conflicting_policy("node-a"), _conflicting_policy("node-b")),
        tailscale_executable=_trusted_executable(tmp_path),
        process_runner=runner,
    )
    with pytest.raises(TailscaleFailure) as refresh:
        await adapter.snapshot()
    assert refresh.value.code is TailscaleErrorCode.IDENTITY_CONFLICT
    for authorize in (
        lambda: adapter.authorize_http("node-a", "http://100.64.0.10:1234"),
        lambda: adapter.authorize_ssh("node-a", "operator@100.64.0.10"),
    ):
        with pytest.raises(TailscaleFailure) as stale:
            authorize()
        assert stale.value.code is TailscaleErrorCode.STALE
