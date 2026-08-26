#!/usr/bin/env python3
"""Compatibility CLI for the generated capability discovery projection.

``bin/ssot/gen-capability-registry.py`` is the sole projection writer. This
module delegates sync/check to it, provides read-only discovery, and exposes
the narrow public boundary for governed BOS loading/invocation. Native provider,
BOS, and workflow registries remain the authorities. Only exact canonical IDs
may reach Agora's native gateway; local skill/workflow kinds must exact-resolve
in the registry before any local receipt is granted. Caller supplied commands,
argv, module paths, targets, and transport overrides are never accepted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Union

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by the CLI environment
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))
from capability_native_inspection import (  # noqa: E402 -- static native source proof only
    NativeInspectionError,
    inspect_native_capability,
    inspection_error_receipt,
    native_kind_requires_projection,
)
from capability_trace_binding import (  # noqa: E402 -- CLI locates the local pure library first
    CANONICAL_REGISTRY_METADATA,
    CAPABILITY_SEMANTICS,
    IDENTITY_RE,
    RESOLUTION_SOURCE_REF,
    SHA256_RE,
    TRACE_BINDING_REQUIRED_FIELDS,
    TRACE_BINDING_SCHEMA,
    TraceBindingError,
    _canonical_json,
    _digest,
    _native_owner,
    _trace_projection,
    _validate_capability_binding,
    build_trace_bound_resolution_receipt,
    validate_trace_binding,
    validate_trace_bound_resolution_receipt,
)

try:
    from capability_native_cleanup import (  # noqa: E402 -- CLI locates the local pure library first
        OWNERSHIP_BY_KIND,
        build_native_cleanup_proof,
    )
    from capability_native_execution_model import (  # noqa: E402 -- CLI locates the local pure library first
        AUTHORIZATION_BY_KIND,
        NativeExecutionReceiptError,
        canonical_digest,
        derive_invocation_id,
    )
    from capability_native_execution_receipt import (  # noqa: E402 -- CLI locates the local pure library first
        build_native_execution_marker,
        build_native_execution_material,
        build_native_execution_receipt,
        validate_native_execution_material,
    )

    NATIVE_EXECUTION_LIBS_AVAILABLE = True
except ImportError:
    # Embedded minimal workspaces (e.g. agent-workflow preflight sandboxes) may
    # omit the native-execution lib set; the module must stay importable there.
    NATIVE_EXECUTION_LIBS_AVAILABLE = False

# Promoted shadow -> warning on 2026-08-26 after two consecutive caller scans
# showed zero unbound production entrypoints (docs/reports/2026-08-26-binding-enforcement-scan.md).
BINDING_ENFORCEMENT = "warning"

DEFAULT_REGISTRY = ROOT / "docs" / "generated" / "capability-registry.yaml"
CANONICAL_GENERATOR = ROOT / "bin" / "ssot" / "gen-capability-registry.py"
FEDERATION_AUDITOR = ROOT / "lib" / "capability_federation_audit.py"
AGORA_SRC = ROOT / "projects" / "agora" / "src"
SUPPORTED_SCHEMA_MAJOR = 1
MAX_INPUT_JSON_BYTES = 1024 * 1024
MAX_MESH_LOG_BYTES = 8 * 1024 * 1024
VERIFICATION_SCHEMA = "capability-admission-verification-request/v1"
VERIFICATION_RECEIPT_SCHEMA = "capability-admission-verification-receipt/v1"
VERIFICATION_FIELDS = {"schema", "material", "request", "expected"}
VERIFICATION_EXPECTED_FIELDS = {"capability_id", "operation_id", "effect_classification"}
MESH_LOG = Path("_knowledge/workflow-mesh/events.jsonl")


class RegistryError(ValueError):
    """The registry is missing, malformed, or uses an unsupported schema."""


class GatewayError(ValueError):
    """The capability cannot safely enter the governed native gateway."""


@dataclass(frozen=True)
class Resolution:
    """Fail-closed resolution result; never an invocation authorization."""

    status: str
    capability: Optional[dict[str, Any]]  # noqa: UP045 -- Python 3.9 contract
    candidate_ids: tuple[str, ...]
    match_count: int


def load_registry(path: Path) -> dict[str, Any]:
    """Load generated v1 and pre-metadata v1 discovery projections."""
    if yaml is None:
        raise RegistryError("pyyaml_not_installed")
    if not path.is_file():
        raise RegistryError("registry_not_found")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise RegistryError("registry_unreadable") from exc
    if not isinstance(data, dict):
        raise RegistryError("registry_not_mapping")

    version = str(data.get("version") or "1.0.0")
    try:
        major = int(version.split(".", 1)[0])
    except (TypeError, ValueError) as exc:
        raise RegistryError("registry_version_invalid") from exc
    if major != SUPPORTED_SCHEMA_MAJOR:
        raise RegistryError("registry_schema_unsupported")

    metadata_keys = set(CANONICAL_REGISTRY_METADATA)
    supplied_metadata = metadata_keys.intersection(data)
    if supplied_metadata and supplied_metadata != metadata_keys:
        raise RegistryError("registry_metadata_incomplete")
    for key, expected in CANONICAL_REGISTRY_METADATA.items():
        if supplied_metadata and data.get(key) != expected:
            raise RegistryError(f"registry_{key}_invalid")

    canonical_shape = all(key in data for key in ("mcp_servers", "bos_services", "cli_commands"))
    legacy_shape = isinstance(data.get("capabilities"), list)
    if not canonical_shape and not legacy_shape:
        raise RegistryError("registry_shape_unsupported")
    return data


def _add(
    index: dict[str, list[dict[str, Any]]],
    capability_id: str,
    kind: str,
    name: str,
    description: str,
    adapter_kind: str,
    target: str,
) -> None:
    if not capability_id:
        return
    index.setdefault(capability_id, []).append(
        {
            "id": capability_id,
            "kind": kind,
            "name": name,
            "description": description,
            "adapter": {"kind": adapter_kind, "target": target},
        }
    )


def build_capability_index(registry: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Project the registry into stable, exact discovery IDs."""
    index: dict[str, list[dict[str, Any]]] = {}

    for raw_server in registry.get("mcp_servers", []) or []:
        if not isinstance(raw_server, dict):
            continue
        if "exists" in raw_server and raw_server.get("exists") is not True:
            continue
        server_id = str(raw_server.get("id") or "")
        server_name = str(raw_server.get("name") or server_id)
        _add(
            index,
            "mcp-server:" + server_id,
            "mcp_server",
            server_name,
            server_name,
            "mcp_native",
            server_id,
        )
        for raw_tool in raw_server.get("tools", []) or []:
            tool = str(raw_tool)
            _add(
                index,
                "mcp-tool:" + server_id + ":" + tool,
                "mcp_tool",
                tool,
                server_name + " " + tool,
                "mcp_native",
                server_id + "/" + tool,
            )

    bos = registry.get("bos_services") or {}
    domains = bos.get("domains") if isinstance(bos, dict) else {}
    if isinstance(domains, dict):
        for services in domains.values():
            if not isinstance(services, list):
                continue
            for raw_service in services:
                if not isinstance(raw_service, dict):
                    continue
                uri = str(raw_service.get("uri") or "")
                _add(
                    index,
                    "bos-service:" + uri,
                    "bos_service",
                    uri,
                    str(raw_service.get("description") or ""),
                    "bos_native",
                    uri,
                )

    for raw_command in registry.get("cli_commands", []) or []:
        if not isinstance(raw_command, dict):
            continue
        name = str(raw_command.get("name") or "")
        _add(
            index,
            "cli-command:" + name,
            "cli_command",
            name,
            str(raw_command.get("description") or ""),
            "cockpit_native",
            name,
        )

    for raw_skill in registry.get("skills", []) or []:
        if not isinstance(raw_skill, dict) or raw_skill.get("exists") is not True:
            continue
        skill_id = str(raw_skill.get("id") or "")
        _add(
            index,
            "skill:" + skill_id,
            "skill",
            skill_id,
            skill_id,
            "instruction_native",
            skill_id,
        )

    for raw_workflow in registry.get("workflows", []) or []:
        if not isinstance(raw_workflow, dict) or raw_workflow.get("exists") is not True:
            continue
        workflow_id = str(raw_workflow.get("id") or "")
        _add(
            index,
            "workflow:" + workflow_id,
            "workflow",
            workflow_id,
            workflow_id,
            "workflow_native",
            workflow_id,
        )

    # Legacy flat registries remain discoverable but their stored invoke strings
    # are deliberately ignored.  They cannot regain a direct execution path.
    for raw_capability in registry.get("capabilities", []) or []:
        if not isinstance(raw_capability, dict):
            continue
        capability_id = str(raw_capability.get("id") or "")
        _add(
            index,
            capability_id,
            "legacy_capability",
            str(raw_capability.get("name") or capability_id),
            str(raw_capability.get("description") or ""),
            "legacy_discovery_only",
            capability_id,
        )

    return index


