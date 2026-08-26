"""Pure, replay-safe helpers for B4-B capability-resolution trace binding.

This module owns only deterministic data validation and receipt construction.
It never reads files, imports provider/runtime modules, starts processes, or
writes state.  ``bin/capability-sync.py`` owns registry I/O and CLI errors.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Any, Optional

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
CANONICAL_REGISTRY_METADATA = {
    "schema": "capability-registry/v1",
    "owner": "workspace-capability-governance",
    "writer": "bin/ssot/gen-capability-registry.py",
}
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTITY_RE = re.compile(r"^[A-Za-z0-9._:@/-]{1,256}$")
CAPABILITY_SEMANTICS = {
    "mcp_server": {"native_owner": "mcp", "adapter_kind": "mcp_native"},
    "mcp_tool": {"native_owner": "mcp", "adapter_kind": "mcp_native"},
    "bos_service": {"native_owner": "agora", "adapter_kind": "bos_native"},
    "cli_command": {"native_owner": "cockpit", "adapter_kind": "cockpit_native"},
    "legacy_capability": {"native_owner": "legacy_projection", "adapter_kind": "legacy_discovery_only"},
}


class TraceBindingError(ValueError):
    """A resolution binding is incomplete, private, or cannot be replayed."""


def _digest(value: bytes) -> str:
    """Return the protocol's lowercase SHA-256 representation."""
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> bytes:
    """Serialize a trace payload deterministically without I/O."""
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


def build_trace_bound_resolution_receipt(
    receipt: Mapping[str, Any],
    *,
    status: str,
    raw_capability: Optional[Mapping[str, Any]],  # noqa: UP045 -- Python 3.9 contract
    selector: Mapping[str, Any],
    binding: Mapping[str, Any],
    projection_metadata: Optional[Mapping[str, Any]],  # noqa: UP045 -- Python 3.9 contract
) -> dict[str, Any]:
    """Bind one resolved projection receipt without authorizing execution."""
    if status == "not_found":
        raise TraceBindingError("resolution_not_found")
    if status == "ambiguous":
        raise TraceBindingError("resolution_ambiguous")
    if status != "resolved" or raw_capability is None:
        raise TraceBindingError("resolution_not_exactly_resolved")
    if set(selector) != {"capability_id"} or selector.get("capability_id") != raw_capability.get("id"):
        raise TraceBindingError("binding_requires_exact_id")
    if not isinstance(projection_metadata, Mapping) or any(
        projection_metadata.get(key) != expected for key, expected in CANONICAL_REGISTRY_METADATA.items()
    ):
        raise TraceBindingError("source_unprovable")

    canonical_binding = validate_trace_binding(binding)
    adapter = raw_capability.get("adapter")
    capability = {
        "id": str(raw_capability.get("id", "")),
        "kind": str(raw_capability.get("kind", "")),
        "adapter_kind": str(adapter.get("kind", "")) if isinstance(adapter, Mapping) else "",
        "native_owner": _native_owner(str(raw_capability.get("kind", ""))),
    }
    _validate_capability_binding(capability)
    registry_digest = str(receipt.get("registry_digest", ""))
    trace = _trace_projection(canonical_binding, capability, registry_digest)
    bound = dict(receipt)
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
