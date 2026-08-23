#!/usr/bin/env python3
"""Compatibility CLI for the generated capability discovery projection.

``bin/cockpit/gen-capability-registry.py`` is the sole projection writer. This
module delegates sync/check to it, provides read-only discovery, and exposes
the narrow public boundary for governed BOS loading/invocation. Native provider,
BOS, and workflow registries remain the authorities. Only exact canonical IDs
may reach Agora's native gateway; caller supplied commands,
argv, module paths, targets, and transport overrides are never accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:  # pragma: no cover - exercised by the CLI environment
    yaml = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "docs" / "generated" / "capability-registry.yaml"
CANONICAL_GENERATOR = ROOT / "bin" / "cockpit" / "gen-capability-registry.py"
FEDERATION_AUDITOR = ROOT / "lib" / "capability_federation_audit.py"
AGORA_SRC = ROOT / "projects" / "agora" / "src"
SUPPORTED_SCHEMA_MAJOR = 1
MAX_INPUT_JSON_BYTES = 1024 * 1024
CANONICAL_REGISTRY_METADATA = {
    "schema": "capability-registry/v1",
    "owner": "workspace-capability-governance",
    "writer": "bin/cockpit/gen-capability-registry.py",
}
TRACE_BINDING_REQUIRED_FIELDS = (
    "correlation_id",
    "workflow_run_id",
    "packet_id",
    "packet_hash",
    "assignment_id",
    "dispatch_id",
    "actor_id",
    "delivery_attempt_id",
)
TRACE_BINDING_SCHEMA = "capability-trace-binding/v1"
RESOLUTION_SOURCE_REF = "generated:capability-registry/v1"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTITY_RE = re.compile(r"^[A-Za-z0-9._:@/-]{1,256}$")
CAPABILITY_SEMANTICS = {
    "mcp_server": {"native_owner": "mcp", "adapter_kind": "mcp_native"},
    "mcp_tool": {"native_owner": "mcp", "adapter_kind": "mcp_native"},
    "bos_service": {"native_owner": "agora", "adapter_kind": "bos_native"},
    "cli_command": {"native_owner": "cockpit", "adapter_kind": "cockpit_native"},
    "legacy_capability": {"native_owner": "legacy_projection", "adapter_kind": "legacy_discovery_only"},
}


class RegistryError(ValueError):
    """The registry is missing, malformed, or uses an unsupported schema."""


class GatewayError(ValueError):
    """The capability cannot safely enter the governed native gateway."""


class TraceBindingError(ValueError):
    """A resolution binding is incomplete, private, or cannot be replayed."""


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


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def validate_trace_binding(binding: Mapping[str, Any]) -> dict[str, str]:
    """Return the canonical, privacy-safe causal identifiers or reject them."""
    if not isinstance(binding, Mapping):
        raise TraceBindingError("binding_not_mapping")
    supplied = set(binding)
    required = set(TRACE_BINDING_REQUIRED_FIELDS)
    if supplied - required:
        raise TraceBindingError("binding_unknown_fields")
    if required - supplied:
        raise TraceBindingError("binding_required_fields_missing")

    canonical: dict[str, str] = {}
    for field in TRACE_BINDING_REQUIRED_FIELDS:
        value = binding[field]
        if not isinstance(value, str) or not value or value != value.strip() or any(ord(char) < 32 for char in value):
            raise TraceBindingError("binding_identifier_invalid")
        if value.startswith(("/", "~", "\\")) or re.match(r"^[A-Za-z]:[\\/]", value):
            raise TraceBindingError("binding_absolute_path_forbidden")
        if field != "packet_hash" and (not IDENTITY_RE.fullmatch(value) or ".." in value):
            raise TraceBindingError("binding_identifier_invalid")
        canonical[field] = value
    if not SHA256_RE.fullmatch(canonical["packet_hash"]):
        raise TraceBindingError("binding_packet_hash_invalid")
    return canonical


def _native_owner(kind: str) -> str:
    return str(CAPABILITY_SEMANTICS.get(kind, {}).get("native_owner") or "projection")


def _validate_capability_binding(capability: Mapping[str, Any]) -> None:
    capability_id = capability.get("id")
    if (
        not isinstance(capability_id, str)
        or not IDENTITY_RE.fullmatch(capability_id)
        or ".." in capability_id
        or capability_id.startswith(("/", "~", "\\"))
    ):
        raise TraceBindingError("capability_id_invalid")
    kind = capability.get("kind")
    semantics = CAPABILITY_SEMANTICS.get(str(kind))
    if semantics is None or any(capability.get(field) != expected for field, expected in semantics.items()):
        raise TraceBindingError("capability_semantics_invalid")


def _trace_projection(
    binding: Mapping[str, str], capability: Mapping[str, Any], registry_digest: str
) -> dict[str, Any]:
    return {
        "schema": TRACE_BINDING_SCHEMA,
        "binding": dict(binding),
        "capability": dict(capability),
        "resolution_source": {
            "authority": "projection",
            "ref": RESOLUTION_SOURCE_REF,
            "digest": registry_digest,
        },
    }


def _bound_resolution_receipt(
    receipt: Mapping[str, Any],
    result: Resolution,
    selector: Mapping[str, Any],
    binding: Mapping[str, Any],
    projection_metadata: Optional[Mapping[str, Any]],  # noqa: UP045 -- Python 3.9 contract
) -> dict[str, Any]:
    if result.status == "not_found":
        raise TraceBindingError("resolution_not_found")
    if result.status == "ambiguous":
        raise TraceBindingError("resolution_ambiguous")
    if result.status != "resolved" or result.capability is None:
        raise TraceBindingError("resolution_not_exactly_resolved")
    if set(selector) != {"capability_id"} or selector.get("capability_id") != result.capability["id"]:
        raise TraceBindingError("binding_requires_exact_id")
    if not isinstance(projection_metadata, Mapping) or any(
        projection_metadata.get(key) != expected for key, expected in CANONICAL_REGISTRY_METADATA.items()
    ):
        raise TraceBindingError("source_unprovable")

    canonical_binding = validate_trace_binding(binding)
    raw_capability = result.capability
    capability = {
        "id": str(raw_capability["id"]),
        "kind": str(raw_capability["kind"]),
        "adapter_kind": str(raw_capability["adapter"]["kind"]),
        "native_owner": _native_owner(str(raw_capability["kind"])),
    }
    _validate_capability_binding(capability)
    registry_digest = str(receipt["registry_digest"])
    trace = _trace_projection(canonical_binding, capability, registry_digest)
    bound = dict(receipt)
    # The legacy discovery adapter target is intentionally excluded: a binding
    # is resolution evidence, never a generic command or transport surface.
    bound.pop("capability_id", None)
    bound.pop("adapter", None)
    bound.update(
        {
            "binding": canonical_binding,
            "capability": capability,
            "resolution_source": trace["resolution_source"],
            "trace_id": _digest(_canonical_json(trace)),
            "states": {
                "invoked": False,
                "evidenced": False,
                "independently_verified": False,
            },
            "value_indicator_policy": False,
        }
    )
    bound["receipt_digest"] = _digest(_canonical_json(bound))
    return validate_trace_bound_resolution_receipt(bound)


def validate_trace_bound_resolution_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Replay-check a B4-B receipt without reading a runtime or executing it."""
    if not isinstance(receipt, Mapping):
        raise TraceBindingError("receipt_not_mapping")
    expected_fields = {
        "schema", "status", "registry_digest", "selector_digest", "match_count", "candidate_id_digests",
        "admission", "invocation", "binding", "capability", "resolution_source", "trace_id", "states",
        "value_indicator_policy", "receipt_digest",
    }
    if set(receipt) != expected_fields:
        raise TraceBindingError("receipt_fields_invalid")
    if receipt.get("schema") != "capability-resolution-receipt/v1" or receipt.get("status") != "resolved":
        raise TraceBindingError("receipt_status_invalid")
    if receipt.get("admission") != {"required": True, "decision": "not_evaluated"}:
        raise TraceBindingError("admission_invalid")
    if receipt.get("invocation") != {
        "allowed": False,
        "route": "native_adapter_only",
        "reason": "admission_not_evaluated",
    }:
        raise TraceBindingError("invocation_forbidden")
    if receipt.get("states") != {"invoked": False, "evidenced": False, "independently_verified": False}:
        raise TraceBindingError("receipt_state_promotion_forbidden")
    if receipt.get("value_indicator_policy") is not False:
        raise TraceBindingError("value_promotion_forbidden")
    if not SHA256_RE.fullmatch(str(receipt.get("registry_digest") or "")):
        raise TraceBindingError("resolution_source_digest_invalid")
    binding = validate_trace_binding(receipt.get("binding", {}))
    capability = receipt.get("capability")
    if not isinstance(capability, Mapping) or set(capability) != {"id", "kind", "adapter_kind", "native_owner"}:
        raise TraceBindingError("capability_binding_invalid")
    if not all(isinstance(capability[field], str) and capability[field] for field in capability):
        raise TraceBindingError("capability_binding_invalid")
    _validate_capability_binding(capability)
    capability_id = str(capability["id"])
    if receipt.get("match_count") != 1:
        raise TraceBindingError("resolution_match_count_invalid")
    if receipt.get("candidate_id_digests") != [_digest(capability_id.encode("utf-8"))]:
        raise TraceBindingError("resolution_candidate_digest_invalid")
    if receipt.get("selector_digest") != _digest(_canonical_json({"capability_id": capability_id})):
        raise TraceBindingError("resolution_selector_digest_invalid")
    source = receipt.get("resolution_source")
    if source != {
        "authority": "projection",
        "ref": RESOLUTION_SOURCE_REF,
        "digest": receipt["registry_digest"],
    }:
        raise TraceBindingError("resolution_source_invalid")
    expected_trace = _digest(_canonical_json(_trace_projection(binding, capability, str(receipt["registry_digest"]))))
    if receipt.get("trace_id") != expected_trace:
        raise TraceBindingError("trace_id_mismatch")
    without_digest = dict(receipt)
    supplied_digest = without_digest.pop("receipt_digest")
    if supplied_digest != _digest(_canonical_json(without_digest)):
        raise TraceBindingError("receipt_digest_mismatch")
    return dict(receipt)


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
    if (
        getattr(router, "_capability_catalog", None) is None
        or getattr(router, "_admission_catalog", None) is None
    ):
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
        gateway = CapabilityInvocationGateway(
            router=_prepare_native_router(bos_router, exact_services)
        )
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
) -> dict[str, Any]:
    """Load or invoke through Agora; never construct a provider process."""
    if operation not in {"load", "invoke"}:
        raise GatewayError("unsupported_gateway_operation")
    if gateway is None or service_catalog is None:
        gateway, service_catalog = _load_native_gateway(capability_id)
    record = build_native_bos_record(registry, capability_id, service_catalog)
    selector = {"capability_id": capability_id}
    if operation == "load":
        return dict(gateway.load(record, selector=selector))
    return dict(gateway.invoke(record, payload, selector=selector))