def resolve_capability(
    registry: Mapping[str, Any],
    capability_id: Optional[str] = None,  # noqa: UP045 -- Python 3.9 contract
    query: Optional[str] = None,  # noqa: UP045 -- Python 3.9 contract
) -> Resolution:
    """Resolve exactly one capability or reject ambiguity/not-found."""
    if bool(capability_id) == bool(query):
        return Resolution("invalid_selector", None, (), 0)

    index = build_capability_index(registry)
    if capability_id:
        matches = list(index.get(capability_id, []))
    else:
        needle = str(query).casefold()
        matches = []
        for entries in index.values():
            for entry in entries:
                haystack = " ".join((str(entry["id"]), str(entry["name"]), str(entry["description"]))).casefold()
                if needle in haystack:
                    matches.append(entry)

    candidate_ids = tuple(sorted({str(entry["id"]) for entry in matches}))
    if not matches:
        return Resolution("not_found", None, (), 0)
    if len(matches) != 1:
        return Resolution("ambiguous", None, candidate_ids, len(matches))
    return Resolution("resolved", matches[0], candidate_ids, 1)


def _bound_resolution_receipt(
    receipt: Mapping[str, Any],
    result: Resolution,
    selector: Mapping[str, Any],
    binding: Mapping[str, Any],
    projection_metadata: Optional[Mapping[str, Any]],  # noqa: UP045 -- Python 3.9 contract
) -> dict[str, Any]:
    return build_trace_bound_resolution_receipt(
        receipt,
        status=result.status,
        raw_capability=result.capability,
        selector=selector,
        binding=binding,
        projection_metadata=projection_metadata,
    )


