"""Pure builder and replay validator for B4-C inspection receipts."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

from capability_native_sources import NativeInspectionError
from capability_trace_binding import TRACE_BINDING_SCHEMA, _canonical_json, _digest, validate_trace_binding

INSPECTION_SCHEMA = "native-capability-inspection-receipt/v1"
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_NATIVE_ID = re.compile(r"^[A-Za-z0-9._:@/-]{1,512}$")
SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]{1,256}$")
SUPPORTED_KINDS = {
    "skill": "skill",
    "workflow": "workflow",
    "mcp-server": "mcp_server",
    "mcp-tool": "mcp_tool",
    "bos-service": "bos_service",
}
SOURCE_SEMANTICS = {
    "skill": ("skill-markdown-frontmatter/v1", "frontmatter_exact_name"),
    "workflow": ("agent-workflow-canonical-yaml/v1", "canonical_workflow_exact_id"),
    "mcp-server": ("python-ast-fastmcp/v1", "python_ast_static_declaration"),
    "mcp-tool": ("python-ast-fastmcp/v1", "python_ast_static_declaration"),
    "bos-service": ("agora-bos-services-yaml/v1", "canonical_bos_exact_uri"),
}


def _fail(code: str) -> None:
    raise NativeInspectionError(code)


def parse_native_selector(capability_id: str) -> tuple[str, str, str]:
    if not isinstance(capability_id, str) or ":" not in capability_id:
        _fail("invalid_selector")
    prefix, native_id = capability_id.split(":", 1)
    kind = SUPPORTED_KINDS.get(prefix)
    if kind is None or not native_id or not SAFE_NATIVE_ID.fullmatch(native_id) or ".." in native_id:
        _fail("invalid_selector")
    if prefix == "bos-service" and not native_id.startswith("bos://"):
        _fail("invalid_selector")
    if prefix == "skill" and not all(SAFE_SEGMENT.fullmatch(part) for part in native_id.split(":")):
        _fail("invalid_selector")
    if prefix in {"workflow", "mcp-server"} and not SAFE_SEGMENT.fullmatch(native_id):
        _fail("invalid_selector")
    if prefix == "mcp-tool":
        server_id, separator, tool_id = native_id.partition(":")
        if not separator or not SAFE_SEGMENT.fullmatch(server_id) or not SAFE_SEGMENT.fullmatch(tool_id):
            _fail("invalid_selector")
    return prefix, kind, native_id


def native_kind_requires_projection(capability_id: str) -> bool:
    prefix, _kind, _native_id = parse_native_selector(capability_id)
    return prefix not in {"skill", "workflow"}


def _expected_source_ref(prefix: str, native_id: str) -> Optional[str]:  # noqa: UP045 -- Python 3.9 contract
    if prefix == "skill":
        return f".agents/skills/{native_id}/SKILL.md"
    if prefix == "workflow":
        return f".omo/_truth/registry/agent-workflows/workflows/{native_id}.yaml"
    if prefix == "bos-service":
        return "projects/agora/etc/bos-services.yaml"
    return None


def _validate_source_semantics(receipt: Mapping[str, Any], prefix: str, native_id: str) -> None:
    source_schema, proof_method = SOURCE_SEMANTICS[prefix]
    if receipt.get("source_schema") != source_schema:
        _fail("source_schema_unsupported")
    if receipt.get("proof") != {"method": proof_method, "strength": "strong"}:
        _fail("source_unprovable")
    source_ref = receipt.get("source_ref")
    if (
        not isinstance(source_ref, str)
        or Path(source_ref).is_absolute()
        or source_ref.startswith(("~", "\\"))
        or "\\" in source_ref
        or any(ord(char) < 32 for char in source_ref)
        or any(part in {"", ".", ".."} for part in Path(source_ref).parts)
    ):
        _fail("dangling_reference")
    expected = _expected_source_ref(prefix, native_id)
    if expected is not None and source_ref != expected:
        _fail("dangling_reference")
    if prefix in {"mcp-server", "mcp-tool"} and not source_ref.endswith(".py"):
        _fail("dangling_reference")


def _validate_native_version(receipt: Mapping[str, Any]) -> None:
    status = receipt.get("native_version_status")
    version = receipt.get("native_version")
    if status == "unprovable":
        if version is not None:
            _fail("source_schema_unsupported")
        return
    if status != "proved" or not isinstance(version, str):
        _fail("source_schema_unsupported")
    if not version or version.strip() != version or len(version) > 64 or any(ord(char) < 32 for char in version):
        _fail("source_schema_unsupported")


def build_native_inspection_receipt(
    *, capability_id: str, binding: Mapping[str, str], proof: Mapping[str, Any], upstream: Mapping[str, Any]
) -> dict[str, Any]:
    _prefix, kind, _native_id = parse_native_selector(capability_id)
    receipt: dict[str, Any] = {
        "schema": INSPECTION_SCHEMA,
        "status": "inspected",
        "selector_digest": _digest(_canonical_json({"capability_id": capability_id})),
        "binding_schema": TRACE_BINDING_SCHEMA,
        "binding": dict(binding),
        "capability": {"kind": kind, "id": capability_id},
        "source_ref": proof["source_ref"],
        "source_digest": _digest(proof["content"]),
        "source_schema": proof["source_schema"],
        "proof": proof["proof"],
        "upstream_resolution": dict(upstream),
        "native_version": proof["native_version"],
        "native_version_status": proof["native_version_status"],
        "read_only": True,
        "executed": False,
        "provider_called": False,
        "invoked": False,
        "value_indicator_policy": False,
        "admission": {"evaluated": False, "decision": "not_evaluated"},
        "authorization": {"evaluated": False, "decision": "not_evaluated"},
        "evidence": {"recorded": False, "status": "not_evaluated"},
        "verification": {"performed": False, "status": "not_evaluated"},
    }
    receipt["receipt_digest"] = _digest(_canonical_json(receipt))
    return validate_native_inspection_receipt(receipt)


def validate_native_inspection_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(receipt, Mapping):
        _fail("source_schema_unsupported")
    required = {
        "schema", "status", "selector_digest", "binding_schema", "binding", "capability",
        "source_ref", "source_digest", "source_schema", "proof", "upstream_resolution",
        "native_version", "native_version_status", "read_only", "executed", "provider_called",
        "invoked", "value_indicator_policy", "admission", "authorization", "evidence",
        "verification", "receipt_digest",
    }
    if set(receipt) != required or receipt.get("schema") != INSPECTION_SCHEMA or receipt.get("status") != "inspected":
        _fail("source_schema_unsupported")
    capability = receipt.get("capability")
    if not isinstance(capability, Mapping) or set(capability) != {"kind", "id"}:
        _fail("source_schema_unsupported")
    capability_id = capability.get("id")
    prefix, kind, native_id = parse_native_selector(str(capability_id))
    if capability.get("kind") != kind:
        _fail("source_schema_unsupported")
    if receipt.get("selector_digest") != _digest(_canonical_json({"capability_id": capability_id})):
        _fail("source_digest_mismatch")
    if receipt.get("binding_schema") != TRACE_BINDING_SCHEMA:
        _fail("upstream_resolution_invalid")
    try:
        validate_trace_binding(receipt.get("binding", {}))
    except ValueError:
        _fail("upstream_resolution_invalid")
    if not SHA256_RE.fullmatch(str(receipt.get("source_digest") or "")):
        _fail("source_digest_mismatch")
    _validate_source_semantics(receipt, prefix, native_id)
    _validate_native_version(receipt)

    upstream = receipt.get("upstream_resolution")
    if not isinstance(upstream, Mapping):
        _fail("upstream_resolution_invalid")
    if prefix in {"skill", "workflow"}:
        if upstream != {"status": "not_applicable", "reason": "native_kind_not_in_projection"}:
            _fail("upstream_resolution_invalid")
    elif (
        set(upstream) != {"status", "schema", "receipt_digest", "registry_digest"}
        or upstream.get("status") != "verified"
        or upstream.get("schema") != "capability-resolution-receipt/v1"
        or not SHA256_RE.fullmatch(str(upstream.get("receipt_digest") or ""))
        or not SHA256_RE.fullmatch(str(upstream.get("registry_digest") or ""))
    ):
        _fail("upstream_resolution_invalid")
    fixed = {
        "read_only": True,
        "executed": False,
        "provider_called": False,
        "invoked": False,
        "value_indicator_policy": False,
        "admission": {"evaluated": False, "decision": "not_evaluated"},
        "authorization": {"evaluated": False, "decision": "not_evaluated"},
        "evidence": {"recorded": False, "status": "not_evaluated"},
        "verification": {"performed": False, "status": "not_evaluated"},
    }
    if any(receipt.get(field) != value for field, value in fixed.items()):
        _fail("value_promotion_forbidden")
    without_digest = dict(receipt)
    supplied = without_digest.pop("receipt_digest")
    if not SHA256_RE.fullmatch(str(supplied or "")) or supplied != _digest(_canonical_json(without_digest)):
        _fail("source_digest_mismatch")
    return dict(receipt)


def inspection_error_receipt(capability_id: str, failure_code: str) -> dict[str, Any]:
    selector = {"capability_id": capability_id} if isinstance(capability_id, str) else {}
    receipt: dict[str, Any] = {
        "schema": INSPECTION_SCHEMA,
        "status": "rejected",
        "failure_code": failure_code,
        "selector_digest": _digest(_canonical_json(selector)),
        "read_only": True,
        "executed": False,
        "provider_called": False,
        "invoked": False,
        "value_indicator_policy": False,
        "admission": {"evaluated": False, "decision": "not_evaluated"},
        "authorization": {"evaluated": False, "decision": "not_evaluated"},
        "evidence": {"recorded": False, "status": "not_evaluated"},
        "verification": {"performed": False, "status": "not_evaluated"},
    }
    receipt["receipt_digest"] = _digest(_canonical_json(receipt))
    return receipt