def _gateway_error_receipt(operation: str, selector: Mapping[str, Any], reason: str) -> dict[str, Any]:
    error_code = (
        "CAPABILITY_GATEWAY_UNAVAILABLE"
        if reason == "gateway_unavailable"
        else "CAPABILITY_NOT_LOADABLE"
    )
    return {
        "schema": "capability-invocation-receipt/v1",
        "operation": operation,
        "status": "rejected",
        "selector_digest": _digest(
            json.dumps(selector, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "error_code": error_code,
        "error_detail_digest": _digest(reason.encode("utf-8")),
        "invocation_attempted": False,
    }


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

    load_parser = commands.add_parser("load", help="admit and probe one exact native BOS capability")
    load_parser.add_argument("--id", dest="capability_id", required=True, help="exact BOS capability ID")
    load_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)

    invoke_parser = commands.add_parser("invoke", help="invoke one admitted native BOS capability")
    invoke_parser.add_argument("--id", dest="capability_id", required=True, help="exact BOS capability ID")
    invoke_parser.add_argument("--input-json", type=Path, required=True, help="bounded structured input file")
    invoke_parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:  # noqa: UP045 -- Python 3.9 contract
    args = _parser().parse_args(argv)
    if args.command in {"sync", "check"}:
        return _delegate_to_writer(args.command, args.registry)

    if args.command == "federation-audit":
        return _delegate_to_federation_auditor(args.workspace_root, strict=args.strict)

    if args.command in {"load", "invoke"}:
        selector = {"capability_id": args.capability_id}
        try:
            registry = load_registry(args.registry)
            payload = _read_json_payload(args.input_json) if args.command == "invoke" else None
            receipt = execute_gateway_operation(
                registry,
                args.command,
                args.capability_id,
                payload=payload,
            )
        except (GatewayError, OSError, RegistryError) as exc:
            reason = str(exc) if isinstance(exc, GatewayError) else "invalid_registry"
            receipt = _gateway_error_receipt(args.command, selector, reason)
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0 if receipt.get("status") in {"ready", "succeeded"} else 5

    selector: dict[str, Any] = {}
    if args.capability_id:
        selector["capability_id"] = args.capability_id
    else:
        selector["query"] = args.query

    binding: Optional[dict[str, str]] = None  # noqa: UP045 -- Python 3.9 contract
    if args.binding_json is not None:
        if not args.capability_id:
            print(json.dumps(_binding_error_receipt(selector, "binding_requires_exact_id"), ensure_ascii=False, sort_keys=True))
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