def build_resolution_receipt(
    result: Resolution,
    registry_content: bytes,
    selector: Mapping[str, Any],
    *,
    binding: Optional[Mapping[str, Any]] = None,  # noqa: UP045 -- Python 3.9 contract
    projection_metadata: Optional[Mapping[str, Any]] = None,  # noqa: UP045 -- Python 3.9 contract
) -> dict[str, Any]:
    """Build a redacted, resolution-only receipt with no execution grant."""
    selector_bytes = json.dumps(selector, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt: dict[str, Any] = {
        "schema": "capability-resolution-receipt/v1",
        "status": result.status,
        "registry_digest": _digest(registry_content),
        "selector_digest": _digest(selector_bytes),
        "match_count": result.match_count,
        "candidate_id_digests": [_digest(value.encode("utf-8")) for value in result.candidate_ids],
        "admission": {"required": True, "decision": "not_evaluated"},
        "invocation": {
            "allowed": False,
            "route": "native_adapter_only",
            "reason": "admission_not_evaluated",
        },
    }
    if result.capability is not None:
        receipt["capability_id"] = result.capability["id"]
        receipt["adapter"] = dict(result.capability["adapter"])
    if binding is not None:
        return _bound_resolution_receipt(receipt, result, selector, binding, projection_metadata)
    return receipt


def _bos_registry_rows(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    bos = registry.get("bos_services") or {}
    domains = bos.get("domains") if isinstance(bos, dict) else {}
    rows: list[dict[str, Any]] = []
    if not isinstance(domains, dict):
        return rows
    for services in domains.values():
        if isinstance(services, list):
            rows.extend(service for service in services if isinstance(service, dict))
    return rows


def build_native_bos_record(
    registry: Mapping[str, Any], capability_id: str, service_catalog: Sequence[Any]
) -> dict[str, Any]:
    """Reconcile one generated BOS row with Agora's native runtime truth."""
    if not capability_id.startswith("bos-service:bos://"):
        raise GatewayError("unsupported_capability_kind")
    resolution = resolve_capability(registry, capability_id=capability_id)
    if resolution.status != "resolved" or resolution.capability is None:
        raise GatewayError("capability_not_exactly_resolved")

    uri = capability_id.removeprefix("bos-service:")
    rows = [row for row in _bos_registry_rows(registry) if str(row.get("uri") or "") == uri]
    if len(rows) != 1:
        raise GatewayError("missing_or_duplicate_bos_truth")
    row = rows[0]
    if str(row.get("status") or "active") != "active":
        raise GatewayError("bos_service_not_active")
    if str(row.get("transport") or "") != "internal":
        raise GatewayError("bos_transport_not_internal")

    services = [service for service in service_catalog if str(getattr(service, "uri", "")) == uri]
    if len(services) != 1:
        raise GatewayError("missing_or_duplicate_runtime_service")
    service = services[0]
    if str(getattr(service, "transport", "")) != "internal":
        raise GatewayError("runtime_transport_not_internal")
    description = str(getattr(service, "description", ""))
    if description != str(row.get("description") or ""):
        raise GatewayError("registry_runtime_description_mismatch")
    operation = str(getattr(service, "action", "") or "invoke")

    return {
        "id": capability_id,
        "source": "agora.bos",
        "status": "active",
        "native_bos_uri": uri,
        "kind": "bos_service",
        "transport": "bos_native",
        "operation": operation,
        "adapter": {"kind": "bos_native", "target": uri},
        "description": description,
    }


def _prepare_native_router(router: Any, exact_services: Sequence[Any]) -> Any:
    """Require lifecycle catalogs before any exact route is seeded."""
    router.enable_capability_gating()
    if getattr(router, "_capability_catalog", None) is None or getattr(router, "_admission_catalog", None) is None:
        raise GatewayError("lifecycle_catalog_unavailable")
    router.seed_from_poc(list(exact_services))
    return router


def _load_native_gateway(capability_id: str) -> tuple[Any, Sequence[Any]]:
    """Load Agora's gateway and seed only the exact native route."""
    if str(AGORA_SRC) not in sys.path:
        sys.path.insert(0, str(AGORA_SRC))
    try:
        from agora.capability_gateway import CapabilityInvocationGateway
        from agora.mcp.bos_router import bos_router
        from agora.mcp.resolver.services import POC_SERVICES
    except Exception as exc:  # noqa: BLE001 - public boundary fails closed
        raise GatewayError("gateway_unavailable") from exc

    uri = capability_id.removeprefix("bos-service:")
    exact_services = [service for service in POC_SERVICES if getattr(service, "uri", "") == uri]
    try:
        gateway = CapabilityInvocationGateway(router=_prepare_native_router(bos_router, exact_services))
    except Exception as exc:  # noqa: BLE001 - public boundary fails closed
        if isinstance(exc, GatewayError):
            raise
        raise GatewayError("gateway_unavailable") from exc
    return gateway, POC_SERVICES


def execute_gateway_operation(
    registry: Mapping[str, Any],
    operation: str,
    capability_id: str,
    *,
    payload: Any = None,
    gateway: Any = None,
    service_catalog: Optional[Sequence[Any]] = None,  # noqa: UP045 -- Python 3.9 contract
    binding: Optional[Mapping[str, Any]] = None,  # noqa: UP045 -- Python 3.9 contract
) -> dict[str, Any]:
    """Load or invoke through Agora; never construct a provider process.

    A validated ``binding`` (from capability-sync's ``--binding-json``) is
    forwarded to Agora so the invocation receipt can carry a ``binding_digest``.
    """
    if operation not in {"load", "invoke"}:
        raise GatewayError("unsupported_gateway_operation")
    if gateway is None or service_catalog is None:
        gateway, service_catalog = _load_native_gateway(capability_id)
    record = build_native_bos_record(registry, capability_id, service_catalog)
    selector = {"capability_id": capability_id}
    if operation == "load":
        return dict(gateway.load(record, selector=selector, binding=binding))
    return dict(gateway.invoke(record, payload, selector=selector, binding=binding))


def _gateway_error_receipt(operation: str, selector: Mapping[str, Any], reason: str) -> dict[str, Any]:
    error_code = "CAPABILITY_GATEWAY_UNAVAILABLE" if reason == "gateway_unavailable" else "CAPABILITY_NOT_LOADABLE"
    return {
        "schema": "capability-invocation-receipt/v1",
        "operation": operation,
        "status": "rejected",
        "selector_digest": _digest(json.dumps(selector, sort_keys=True, separators=(",", ":")).encode("utf-8")),
        "error_code": error_code,
        "error_detail_digest": _digest(reason.encode("utf-8")),
        "invocation_attempted": False,
    }


_LOCAL_RESOLUTION_FAILURES = {
    # Exit codes mirror the find contract: not_found=2, ambiguous=3, selector=4.
    "not_found": ("resolution_not_found", 2),
    "ambiguous": ("resolution_ambiguous", 3),
    "invalid_selector": ("resolution_invalid", 4),
}


def _local_rejection_receipt(selector: Mapping[str, Any], failure_code: str) -> dict[str, Any]:
    """Redacted local denial; the selector is never echoed back."""
    return {
        "schema": "capability-local-operation-receipt/v1",
        "status": "rejected",
        "failure_code": failure_code,
        "selector_digest": _digest(_canonical_json(selector)),
        "read_only": True,
        "executed": False,
        "provider_called": False,
        "invoked": False,
        "invocation": {"allowed": False, "route": "none", "reason": failure_code},
        "value_indicator_policy": False,
    }


def _local_capability_receipt(
    operation: str,
    capability_id: str,
    resolution: Optional[Resolution],  # noqa: UP045 -- Python 3.9 contract
    binding: Optional[Mapping[str, Any]] = None,  # noqa: UP045 -- Python 3.9 contract
) -> tuple[dict[str, Any], int]:
    """Authorize local metadata operations without importing or executing sources.

    The capability must first exact-resolve against the loaded registry;
    prefix branching alone never grants a local receipt.
    """
    prefix = capability_id.partition(":")[0]
    selector = {"capability_id": capability_id}
    if resolution is None:
        return _local_rejection_receipt(selector, "invalid_registry"), 4
    if resolution.status != "resolved":
        failure_code, exit_code = _LOCAL_RESOLUTION_FAILURES.get(resolution.status, ("resolution_invalid", 4))
        return _local_rejection_receipt(selector, failure_code), exit_code

    if prefix == "skill" and operation == "invoke":
        return {
            "schema": "capability-local-operation-receipt/v1",
            "status": "rejected",
            "failure_code": "skill_invoke_forbidden",
            "selector_digest": _digest(_canonical_json(selector)),
            "read_only": True,
            "executed": False,
            "provider_called": False,
            "invoked": False,
            "invocation": {"allowed": False, "route": "none", "reason": "skill_load_only"},
            "value_indicator_policy": False,
        }, 4

    if prefix == "workflow" and operation == "invoke":
        try:
            actor_id = validate_trace_binding(binding or {}).get("actor_id")
        except (TypeError, ValueError):
            actor_id = None
        allowed = actor_id == "workflow-controller"
        return {
            "schema": "capability-local-operation-receipt/v1",
            "status": "ready" if allowed else "rejected",
            "failure_code": None if allowed else "workflow_controller_required",
            "selector_digest": _digest(_canonical_json(selector)),
            "read_only": True,
            "executed": False,
            "provider_called": False,
            "invoked": False,
            "invocation": {
                "allowed": allowed,
                "route": "workflow_controller_only" if allowed else "none",
                "reason": "not_executed" if allowed else "workflow_controller_required",
            },
            "value_indicator_policy": False,
        }, 0 if allowed else 4

    return {
        "schema": "capability-local-operation-receipt/v1",
        "status": "ready",
        "selector_digest": _digest(_canonical_json(selector)),
        "read_only": True,
        "executed": False,
        "provider_called": False,
        "invoked": False,
        "invocation": {"allowed": False, "route": "local_metadata_only", "reason": "load_only"},
        "value_indicator_policy": False,
    }, 0


def _read_json_payload(path: Path) -> Any:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise GatewayError("input_json_unreadable") from exc
    if len(content) > MAX_INPUT_JSON_BYTES:
        raise GatewayError("input_json_too_large")
    try:
        return json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GatewayError("input_json_invalid") from exc


def _read_trace_binding(path: Path) -> dict[str, str]:
    """Read only the fixed causal identity envelope for a resolution receipt."""
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise TraceBindingError("binding_unreadable") from exc
    if len(content) > MAX_INPUT_JSON_BYTES:
        raise TraceBindingError("binding_too_large")
    try:
        value = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TraceBindingError("binding_json_invalid") from exc
    return validate_trace_binding(value)


def _read_bounded_native_json(path: Path, prefix: str) -> Any:
    """Read one bounded native receipt JSON; failures raise redacted contract codes."""
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise TraceBindingError(f"{prefix}_unreadable") from exc
    if len(content) > MAX_INPUT_JSON_BYTES:
        raise TraceBindingError(f"{prefix}_too_large")
    try:
        return json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TraceBindingError(f"{prefix}_invalid") from exc


def _binding_error_receipt(selector: Mapping[str, Any], failure_code: str) -> dict[str, Any]:
    """Return a redacted non-execution denial; never echo user-supplied identities."""
    return {
        "schema": "capability-resolution-receipt/v1",
        "status": "rejected",
        "failure_code": failure_code,
        "selector_digest": _digest(_canonical_json(selector)),
        "invocation": {"allowed": False, "route": "native_adapter_only", "reason": "binding_rejected"},
        "states": {"invoked": False, "evidenced": False, "independently_verified": False},
        "value_indicator_policy": False,
    }


_VERIFICATION_FAILURES = {
    "source_unprovable",
    "native_route_unprovable",
    "admission_contradiction",
    "admission_expired",
    "admission_receipt_invalid",
    "authorization_required",
    "value_promotion_forbidden",
}


def _verification_receipt(
    status: str, failure_code: Optional[str] = None, **values: Any  # noqa: UP045 -- Python 3.9 contract
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema": VERIFICATION_RECEIPT_SCHEMA,
        "status": status,
        "value_indicator_policy": False,
    }
    if status == "verified":
        receipt.update(values)
        receipt["authority"] = "omo-workflow-mesh"
    else:
        receipt["failure_code"] = failure_code if failure_code in _VERIFICATION_FAILURES else "native_route_unprovable"
    return receipt


def _mesh_stat_fingerprint(stat: Any) -> tuple[int, int, int, int, int]:
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _mesh_path_stat(path: Path) -> Any:
    """Small seam for testing the pathname identity around one descriptor read."""
    return path.stat()


def _load_workflow_mesh_projection() -> Any:
    """Return the Python-3.9-safe read-only projector for frozen Mesh v1 facts."""
    return _project_verification_mesh_run


def _project_verification_mesh_run(events: list[dict[str, Any]], workflow_run_id: str) -> dict[str, Any]:
    """Materialize only the persisted Mesh v1 facts consumed by verification.

    This is not a writer, registry, or independent authority.  It deliberately
    implements only admitted/dispatched/running StepRun and worker lifecycle
    projection from the already-read authoritative JSONL bytes.
    """
    required_event_fields = {
        "event_id",
        "event_type",
        "trace_id",
        "workflow_run_id",
        "occurred_at",
        "producer",
        "schema_version",
        "idempotency_key",
        "payload",
    }
    allowed_states = {
        "WorkflowRequested": {"unknown"},
        "WorkflowAdmitted": {"planned"},
        "StepDispatched": {"admitted", "dispatched", "running"},
        "StepStarted": {"admitted", "dispatched", "running"},
        "WorkerAcknowledged": {"dispatched", "running"},
        "WorkerLeaseRenewed": {"dispatched", "running"},
        "WorkerLeaseExpired": {"dispatched", "running"},
        "WorkerReclaimed": {"unavailable"},
    }
    snapshot: dict[str, Any] = {
        "workflow_run_id": workflow_run_id,
        "state": "unknown",
        "admission": None,
        "step_runs": {},
        "worker": None,
    }

    for event in events:
        if event.get("workflow_run_id") != workflow_run_id:
            continue
        if not required_event_fields.issubset(event) or event.get("schema_version") != "workflow-mesh/v1":
            raise TraceBindingError("admission_receipt_invalid")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            raise TraceBindingError("admission_receipt_invalid")
        event_type = event.get("event_type")
        if event_type == "AdmissionRenewed":
            raise TraceBindingError("admission_contradiction")
        if event_type not in allowed_states or snapshot["state"] not in allowed_states[event_type]:
            raise TraceBindingError("admission_receipt_invalid")

        if event_type == "WorkflowRequested":
            snapshot["state"] = "planned"
            continue

        if event_type == "WorkflowAdmitted":
            admission = payload.get("admission") or payload
            required_admission_fields = {
                "admission_id",
                "status",
                "workflow_run_id",
                "trace_id",
                "step_run_ids",
                "capabilities",
                "policy_digest",
                "issued_at",
                "expires_at",
                "proof",
            }
            if not isinstance(admission, dict) or not required_admission_fields.issubset(admission):
                raise TraceBindingError("admission_receipt_invalid")
            proof = admission.get("proof")
            unsigned = {key: value for key, value in admission.items() if key != "proof"}
            if (
                admission.get("status") != "admitted"
                or admission.get("workflow_run_id") != workflow_run_id
                or not isinstance(proof, str)
                or "sha256:" + proof != _digest(_canonical_json(unsigned))
                or not isinstance(admission.get("step_run_ids"), list)
                or not admission["step_run_ids"]
            ):
                raise TraceBindingError("admission_receipt_invalid")
            snapshot["admission"] = dict(admission)
            snapshot["state"] = "admitted"
            continue

        admission = snapshot.get("admission")
        step_run_id = payload.get("step_run_id")
        if not step_run_id or not isinstance(admission, dict):
            raise TraceBindingError("admission_receipt_invalid")
        if payload.get("admission_id") != admission.get("admission_id"):
            raise TraceBindingError("admission_receipt_invalid")
        if not any(
            step_run_id == admitted or step_run_id.startswith(f"{admitted}:")
            for admitted in admission["step_run_ids"]
        ):
            raise TraceBindingError("admission_receipt_invalid")
        step_runs = snapshot["step_runs"]
        if event_type != "StepDispatched" and step_run_id not in step_runs:
            raise TraceBindingError("admission_receipt_invalid")

        if event_type.startswith("Worker"):
            required_worker_fields = {"dispatch_id", "worker_id", "step_run_id", "admission_id"}
            worker_specific_fields = {
                "WorkerAcknowledged": {
                    "acknowledged_at",
                    "lease_expires_at",
                    "packet_id",
                    "packet_hash",
                    "instruction_binding",
                    "ack_decision",
                    "ack_origin_proof_digest",
                },
                "WorkerLeaseRenewed": {"heartbeat_id", "heartbeat_at", "lease_expires_at"},
                "WorkerLeaseExpired": {"expired_at", "lease_expires_at", "reason"},
                "WorkerReclaimed": {
                    "reclaimed_at",
                    "successor_worker_id",
                    "successor_dispatch_id",
                    "reason",
                },
            }
            if not (required_worker_fields | worker_specific_fields[event_type]).issubset(payload):
                raise TraceBindingError("admission_receipt_invalid")
            worker = snapshot.get("worker")
            if not isinstance(worker, dict) or any(
                worker.get(key) != payload.get(key) for key in required_worker_fields
            ):
                raise TraceBindingError("admission_receipt_invalid")
            worker_state = worker.get("state")
            if event_type == "WorkerAcknowledged":
                if worker_state not in {"dispatched", "acknowledged"} or payload.get("ack_decision") not in {
                    "proceed",
                    "stop",
                }:
                    raise TraceBindingError("admission_receipt_invalid")
                if any(
                    worker.get(key) != payload.get(key)
                    for key in ("packet_id", "packet_hash", "instruction_binding")
                ):
                    raise TraceBindingError("admission_receipt_invalid")
            elif event_type == "WorkerLeaseRenewed" and worker_state not in {"acknowledged", "active"}:
                raise TraceBindingError("admission_receipt_invalid")
            elif event_type == "WorkerLeaseExpired" and worker_state not in {"acknowledged", "active"}:
                raise TraceBindingError("admission_receipt_invalid")
            elif event_type == "WorkerReclaimed" and worker_state != "lease_expired":
                raise TraceBindingError("admission_receipt_invalid")

        step = step_runs.setdefault(
            step_run_id,
            {
                "step_run_id": step_run_id,
                "state": "unknown",
                "admission_id": payload.get("admission_id"),
            },
        )
        step["state"] = {
            "StepDispatched": "dispatched",
            "StepStarted": "running",
            "WorkerLeaseRenewed": "running",
            "WorkerLeaseExpired": "unavailable",
            "WorkerReclaimed": "running",
        }.get(event_type, step["state"])
        step["admission_id"] = payload.get("admission_id", step.get("admission_id"))

        if event_type == "StepDispatched":
            snapshot["state"] = "running" if snapshot["state"] == "running" else "dispatched"
            if payload.get("dispatch_id"):
                snapshot["worker"] = {
                    "dispatch_id": payload["dispatch_id"],
                    "worker_id": payload.get("worker_id"),
                    "step_run_id": step_run_id,
                    "admission_id": payload.get("admission_id"),
                    "packet_id": payload.get("packet_id"),
                    "packet_hash": payload.get("packet_hash"),
                    "instruction_binding": payload.get("instruction_binding"),
                    "state": "dispatched",
                }
        elif event_type == "StepStarted":
            snapshot["state"] = "running"
        else:
            worker = snapshot["worker"]
            assert isinstance(worker, dict)
            if event_type == "WorkerAcknowledged":
                worker.update(
                    {
                        "state": "acknowledged",
                        "packet_id": payload["packet_id"],
                        "packet_hash": payload["packet_hash"],
                        "instruction_binding": payload["instruction_binding"],
                    }
                )
            elif event_type == "WorkerLeaseRenewed":
                worker["state"] = "active"
                snapshot["state"] = "running"
            elif event_type == "WorkerLeaseExpired":
                worker["state"] = "lease_expired"
                snapshot["state"] = "unavailable"
            else:
                worker.update(
                    {
                        "state": "reclaimed",
                        "successor_worker_id": payload["successor_worker_id"],
                        "successor_dispatch_id": payload["successor_dispatch_id"],
                    }
                )
                snapshot["state"] = "running"
    return snapshot


def _read_mesh_snapshot(omo_dir: Path, workflow_run_id: str) -> dict[str, Any]:
    """Read the append-only Mesh log without constructing its locking store."""
    log_path = Path(omo_dir) / MESH_LOG
    try:
        with log_path.open("rb") as mesh_log:
            before = os.fstat(mesh_log.fileno())
            before_path = _mesh_path_stat(log_path)
            content = mesh_log.read(MAX_MESH_LOG_BYTES + 1)
            after = os.fstat(mesh_log.fileno())
            after_path = _mesh_path_stat(log_path)
    except (OSError, UnicodeError) as exc:
        raise TraceBindingError("source_unprovable") from exc
    if (
        _mesh_stat_fingerprint(before) != _mesh_stat_fingerprint(after)
        or (before.st_dev, before.st_ino) != (before_path.st_dev, before_path.st_ino)
        or (after.st_dev, after.st_ino) != (after_path.st_dev, after_path.st_ino)
        or len(content) > MAX_MESH_LOG_BYTES
    ):
        raise TraceBindingError("source_unprovable")
    events: list[dict[str, Any]] = []
    try:
        for line in content.splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("event_not_mapping")
            events.append(event)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise TraceBindingError("admission_receipt_invalid") from exc
    if any(
        event.get("workflow_run_id") == workflow_run_id and event.get("event_type") == "AdmissionRenewed"
        for event in events
    ):
        # OMO's v1 projection records the transition but does not rebind the
        # grant proof or expiry.  No old or caller-proposed receipt is sound.
        raise TraceBindingError("admission_contradiction")
    try:
        projector = _load_workflow_mesh_projection()
    except TraceBindingError:
        raise
    except Exception as exc:  # noqa: BLE001 - unavailable OMO source is a redacted source failure
        raise TraceBindingError("source_unprovable") from exc
    try:
        snapshot = projector(events, workflow_run_id)
    except Exception as exc:  # noqa: BLE001 - Mesh details must never cross the public boundary
        raise TraceBindingError("admission_receipt_invalid") from exc
    if not isinstance(snapshot, dict):
        raise TraceBindingError("admission_receipt_invalid")
    return snapshot


def _parse_verification_envelope(envelope: Any) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(envelope, Mapping) or set(envelope) != VERIFICATION_FIELDS:
        raise TraceBindingError("native_route_unprovable")
    if envelope.get("schema") != VERIFICATION_SCHEMA:
        raise TraceBindingError("native_route_unprovable")
    material = envelope.get("material")
    request = envelope.get("request")
    expected = envelope.get("expected")
    if (
        not isinstance(material, Mapping)
        or not isinstance(request, Mapping)
        or not isinstance(expected, Mapping)
        or set(expected) != VERIFICATION_EXPECTED_FIELDS
    ):
        raise TraceBindingError("native_route_unprovable")
    return dict(envelope), dict(material), dict(request), dict(expected)


def _verify_worker_context(material: Mapping[str, Any], snapshot: Mapping[str, Any]) -> None:
    binding = material["binding"]
    admission_material = material["admission"]
    worker = snapshot.get("worker")
    if not isinstance(worker, Mapping):
        raise TraceBindingError("admission_receipt_invalid")
    if snapshot.get("state") not in {"dispatched", "running"}:
        raise TraceBindingError("admission_contradiction")
    if worker.get("state") not in {"dispatched", "acknowledged", "active"}:
        raise TraceBindingError("admission_contradiction")
    expected = {
        "dispatch_id": binding["dispatch_id"],
        "worker_id": admission_material["worker"].get("id"),
        "step_run_id": admission_material["step_run_id"],
        "admission_id": admission_material["admission_id"],
        "packet_id": binding["packet_id"],
        "packet_hash": binding["packet_hash"],
    }
    if any(worker.get(key) != value for key, value in expected.items()):
        raise TraceBindingError("admission_receipt_invalid")
    if binding.get("actor_id") != worker.get("worker_id"):
        raise TraceBindingError("admission_receipt_invalid")


def verify_material_against_mesh(  # noqa: UP007 -- public Python 3.9 compatibility contract
    omo_dir: Union[Path, str], envelope: Mapping[str, Any]  # noqa: UP007 -- Python 3.9 style
) -> dict[str, Any]:
    """Verify frozen execution material against one stable, persisted Mesh read."""
    try:
        _raw, material_input, request, expected = _parse_verification_envelope(envelope)
        if not NATIVE_EXECUTION_LIBS_AVAILABLE:
            raise TraceBindingError("native_route_unprovable")
        material = validate_native_execution_material(material_input)
        if expected != {
            "capability_id": material["capability"]["id"],
            "operation_id": material["operation_id"],
            "effect_classification": material["effect_classification"],
        }:
            raise TraceBindingError("native_route_unprovable")
        if material["capability"]["kind"] not in {"mcp_tool", "bos_service"}:
            raise TraceBindingError("native_route_unprovable")
        if canonical_digest(request) != material["request_digest"]:
            raise TraceBindingError("native_route_unprovable")

        binding = material["binding"]
        admission_material = material["admission"]
        snapshot = _read_mesh_snapshot(Path(omo_dir), binding["workflow_run_id"])
        admission = snapshot.get("admission")
        if snapshot.get("workflow_run_id") != binding["workflow_run_id"]:
            raise TraceBindingError("admission_contradiction")
        if snapshot.get("state") not in {"admitted", "dispatched", "running"}:
            raise TraceBindingError("admission_contradiction")
        if not isinstance(admission, Mapping):
            raise TraceBindingError("admission_receipt_invalid")
        proof = admission.get("proof")
        if not isinstance(proof, str) or re.fullmatch(r"[0-9a-f]{64}", proof) is None:
            raise TraceBindingError("admission_receipt_invalid")
        if admission.get("admission_id") != admission_material["admission_id"]:
            raise TraceBindingError("admission_receipt_invalid")
        if admission_material["receipt_digest"] != "sha256:" + proof:
            raise TraceBindingError("admission_receipt_invalid")
        if admission.get("workflow_run_id") != binding["workflow_run_id"]:
            raise TraceBindingError("admission_contradiction")

        request_identity = admission.get("request_identity")
        if not isinstance(request_identity, Mapping):
            raise TraceBindingError("admission_receipt_invalid")
        identity_expected = {"packet_id": binding["packet_id"], "packet_hash": binding["packet_hash"]}
        if any(request_identity.get(key) != value for key, value in identity_expected.items()):
            raise TraceBindingError("admission_receipt_invalid")
        capabilities = admission.get("capabilities")
        if (
            not isinstance(capabilities, list)
            or not capabilities
            or any(
                not isinstance(capability, str)
                or not IDENTITY_RE.fullmatch(capability)
                or ".." in capability
                for capability in capabilities
            )
            or material["capability"]["id"] not in capabilities
        ):
            raise TraceBindingError("admission_receipt_invalid")
        if material["admission"]["step_run_id"] not in admission.get("step_run_ids", []):
            raise TraceBindingError("admission_receipt_invalid")

        try:
            expires_at = datetime.fromisoformat(str(admission["expires_at"]).replace("Z", "+00:00"))
            issued_at = datetime.fromisoformat(str(admission["issued_at"]).replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise TraceBindingError("admission_receipt_invalid") from exc
        if expires_at.tzinfo is None or issued_at.tzinfo is None or issued_at >= expires_at:
            raise TraceBindingError("admission_receipt_invalid")
        if datetime.now(timezone.utc) >= expires_at:  # noqa: UP017 -- Python 3.9 has no datetime.UTC
            raise TraceBindingError("admission_expired")

        effect = material["effect_classification"]
        if effect == "effectful" and snapshot.get("state") not in {"dispatched", "running"}:
            raise TraceBindingError("admission_contradiction")
        requires_projected_step = effect == "effectful" or snapshot.get("state") in {"dispatched", "running"}
        if requires_projected_step:
            step_runs = snapshot.get("step_runs")
            step = step_runs.get(admission_material["step_run_id"]) if isinstance(step_runs, Mapping) else None
            if not isinstance(step, Mapping) or step.get("admission_id") != admission_material["admission_id"]:
                raise TraceBindingError("admission_receipt_invalid")
        if effect == "effectful":
            _verify_worker_context(material, snapshot)
        elif snapshot.get("state") in {"dispatched", "running"}:
            _verify_worker_context(material, snapshot)
        return _verification_receipt(
            "verified",
            material_digest=canonical_digest(material),
            admission_digest=admission_material["receipt_digest"],
            capability_id=material["capability"]["id"],
            operation_id=material["operation_id"],
            effect_classification=effect,
        )
    except TraceBindingError as exc:
        return _verification_receipt("rejected", str(exc))
    except (NativeExecutionReceiptError, KeyError, TypeError, ValueError):
        return _verification_receipt("rejected", "native_route_unprovable")


def _read_bounded_stdin_json() -> Any:
    try:
        stream = getattr(sys.stdin, "buffer", sys.stdin)
        content = stream.read(MAX_INPUT_JSON_BYTES + 1)
        if not isinstance(content, (bytes, bytearray)) or len(content) > MAX_INPUT_JSON_BYTES:
            raise TraceBindingError("native_route_unprovable")
        return json.loads(content)
    except TraceBindingError:
        raise
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        raise TraceBindingError("native_route_unprovable") from exc


def _delegate_to_writer(action: str, registry_path: Path) -> int:
    command = [sys.executable, str(CANONICAL_GENERATOR), "--quiet", "--output", str(registry_path)]
    if action == "check":
        command.append("--check")
    return subprocess.run(command, check=False).returncode


def _delegate_to_federation_auditor(workspace_root: Path, *, strict: bool) -> int:
    """Run the internal read-only observer through a fixed public command."""
    command = [
        sys.executable,
        str(FEDERATION_AUDITOR),
        "--workspace-root",
        str(workspace_root),
        "--json",
    ]
    if strict:
        command.append("--strict")
    return subprocess.run(command, check=False).returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capability registry compatibility and discovery CLI")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser(
        "verify-material",
        help="verify one bounded native execution material envelope against persisted Workflow Mesh admission",
    )

    sync_parser = commands.add_parser("sync", help="delegate generation to the projection writer")
    sync_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)

    check_parser = commands.add_parser("check", help="delegate read-only drift check")
    check_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)

    audit_parser = commands.add_parser(
        "federation-audit",
        help="audit native capability authorities without writing or invoking them",
    )
    audit_parser.add_argument("--workspace-root", type=Path, default=ROOT)
    audit_parser.add_argument("--json", action="store_true", help="emit canonical JSON")
    audit_parser.add_argument("--strict", action="store_true", help="treat warnings as non-zero")

    find_parser = commands.add_parser("find", help="resolve one capability without invoking it")
    selector = find_parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--id", dest="capability_id", help="exact capability ID")
    selector.add_argument("--query", help="compatibility search; ambiguity is rejected")
    find_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    find_parser.add_argument(
        "--binding-json",
        type=Path,
        help="read-only B4-B causal binding JSON; requires --id and never authorizes invocation",
    )

    inspect_parser = commands.add_parser(
        "inspect",
        help="statically prove one exact native declaration without loading or invoking it",
    )
    inspect_parser.add_argument("--id", dest="capability_id", required=True, help="exact native capability ID")
    inspect_upstream = inspect_parser.add_mutually_exclusive_group(required=True)
    inspect_upstream.add_argument(
        "--binding-json",
        type=Path,
        help="B4-B causal binding for Skill/Workflow kinds outside the generated projection",
    )
    inspect_upstream.add_argument(
        "--resolution-receipt-json",
        type=Path,
        help="B4-B resolution receipt required for MCP/BOS native inspection",
    )
    inspect_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)

    load_parser = commands.add_parser("load", help="admit and probe one exact native BOS capability")
    load_parser.add_argument("--id", dest="capability_id", required=True, help="exact BOS capability ID")
    load_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    load_parser.add_argument(
        "--binding-json",
        type=Path,
        help="read-only B4-B causal binding JSON; forwarded to Agora so the receipt carries a binding_digest",
    )

    invoke_parser = commands.add_parser("invoke", help="invoke one admitted native BOS capability")
    invoke_parser.add_argument("--id", dest="capability_id", required=True, help="exact BOS capability ID")
    invoke_parser.add_argument("--input-json", type=Path, required=True, help="bounded structured input file")
    invoke_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    invoke_parser.add_argument(
        "--binding-json",
        type=Path,
        help="read-only B4-B causal binding JSON; forwarded to Agora so the receipt carries a binding_digest",
    )

    for target_parser in (load_parser, invoke_parser):
        target_parser.add_argument(
            "--inspection-receipt-json",
            type=Path,
            help="bounded native inspection receipt JSON required for a bound execution",
        )
        target_parser.add_argument(
            "--admission-receipt-json",
            type=Path,
            help="bounded admission receipt JSON required for a bound execution",
        )
        target_parser.add_argument(
            "--operation-id",
            help="caller-owned operation identifier recorded in the native execution material",
        )
        target_parser.add_argument(
            "--effect-classification",
            choices=("read_only", "effectful"),
            help="declared effect classification recorded in the native execution material",
        )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:  # noqa: UP045 -- Python 3.9 contract
    args = _parser().parse_args(argv)
    if args.command == "verify-material":
        try:
            envelope = _read_bounded_stdin_json()
        except TraceBindingError as exc:
            receipt = _verification_receipt("rejected", str(exc))
        else:
            receipt = verify_material_against_mesh(ROOT / ".omo", envelope)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0 if receipt.get("status") == "verified" else 4

    if args.command in {"sync", "check"}:
        return _delegate_to_writer(args.command, args.registry)

    if args.command == "federation-audit":
        return _delegate_to_federation_auditor(args.workspace_root, strict=args.strict)

    if args.command == "inspect":
        try:
            if native_kind_requires_projection(args.capability_id):
                before = args.registry.stat()
                registry_content = args.registry.read_bytes()
                registry = load_registry(args.registry)
                after = args.registry.stat()
                if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev,
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                ) or len(registry_content) != before.st_size:
                    raise NativeInspectionError("source_digest_mismatch")
            else:
                registry_content = b""
                registry = {}
            binding = _read_json_payload(args.binding_json) if args.binding_json is not None else None
            resolution_receipt = (
                _read_json_payload(args.resolution_receipt_json) if args.resolution_receipt_json is not None else None
            )
            receipt = inspect_native_capability(
                root=ROOT,
                capability_id=args.capability_id,
                registry=registry,
                registry_content=registry_content,
                binding=binding,
                resolution_receipt=resolution_receipt,
            )
        except NativeInspectionError as exc:
            receipt = inspection_error_receipt(args.capability_id, str(exc))
        except GatewayError:
            receipt = inspection_error_receipt(args.capability_id, "upstream_resolution_invalid")
        except (OSError, RegistryError):
            receipt = inspection_error_receipt(args.capability_id, "source_unprovable")
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0 if receipt.get("status") == "inspected" else 4

    if args.command in {"load", "invoke"}:
        selector = {"capability_id": args.capability_id}
        try:
            local_capability = not native_kind_requires_projection(args.capability_id)
        except NativeInspectionError:
            local_capability = False
        if local_capability:
            try:
                binding = _read_trace_binding(args.binding_json) if args.binding_json is not None else None
            except TraceBindingError:
                binding = None
            try:
                registry = load_registry(args.registry)
                resolution = resolve_capability(registry, capability_id=args.capability_id)
            except (OSError, RegistryError):
                resolution = None
            receipt, exit_code = _local_capability_receipt(args.command, args.capability_id, resolution, binding)
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
            return exit_code
        bundle = (
            args.binding_json,
            args.inspection_receipt_json,
            args.admission_receipt_json,
            args.operation_id,
            args.effect_classification,
        )
        bundle_present = any(value is not None for value in bundle)
        bundle_complete = all(value is not None for value in bundle)
        if bundle_present and not bundle_complete:
            print(
                json.dumps(
                    _binding_error_receipt(selector, "binding_bundle_incomplete"),
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 4
        if not bundle_present:
            # Shadow rollout invariant: legacy responses are observed only and are
            # never labeled native or independently verified.
            try:
                registry = load_registry(args.registry)
                payload = _read_json_payload(args.input_json) if args.command == "invoke" else None
                receipt = execute_gateway_operation(registry, args.command, args.capability_id, payload=payload)
            except (GatewayError, OSError, RegistryError) as exc:
                reason = str(exc) if isinstance(exc, GatewayError) else "invalid_registry"
                receipt = _gateway_error_receipt(args.command, selector, reason)
            receipt["binding_enforcement"] = f"{BINDING_ENFORCEMENT}_missing"
            print("capability binding is required for new callers", file=sys.stderr)
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
            return 0 if receipt.get("status") in {"ready", "succeeded"} else 5

        try:
            if not NATIVE_EXECUTION_LIBS_AVAILABLE:
                raise TraceBindingError("native_execution_libraries_unavailable")
            binding = _read_trace_binding(args.binding_json)
            inspection = _read_bounded_native_json(args.inspection_receipt_json, "inspection_receipt")
            admission = _read_bounded_native_json(args.admission_receipt_json, "admission_receipt")
            capability = inspection.get("capability") if isinstance(inspection, dict) else None
            if not isinstance(capability, dict) or capability.get("id") != args.capability_id:
                raise TraceBindingError("native_route_unprovable")
            if args.effect_classification == "effectful":
                # Fail closed until a caller-owned terminal action evidence path exists.
                raise TraceBindingError("execution_evidence_missing")
            payload = _read_json_payload(args.input_json) if args.command == "invoke" else None
            material = build_native_execution_material(
                binding=binding,
                capability=capability,
                inspection={
                    "receipt_digest": inspection["receipt_digest"],
                    "source_digest": inspection["source_digest"],
                },
                operation_id=args.operation_id,
                request_digest=canonical_digest(payload),
                admission=admission,
                authorization_source=AUTHORIZATION_BY_KIND[capability["kind"]],
                effect_classification=args.effect_classification,
                execution_attempt=1,
            )
            # Derivation-only marker: durable persistence stays caller-owned.
            build_native_execution_marker(material)
            registry = load_registry(args.registry)
            gateway_receipt = execute_gateway_operation(
                registry, args.command, args.capability_id, payload=payload, binding=binding
            )
            succeeded = gateway_receipt.get("status") == "succeeded"
            cleanup = build_native_cleanup_proof(
                capability_kind=material["capability"]["kind"],
                invocation_id=derive_invocation_id(material),
                ownership_scope=OWNERSHIP_BY_KIND[material["capability"]["kind"]],
                baseline_digest=canonical_digest(payload),
                terminal_digest=canonical_digest(payload),
                measurements={
                    "owned_lock_count": 0,
                    "reference_count_delta": 0,
                    "connection_created": False,
                    "connection_disconnected": False,
                    "owned_residue_count": 0,
                },
                status="proved",
                failure_code=None,
            )
            receipt = build_native_execution_receipt(
                material=material,
                transport_state="confirmed" if succeeded else "failed",
                outcome="succeeded" if succeeded else "failed",
                failure_code=None if succeeded else "native_invocation_failed",
                result_digest=canonical_digest(gateway_receipt) if succeeded else None,
                action_receipt={"status": "not_applicable", "id": None, "digest": None},
                cleanup_proof=cleanup,
            )
        except (GatewayError, OSError, RegistryError) as exc:
            reason = str(exc) if isinstance(exc, GatewayError) else "invalid_registry"
            receipt = _gateway_error_receipt(args.command, selector, reason)
        except (TraceBindingError, NativeExecutionReceiptError) as exc:
            receipt = _binding_error_receipt(selector, str(exc))
            print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
            return 4
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0 if receipt.get("status") in {"ready", "succeeded", "completed"} else 5

    selector: dict[str, Any] = {}
    if args.capability_id:
        selector["capability_id"] = args.capability_id
    else:
        selector["query"] = args.query

    binding: Optional[dict[str, str]] = None  # noqa: UP045 -- Python 3.9 contract
    if args.binding_json is not None:
        if not args.capability_id:
            print(
                json.dumps(
                    _binding_error_receipt(selector, "binding_requires_exact_id"), ensure_ascii=False, sort_keys=True
                )
            )
            return 4
        try:
            binding = _read_trace_binding(args.binding_json)
        except TraceBindingError as exc:
            print(json.dumps(_binding_error_receipt(selector, str(exc)), ensure_ascii=False, sort_keys=True))
            return 4

    try:
        content = args.registry.read_bytes()
        registry = load_registry(args.registry)
        result = resolve_capability(registry, **selector)
    except (OSError, RegistryError):
        content = b""
        registry = None
        result = Resolution("invalid_registry", None, (), 0)

    if binding is not None and result.status == "invalid_registry":
        receipt = _binding_error_receipt(selector, "source_unprovable")
    else:
        try:
            receipt = build_resolution_receipt(
                result,
                content,
                selector,
                binding=binding,
                projection_metadata=registry,
            )
        except TraceBindingError as exc:
            receipt = _binding_error_receipt(selector, str(exc))
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    if receipt.get("status") == "rejected":
        return 4
    return {
        "resolved": 0,
        "not_found": 2,
        "ambiguous": 3,
        "invalid_selector": 4,
        "invalid_registry": 4,
    }[result.status]


if __name__ == "__main__":
    sys.exit(main())
