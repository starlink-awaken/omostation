"""Focused AC-05 tests for the capability invocation gateway."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import pytest

from agora.capability_gateway import CapabilityInvocationGateway, serialize_receipt
from agora.mcp.bos_router import BOSRouter
from agora.mcp.resolver.services_types import BosService

URI = "bos://capability/test/invoke"
_NATIVE_CALLS: list[dict[str, Any]] = []


def _native_fixture(arguments: dict[str, Any]) -> dict[str, Any]:
    _NATIVE_CALLS.append(dict(arguments))
    return {"ok": True}


def _record(**overrides: Any) -> dict[str, Any]:
    record = {
        "id": f"bos-service:{URI}",
        "source": "agora.bos",
        "status": "active",
        "native_bos_uri": URI,
        "kind": "bos_service",
        "transport": "bos_native",
        "operation": "invoke",
    }
    record.update(overrides)
    return record


class FakeAdapter:
    kind = "native"

    def __init__(self, health: str = "healthy") -> None:
        self.health = health
        self.probe_calls: list[dict[str, Any]] = []
        self.invoke_calls: list[tuple[dict[str, Any], Any]] = []

    def probe(self, record: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        self.probe_calls.append({"record": record, "timeout": timeout})
        return {"status": self.health, "evidence": "provider output must not escape"}

    def invoke(self, record: dict[str, Any], payload: Any) -> dict[str, Any]:
        self.invoke_calls.append((record, payload))
        return {"status": "ok", "result": "provider output must not escape"}


def _router() -> BOSRouter:
    router = BOSRouter(admission_evaluator=lambda _request: {"status": "admitted"})
    assert router.register(
        URI,
        adapter="poc",
        config={"domain": "capability", "transport": "internal"},
    )
    return router


def _gateway(
    record: dict[str, Any] | None = None,
    *,
    adapter: FakeAdapter | None = None,
    admission: Any = None,
) -> tuple[CapabilityInvocationGateway, FakeAdapter]:
    native = adapter or FakeAdapter()
    gateway = CapabilityInvocationGateway(
        registry=[record or _record()],
        router=_router(),
        admission_evaluator=admission or (lambda _request: {"status": "admitted"}),
        adapter=native,
    )
    return gateway, native


def test_exact_record_mismatch_rejects_before_adapter_call() -> None:
    gateway, adapter = _gateway()

    receipt = gateway.invoke(_record(operation="wrong"), {"query": "x"})

    assert receipt["status"] == "rejected"
    assert receipt["error_code"] == "INVALID_RECORD"
    assert adapter.probe_calls == []
    assert adapter.invoke_calls == []


@pytest.mark.parametrize(
    ("registry", "candidate"),
    [
        ([_record()], _record(native_bos_uri="bos://capability/missing/invoke")),
        ([_record(), _record()], _record()),
        ([_record()], {"uri": URI, "source": "legacy"}),
    ],
)
def test_missing_duplicate_or_legacy_record_fails_closed(
    registry: list[dict[str, Any]], candidate: dict[str, Any]
) -> None:
    adapter = FakeAdapter()
    gateway = CapabilityInvocationGateway(
        registry=registry,
        router=_router(),
        admission_evaluator=lambda _request: {"status": "admitted"},
        adapter=adapter,
    )

    receipt = gateway.invoke(candidate, {"query": "x"})

    assert receipt["status"] == "rejected"
    assert receipt["error_code"] == "INVALID_RECORD"
    assert adapter.probe_calls == []
    assert adapter.invoke_calls == []


@pytest.mark.parametrize(
    ("admission_result", "error_code"),
    [
        ({"status": "rejected", "reasons": ["denied"]}, "ADMISSION_DENIED"),
        (
            {"status": "rejected", "reasons": ["provider_unavailable"]},
            "ADMISSION_REQUIRED",
        ),
    ],
)
def test_admission_failure_is_before_adapter_call(
    admission_result: dict[str, Any], error_code: str
) -> None:
    gateway, adapter = _gateway(admission=lambda _request: admission_result)

    receipt = gateway.invoke(_record(), {"query": "x"})

    assert receipt["status"] == "rejected"
    assert receipt["error_code"] == error_code
    assert adapter.probe_calls == []
    assert adapter.invoke_calls == []


@pytest.mark.parametrize("health", ["unknown", "unhealthy"])
def test_unknown_or_unhealthy_health_rejects_invoke(health: str) -> None:
    gateway, adapter = _gateway(adapter=FakeAdapter(health))

    receipt = gateway.invoke(_record(), {"query": "x"})

    assert receipt["status"] == "rejected"
    assert receipt["error_code"] in {"HEALTH_UNKNOWN", "HEALTH_UNHEALTHY"}
    assert len(adapter.probe_calls) == 1
    assert adapter.invoke_calls == []


def test_load_calls_readiness_but_not_business_invocation() -> None:
    gateway, adapter = _gateway()

    receipt = gateway.load(_record())

    assert receipt["status"] == "ready"
    assert receipt["invocation_attempted"] is False
    assert len(adapter.probe_calls) == 1
    assert adapter.invoke_calls == []


def test_explicit_invoke_selects_native_adapter_once() -> None:
    gateway, adapter = _gateway()

    receipt = gateway.invoke(_record(), {"query": "private"})

    assert receipt["status"] == "succeeded"
    assert receipt["adapter_kind"] == "native"
    assert receipt["invocation_attempted"] is True
    assert len(adapter.probe_calls) == 1
    assert len(adapter.invoke_calls) == 1
    assert receipt["operation"] == "invoke"


def test_default_adapter_executes_declared_internal_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agora.mcp.resolver import api

    service = BosService(
        uri=URI,
        domain="capability",
        package="test",
        action="invoke",
        transport="internal",
        module_path=__name__,
        func_name="_native_fixture",
    )
    monkeypatch.setattr(api, "POC_SERVICES", [service])
    monkeypatch.setattr(api, "_service_index", None)
    _NATIVE_CALLS.clear()
    gateway = CapabilityInvocationGateway(
        registry=[_record()],
        router=_router(),
        admission_evaluator=lambda _request: {"status": "admitted"},
    )

    receipt = gateway.invoke(_record(), {"query": "actual-native-call"})

    assert receipt["status"] == "succeeded"
    assert receipt["operation"] == "invoke"
    assert receipt["invocation_attempted"] is True
    assert _NATIVE_CALLS == [{"query": "actual-native-call"}]


def test_default_registry_projects_only_supported_internal_services(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agora.mcp.resolver import services

    internal = BosService(
        uri=URI,
        domain="capability",
        package="test",
        action="invoke",
        transport="internal",
    )
    unsupported = BosService(
        uri="bos://capability/test/stdio",
        domain="capability",
        package="test",
        action="stdio",
        transport="stdio",
        command=["false"],
    )
    monkeypatch.setattr(services, "POC_SERVICES", [internal, unsupported])

    gateway = CapabilityInvocationGateway(
        router=_router(),
        admission_evaluator=lambda _request: {"status": "admitted"},
        adapter=FakeAdapter(),
    )

    assert [record["id"] for record in gateway._registry] == [f"bos-service:{URI}"]


def test_default_route_resolution_preserves_mounted_lifecycle_gate() -> None:
    class GatedRouter:
        def __init__(self) -> None:
            self.resolve_calls = 0
            self.direct_calls = 0

        def resolve(self, _uri: str) -> None:
            self.resolve_calls += 1

        def resolve_with_capability(self, *_args: Any, **_kwargs: Any) -> None:
            self.direct_calls += 1
            raise AssertionError("mounted lifecycle gate was bypassed")

    router = GatedRouter()
    adapter = FakeAdapter()
    gateway = CapabilityInvocationGateway(
        registry=[_record()],
        router=router,
        admission_evaluator=lambda _request: {"status": "admitted"},
        adapter=adapter,
    )

    receipt = gateway.load(_record())

    assert receipt["status"] == "rejected"
    assert receipt["error_code"] == "ADAPTER_NOT_READY"
    assert router.resolve_calls == 1
    assert router.direct_calls == 0
    assert adapter.probe_calls == []


def test_injected_probe_is_bounded_by_gateway_timeout() -> None:
    class BlockingAdapter(FakeAdapter):
        def probe(self, record: dict[str, Any], *, timeout: float) -> dict[str, Any]:
            self.probe_calls.append({"record": record, "timeout": timeout})
            threading.Event().wait(0.2)
            return {"status": "healthy"}

    adapter = BlockingAdapter()
    gateway = CapabilityInvocationGateway(
        registry=[_record()],
        router=_router(),
        admission_evaluator=lambda _request: {"status": "admitted"},
        adapter=adapter,
        readiness_timeout=0.01,
    )

    started = time.monotonic()
    receipt = gateway.invoke(_record(), {"query": "x"})

    assert time.monotonic() - started < 0.15
    assert receipt["status"] == "rejected"
    assert receipt["error_code"] == "HEALTH_UNKNOWN"
    assert adapter.invoke_calls == []


@pytest.mark.parametrize(
    "record",
    [
        _record(kind="legacy_tool"),
        _record(transport="stdio"),
    ],
)
def test_unsupported_kind_or_transport_fails_closed(record: dict[str, Any]) -> None:
    gateway, adapter = _gateway()

    receipt = gateway.invoke(record, {"query": "x"})

    assert receipt["status"] == "rejected"
    assert receipt["error_code"] == "UNSUPPORTED_ADAPTER"
    assert adapter.probe_calls == []
    assert adapter.invoke_calls == []


def test_caller_command_override_fails_closed() -> None:
    gateway, adapter = _gateway()

    receipt = gateway.invoke(
        _record(), {"query": "x"}, command=["bash", "-lc", "danger"]
    )

    assert receipt["status"] == "rejected"
    assert receipt["error_code"] == "INVALID_RECORD"
    assert adapter.probe_calls == []
    assert adapter.invoke_calls == []


def test_receipt_serialization_is_privacy_safe() -> None:
    gateway, _adapter = _gateway()
    secret = "super-secret-input"

    receipt = gateway.invoke(
        _record(),
        {
            "secret": secret,
            "absolute_path": "/Users/xiamingxing/private.txt",
        },
    )
    encoded = json.dumps(serialize_receipt(receipt), sort_keys=True)

    assert secret not in encoded
    assert "provider output must not escape" not in encoded
    assert "/Users/xiamingxing" not in encoded
    assert receipt["input_digest"]
    assert receipt["result_digest"]
    assert receipt["admission_decision_digest"]
    assert receipt["health_evidence_digest"]
