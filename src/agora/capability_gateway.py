"""Narrow, fail-closed gateway for invoking canonical BOS capabilities.

The gateway is deliberately not an executor.  A caller supplies only an
exact record already present in the canonical BOS capability registry and a
business payload.  Registry-owned native transport details are resolved from
the BOS URI; commands, module paths, adapter targets, and argv are never
accepted from the caller.
"""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import inspect
import json
import queue
import re
import threading
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Protocol

from agora.admission import evaluate_admission
from agora.mcp.bos_router import BOSRouter, bos_router

CANONICAL_SOURCE = "agora.bos"
CANONICAL_KIND = "bos_service"
NATIVE_TRANSPORT = "bos_native"
_UNDERLYING_NATIVE_TRANSPORT = "internal"
RECEIPT_SCHEMA = "capability-invocation-receipt/v1"

_REQUIRED_RECORD_FIELDS = frozenset(
    {"id", "source", "status", "native_bos_uri", "kind", "transport", "operation"}
)
_OPTIONAL_RECORD_FIELDS = frozenset({"adapter", "description", "name"})
_CALLER_CONTROLLED_FIELDS = frozenset(
    {
        "adapter",
        "adapter_target",
        "argv",
        "command",
        "func_name",
        "http_url",
        "module_path",
        "target",
    }
)
_FORBIDDEN_RECORD_FIELDS = _CALLER_CONTROLLED_FIELDS - {"adapter"}
_OPERATION_PATTERN = re.compile(r"^[a-z][a-z0-9_/-]*$")
_UNSET = object()


class NativeTransportAdapter(Protocol):
    """The only adapter contract exposed by this tranche."""

    kind: str

    def probe(
        self, record: Mapping[str, Any], *, timeout: float
    ) -> Mapping[str, Any]: ...

    def invoke(self, record: Mapping[str, Any], payload: Any) -> Any: ...


class _DefaultNativeTransportAdapter:
    """Bounded readiness plus the existing in-process BOS resolver path."""

    kind = NATIVE_TRANSPORT

    def probe(self, record: Mapping[str, Any], *, timeout: float) -> Mapping[str, Any]:
        uri = str(record["native_bos_uri"])

        def resolve_handler() -> tuple[str, str]:
            from agora.mcp.resolver.api import get_service

            service = get_service(uri)
            if service is None or service.transport != _UNDERLYING_NATIVE_TRANSPORT:
                raise LookupError("native internal service unavailable")
            if not service.module_path or not service.func_name:
                raise LookupError("native handler declaration incomplete")
            module = importlib.import_module(service.module_path)
            handler = getattr(module, service.func_name)
            if not callable(handler):
                raise LookupError("native handler is not callable")
            return service.module_path, service.func_name

        result, reason = _bounded_call(resolve_handler, timeout)
        if reason == "timeout":
            return {"status": "unknown", "evidence": "readiness_timeout"}
        if reason is not None or result is None:
            return {"status": "unhealthy", "evidence": "native_handler_unavailable"}
        return {"status": "healthy", "evidence": "native_handler_resolved"}

    def invoke(self, record: Mapping[str, Any], payload: Any) -> Any:
        """Invoke through ``resolve_bos_uri``; no command or argv is built."""
        from agora.mcp.resolver.api import resolve_bos_uri

        result = resolve_bos_uri(
            str(record["native_bos_uri"]),
            arguments=payload if isinstance(payload, dict) else {"value": payload},
        )
        if inspect.isawaitable(result):
            return _run_awaitable(result)
        return result


# Public alias makes dependency injection and type-oriented discovery easy.
NativeAdapter = _DefaultNativeTransportAdapter


class CapabilityInvocationGateway:
    """Reconcile, admit, route, probe, and explicitly invoke one BOS record."""

    def __init__(
        self,
        *,
        registry: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None = None,
        admission_evaluator: Callable[[dict[str, Any]], Mapping[str, Any]]
        | None = None,
        router: BOSRouter | Any | None = None,
        adapter: NativeTransportAdapter | Any | None = None,
        capability_catalog: Any | None = None,
        admission_catalog: Any | None = None,
        readiness_timeout: float = 1.0,
    ) -> None:
        self._registry = list(_coerce_registry(registry))
        self._admission_evaluator = admission_evaluator or evaluate_admission
        self._router = router or bos_router
        self._adapter = adapter or _DefaultNativeTransportAdapter()
        self._capability_catalog = capability_catalog
        self._admission_catalog = admission_catalog
        self._readiness_timeout = max(0.001, float(readiness_timeout))
        self._registry_digest = _digest(self._registry)

    def load(
        self,
        record: Mapping[str, Any],
        *,
        selector: Mapping[str, Any] | None = None,
        **caller_options: Any,
    ) -> dict[str, Any]:
        """Check admission, route, and bounded readiness without invoking."""
        payload = _UNSET
        prepared = self._prepare(record, selector, caller_options, payload)
        if "record" not in prepared:
            return prepared
        return self._receipt(
            operation="load",
            record=prepared["record"],
            selector=selector,
            admission=prepared["admission"],
            health=prepared["health"],
            adapter=prepared["adapter"],
            invocation_attempted=False,
            input_value=None,
            result_value=None,
            status="ready",
        )

    def invoke(
        self,
        record: Mapping[str, Any],
        payload: Any,
        *,
        selector: Mapping[str, Any] | None = None,
        **caller_options: Any,
    ) -> dict[str, Any]:
        """Invoke exactly one declared native operation after readiness."""
        prepared = self._prepare(record, selector, caller_options, payload)
        if "record" not in prepared:
            prepared["input_digest"] = _digest(payload)
            return prepared

        safe_record = prepared["record"]
        try:
            result = self._adapter.invoke(safe_record, payload)
            if isinstance(result, Mapping) and str(
                result.get("status", "")
            ).lower() in {
                "error",
                "failed",
                "failure",
            }:
                return self._receipt(
                    operation="invoke",
                    record=safe_record,
                    selector=selector,
                    admission=prepared["admission"],
                    health=prepared["health"],
                    adapter=prepared["adapter"],
                    invocation_attempted=True,
                    input_value=payload,
                    result_value=result,
                    status="failed",
                    error_code="INVOCATION_FAILURE",
                    error_detail=result.get("error", "adapter returned failure"),
                    exit_code=_exit_code(result),
                )
            return self._receipt(
                operation="invoke",
                record=safe_record,
                selector=selector,
                admission=prepared["admission"],
                health=prepared["health"],
                adapter=prepared["adapter"],
                invocation_attempted=True,
                input_value=payload,
                result_value=result,
                status="succeeded",
                exit_code=_exit_code(result),
            )
        except Exception as exc:  # noqa: BLE001 - gateway must fail closed
            return self._receipt(
                operation="invoke",
                record=safe_record,
                selector=selector,
                admission=prepared["admission"],
                health=prepared["health"],
                adapter=prepared["adapter"],
                invocation_attempted=True,
                input_value=payload,
                result_value=None,
                status="failed",
                error_code="INVOCATION_FAILURE",
                error_detail=type(exc).__name__,
            )

    def _prepare(
        self,
        record: Mapping[str, Any],
        selector: Mapping[str, Any] | None,
        caller_options: Mapping[str, Any],
        payload: Any,
    ) -> dict[str, Any]:
        if caller_options or (
            isinstance(payload, Mapping)
            and _CALLER_CONTROLLED_FIELDS.intersection(payload)
        ):
            return self._error(
                "load" if payload is _UNSET else "invoke",
                record,
                selector,
                "INVALID_RECORD",
                "caller_execution_metadata_forbidden",
            )

        valid, record_error = _validate_record(record)
        if valid is None:
            return self._error(
                "load" if payload is _UNSET else "invoke",
                record,
                selector,
                record_error or "INVALID_RECORD",
                "record_validation_failed",
            )

        registry_result = self._reconcile(valid)
        if registry_result is not None:
            return self._error(
                "load" if payload is _UNSET else "invoke",
                valid,
                selector,
                "INVALID_RECORD",
                registry_result,
            )

        admission = self._admit(valid)
        if admission["status"] != "admitted":
            reason = str(admission.get("reason", "")).lower()
            code = (
                "ADMISSION_REQUIRED"
                if "provider_unavailable" in reason
                or "provider unavailable" in reason
                or "required" in reason
                or "evaluator_error" in reason
                else "ADMISSION_DENIED"
            )
            return self._error(
                "load" if payload is _UNSET else "invoke",
                valid,
                selector,
                code,
                "admission_rejected",
                admission=admission,
            )

        route = self._resolve_route(valid["native_bos_uri"])
        if route is None:
            return self._error(
                "load" if payload is _UNSET else "invoke",
                valid,
                selector,
                "ADAPTER_NOT_READY",
                "route_unavailable",
                admission=admission,
            )
        if str(route.get("prefix", "")).rstrip("/") != valid["native_bos_uri"]:
            return self._error(
                "load" if payload is _UNSET else "invoke",
                valid,
                selector,
                "INVALID_RECORD",
                "route_record_mismatch",
                admission=admission,
            )
        route_adapter = str(route.get("adapter", ""))
        route_transport = str(route.get("config", {}).get("transport", ""))
        if route_adapter not in {"poc", "native", "internal"} or (
            route_transport
            and route_transport not in {NATIVE_TRANSPORT, _UNDERLYING_NATIVE_TRANSPORT}
        ):
            return self._error(
                "load" if payload is _UNSET else "invoke",
                valid,
                selector,
                "UNSUPPORTED_ADAPTER",
                "route_adapter_unsupported",
                admission=admission,
            )

        adapter_kind = str(getattr(self._adapter, "kind", "native"))
        if adapter_kind not in {"native", NATIVE_TRANSPORT} or not callable(
            getattr(self._adapter, "probe", None)
        ):
            return self._error(
                "load" if payload is _UNSET else "invoke",
                valid,
                selector,
                "UNSUPPORTED_ADAPTER",
                "native_adapter_unavailable",
                admission=admission,
            )
        health_raw, probe_error = _bounded_call(
            lambda: self._adapter.probe(dict(valid), timeout=self._readiness_timeout),
            self._readiness_timeout,
        )
        if probe_error is not None:
            health_raw = {
                "status": "unknown",
                "evidence": "probe_timeout"
                if probe_error == "timeout"
                else "probe_failed",
            }
        health = _health_projection(health_raw)
        if health["status"] != "healthy":
            code = (
                "HEALTH_UNKNOWN"
                if health["status"] == "unknown"
                else "HEALTH_UNHEALTHY"
            )
            return self._error(
                "load" if payload is _UNSET else "invoke",
                valid,
                selector,
                code,
                "readiness_not_healthy",
                admission=admission,
                health=health,
                adapter={"kind": adapter_kind, "target": valid["native_bos_uri"]},
            )
        return {
            "record": valid,
            "route": route,
            "admission": admission,
            "health": health,
            "adapter": {"kind": adapter_kind, "target": valid["native_bos_uri"]},
        }

    def _reconcile(self, record: dict[str, Any]) -> str | None:
        records = []
        for candidate in self._registry:
            valid, error = _validate_record(candidate)
            if valid is None:
                return error or "invalid_registry_record"
            records.append(valid)
        matching = [
            candidate for candidate in records if candidate["id"] == record["id"]
        ]
        if len(matching) != 1:
            return "missing_or_duplicate_canonical_record"
        if matching[0] != record:
            return "canonical_record_mismatch"
        return None

    def _admit(self, record: Mapping[str, Any]) -> dict[str, Any]:
        request = {
            "capability": record["native_bos_uri"],
            "operation": record["operation"],
            "role": "capability_invocation",
            "source": CANONICAL_SOURCE,
            "adapter": NATIVE_TRANSPORT,
        }
        try:
            result = self._admission_evaluator(request)
        except Exception:
            return {"status": "rejected", "reason": "admission_evaluator_error"}
        if not isinstance(result, Mapping) or "status" not in result:
            return {"status": "rejected", "reason": "invalid_admission_result"}
        result_dict = dict(result)
        return {
            "status": str(result_dict.get("status", "rejected")),
            "reason": ";".join(str(item) for item in result_dict.get("reasons", [])),
            "decision": result_dict,
        }

    def _resolve_route(self, uri: str) -> Mapping[str, Any] | None:
        try:
            if self._capability_catalog is None and self._admission_catalog is None:
                # The public resolver preserves catalogs already mounted by
                # ``enable_capability_gating`` on the production singleton.
                return self._router.resolve(uri)
            return self._router.resolve_with_capability(
                uri,
                capability_catalog=self._capability_catalog,
                admission_catalog=self._admission_catalog,
            )
        except TypeError:
            # Keep small fakes useful without weakening the production API.
            return self._router.resolve_with_capability(uri)
        except Exception:
            return None

    def _error(
        self,
        operation: str,
        record: Any,
        selector: Mapping[str, Any] | None,
        error_code: str,
        detail: str,
        *,
        admission: Mapping[str, Any] | None = None,
        health: Mapping[str, Any] | None = None,
        adapter: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._receipt(
            operation=operation,
            record=record,
            selector=selector,
            admission=admission or {},
            health=health or {},
            adapter=adapter
            or {"kind": NATIVE_TRANSPORT, "target": _record_uri(record)},
            invocation_attempted=False,
            input_value=None,
            result_value=None,
            status="rejected",
            error_code=error_code,
            error_detail=detail,
        )

    def _receipt(
        self,
        *,
        operation: str,
        record: Any,
        selector: Mapping[str, Any] | None,
        admission: Mapping[str, Any],
        health: Mapping[str, Any],
        adapter: Mapping[str, Any],
        invocation_attempted: bool,
        input_value: Any,
        result_value: Any,
        status: str,
        error_code: str = "",
        error_detail: Any = "",
        exit_code: int | None = None,
    ) -> dict[str, Any]:
        receipt = {
            "schema": RECEIPT_SCHEMA,
            "operation": operation,
            "status": status,
            "capability_id": _record_id(record),
            "registry_digest": self._registry_digest,
            "record_digest": _digest(record),
            "selector_digest": _digest(selector),
            "admission_status": str(admission.get("status", "not_evaluated")),
            "admission_decision_digest": _digest(admission.get("decision", admission)),
            "health_status": str(health.get("status", "not_evaluated")),
            "health_evidence_digest": _digest(health.get("evidence", health)),
            "adapter_kind": str(adapter.get("kind", "native")),
            "adapter_target_digest": _digest(adapter.get("target", "")),
            "invocation_attempted": invocation_attempted,
            "input_digest": _digest(input_value),
            "result_digest": _digest(result_value),
            "exit_code": exit_code,
            "error_code": error_code,
            "error_detail_digest": _digest(error_detail),
        }
        return serialize_receipt(receipt)


def serialize_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Serialize only the fixed privacy-safe receipt envelope fields."""
    return {key: receipt.get(key) for key in _RECEIPT_FIELDS}


_RECEIPT_FIELDS = (
    "schema",
    "operation",
    "status",
    "capability_id",
    "registry_digest",
    "record_digest",
    "selector_digest",
    "admission_status",
    "admission_decision_digest",
    "health_status",
    "health_evidence_digest",
    "adapter_kind",
    "adapter_target_digest",
    "invocation_attempted",
    "input_digest",
    "result_digest",
    "exit_code",
    "error_code",
    "error_detail_digest",
)


def _coerce_registry(
    registry: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None,
) -> Iterable[Mapping[str, Any]]:
    if registry is None:
        from agora.mcp.resolver.services import POC_SERVICES

        return [
            {
                "id": f"bos-service:{service.uri}",
                "source": CANONICAL_SOURCE,
                "status": "active",
                "native_bos_uri": service.uri,
                "kind": CANONICAL_KIND,
                "transport": NATIVE_TRANSPORT,
                "operation": service.action or "invoke",
                "adapter": {"kind": NATIVE_TRANSPORT, "target": service.uri},
                "description": service.description,
            }
            for service in POC_SERVICES
            if service.uri and service.transport == _UNDERLYING_NATIVE_TRANSPORT
        ]
    if isinstance(registry, Mapping):
        if isinstance(registry.get("records"), list):
            return registry["records"]
        if "id" in registry:
            return [registry]
        return list(registry.values())
    return registry


def _validate_record(record: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(record, Mapping):
        return None, "INVALID_RECORD"
    if _FORBIDDEN_RECORD_FIELDS.intersection(record):
        return None, "INVALID_RECORD"
    missing = _REQUIRED_RECORD_FIELDS - set(record)
    if missing:
        return None, "INVALID_RECORD"
    if (
        record.get("kind") != CANONICAL_KIND
        or record.get("transport") != NATIVE_TRANSPORT
    ):
        return None, "UNSUPPORTED_ADAPTER"
    uri = record.get("native_bos_uri")
    record_id = record.get("id")
    if (
        not isinstance(uri, str)
        or not uri.startswith("bos://")
        or not isinstance(record_id, str)
        or record_id != f"bos-service:{uri}"
        or record.get("source") != CANONICAL_SOURCE
        or record.get("status") != "active"
        or not isinstance(record.get("operation"), str)
        or not _OPERATION_PATTERN.fullmatch(record["operation"])
    ):
        return None, "INVALID_RECORD"
    unknown = set(record) - _REQUIRED_RECORD_FIELDS - _OPTIONAL_RECORD_FIELDS
    if unknown:
        return None, "INVALID_RECORD"
    adapter = record.get("adapter")
    if adapter is not None and (
        not isinstance(adapter, Mapping)
        or adapter.get("kind") != NATIVE_TRANSPORT
        or adapter.get("target") != uri
        or set(adapter) != {"kind", "target"}
    ):
        return None, "UNSUPPORTED_ADAPTER"
    return dict(record), None


def _health_projection(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {"status": "unknown", "evidence": "invalid_probe"}
    raw_status = str(value.get("status", "")).strip().lower()
    if raw_status in {"healthy", "ok"}:
        status = "healthy"
    elif raw_status in {"unhealthy", "failed", "error", "down"}:
        status = "unhealthy"
    else:
        status = "unknown"
    return {"status": status, "evidence": str(value.get("evidence", ""))}


def _bounded_call(
    function: Callable[[], Any], timeout: float
) -> tuple[Any, str | None]:
    result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def run() -> None:
        try:
            result_queue.put(("result", function()))
        except Exception as exc:  # noqa: BLE001 - probe result is fail-closed
            result_queue.put(("error", exc))

    threading.Thread(target=run, daemon=True).start()
    try:
        kind, value = result_queue.get(timeout=timeout)
    except queue.Empty:
        return None, "timeout"
    if kind == "error":
        return None, type(value).__name__
    return value, None


def _run_awaitable(value: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(value)
    result, reason = _bounded_call(lambda: asyncio.run(value), 10.0)
    if reason is not None:
        raise TimeoutError("native invocation timeout")
    return result


def _exit_code(value: Any) -> int | None:
    if isinstance(value, Mapping) and isinstance(value.get("exit_code"), int):
        return value["exit_code"]
    return None


def _record_id(record: Any) -> str:
    return str(record.get("id", "")) if isinstance(record, Mapping) else ""


def _record_uri(record: Any) -> str:
    return str(record.get("native_bos_uri", "")) if isinstance(record, Mapping) else ""


def _digest(value: Any) -> str:
    canonical = json.dumps(_digestable(value), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _digestable(value: Any) -> Any:
    if value is _UNSET:
        return "<unset>"
    if isinstance(value, Mapping):
        return {
            str(key): _digestable(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_digestable(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return f"<{type(value).__module__}.{type(value).__qualname__}>"


__all__ = [
    "CANONICAL_KIND",
    "CANONICAL_SOURCE",
    "NATIVE_TRANSPORT",
    "RECEIPT_SCHEMA",
    "CapabilityInvocationGateway",
    "NativeAdapter",
    "NativeTransportAdapter",
    "serialize_receipt",
]
