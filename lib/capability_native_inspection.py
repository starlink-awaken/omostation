"""Static, replay-safe native capability inspection for B4-C.

The inspector reads repository authorities and emits source proofs.  It never
imports provider modules, starts a process, opens a socket, or evaluates an
admission/execution policy.  Generated MCP/BOS data is used only as a locator;
the native source must independently prove the selected declaration.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

import yaml
from capability_native_receipt import (
    build_native_inspection_receipt,
    inspection_error_receipt,
    native_kind_requires_projection,
    parse_native_selector,
    validate_native_inspection_receipt,
)
from capability_native_sources import (
    NativeInspectionError,
    parse_fastmcp_authority,
    read_stable_source,
    snapshot_directory_files,
)
from capability_trace_binding import (
    _digest,
    validate_trace_binding,
    validate_trace_bound_resolution_receipt,
)

_read_stable_source = read_stable_source


def _workflow_snapshot(root: Path, source_ref: str):
    return snapshot_directory_files(root, source_ref, suffix=".yaml")

def _fail(code: str) -> None:
    raise NativeInspectionError(code)


def _yaml_mapping(content: bytes) -> Mapping[str, Any]:
    try:
        value = yaml.safe_load(content)
    except (UnicodeDecodeError, yaml.YAMLError):
        _fail("source_schema_unsupported")
    if not isinstance(value, Mapping):
        _fail("source_schema_unsupported")
    return value


def _native_version(source: Mapping[str, Any]) -> tuple[Optional[str], str]:  # noqa: UP045 -- Python 3.9 contract
    value = source.get("version")
    if not isinstance(value, bool) and isinstance(value, (str, int, float)) and str(value).strip() and len(str(value)) <= 64:
        return str(value), "proved"
    return None, "unprovable"


def _inspect_skill(root: Path, native_id: str) -> dict[str, Any]:
    source_ref = f".agents/skills/{native_id}/SKILL.md"
    content = _read_stable_source(root, source_ref)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        _fail("source_schema_unsupported")
    if not text.startswith("---\n"):
        _fail("source_schema_unsupported")
    closing = text.find("\n---\n", 4)
    if closing < 0 or closing > 65536:
        _fail("source_schema_unsupported")
    frontmatter = _yaml_mapping(text[4:closing].encode("utf-8"))
    if frontmatter.get("name") != native_id:
        _fail("dangling_reference")
    version, version_status = _native_version(frontmatter)
    return {
        "source_ref": source_ref,
        "content": content,
        "source_schema": "skill-markdown-frontmatter/v1",
        "proof": {"method": "frontmatter_exact_name", "strength": "strong"},
        "native_version": version,
        "native_version_status": version_status,
    }


def _inspect_workflow(root: Path, native_id: str) -> dict[str, Any]:
    directory_ref = ".omo/_truth/registry/agent-workflows/workflows"
    source_ref = f"{directory_ref}/{native_id}.yaml"
    snapshot_before = _workflow_snapshot(root, directory_ref)
    matches = 0
    content: Optional[bytes] = None  # noqa: UP045 -- Python 3.9 contract
    workflow: Optional[Mapping[str, Any]] = None  # noqa: UP045 -- Python 3.9 contract
    for name, candidate_content in snapshot_before.entries:
        try:
            candidate = _yaml_mapping(candidate_content)
        except NativeInspectionError:
            _fail("source_unprovable")
        if candidate.get("id") == native_id:
            matches += 1
            if name == f"{native_id}.yaml":
                content = candidate_content
                workflow = candidate
    snapshot_after = _workflow_snapshot(root, directory_ref)
    if snapshot_before != snapshot_after:
        _fail("source_digest_mismatch")
    if matches != 1:
        _fail("duplicate_authority_claim" if matches > 1 else "resolution_not_found")
    if content is None or workflow is None:
        _fail("dangling_reference")
    version, version_status = _native_version(workflow)
    return {
        "source_ref": source_ref,
        "content": content,
        "source_schema": "agent-workflow-canonical-yaml/v1",
        "proof": {"method": "canonical_workflow_exact_id", "strength": "strong"},
        "native_version": version,
        "native_version_status": version_status,
    }


def _registry_mcp_rows(registry: Mapping[str, Any], server_id: str) -> list[Mapping[str, Any]]:
    rows = registry.get("mcp_servers")
    if not isinstance(rows, list):
        _fail("source_schema_unsupported")
    return [row for row in rows if isinstance(row, Mapping) and row.get("id") == server_id]


def _inspect_mcp(root: Path, registry: Mapping[str, Any], prefix: str, native_id: str) -> dict[str, Any]:
    server_id, _, tool_id = native_id.partition(":")
    rows = _registry_mcp_rows(registry, server_id)
    if not rows:
        _fail("resolution_not_found")
    if len(rows) != 1:
        _fail("duplicate_authority_claim")
    row = rows[0]
    if row.get("exists") is not True or not isinstance(row.get("file"), str):
        _fail("source_unprovable")
    source_ref = str(row["file"])
    content = _read_stable_source(root, source_ref)
    authority = parse_fastmcp_authority(content, source_ref, server_id)
    static_tools = authority["tools"]
    projected_tools = row.get("tools")
    if not isinstance(projected_tools, list) or not all(isinstance(value, str) for value in projected_tools):
        _fail("source_schema_unsupported")
    if len(projected_tools) != len(set(projected_tools)) or len(static_tools) != len(set(static_tools)):
        _fail("duplicate_authority_claim")
    if set(projected_tools) != set(static_tools):
        _fail("source_unprovable")
    if prefix == "mcp-tool" and tool_id not in static_tools:
        _fail("resolution_not_found")
    return {
        "source_ref": source_ref,
        "content": content,
        "source_schema": "python-ast-fastmcp/v1",
        "proof": {"method": "python_ast_static_declaration", "strength": "strong"},
        "native_version": authority["native_version"],
        "native_version_status": authority["native_version_status"],
    }


def _inspect_bos(root: Path, native_id: str) -> dict[str, Any]:
    source_ref = "projects/agora/etc/bos-services.yaml"
    content = _read_stable_source(root, source_ref)
    catalog = _yaml_mapping(content)
    services = catalog.get("services")
    if not isinstance(services, list):
        _fail("source_schema_unsupported")
    matches = [row for row in services if isinstance(row, Mapping) and row.get("uri") == native_id]
    if not matches:
        _fail("resolution_not_found")
    if len(matches) != 1:
        _fail("duplicate_authority_claim")
    version, version_status = _native_version(catalog)
    return {
        "source_ref": source_ref,
        "content": content,
        "source_schema": "agora-bos-services-yaml/v1",
        "proof": {"method": "canonical_bos_exact_uri", "strength": "strong"},
        "native_version": version,
        "native_version_status": version_status,
    }


def _validate_upstream(
    prefix: str,
    capability_id: str,
    binding: Optional[Mapping[str, Any]],  # noqa: UP045 -- Python 3.9 contract
    resolution_receipt: Optional[Mapping[str, Any]],  # noqa: UP045 -- Python 3.9 contract
    registry_content: bytes,
) -> tuple[dict[str, str], dict[str, Any]]:
    if prefix in {"skill", "workflow"}:
        if binding is None or resolution_receipt is not None:
            _fail("upstream_resolution_required")
        try:
            canonical_binding = validate_trace_binding(binding)
        except ValueError:
            _fail("upstream_resolution_invalid")
        return canonical_binding, {"status": "not_applicable", "reason": "native_kind_not_in_projection"}
    if resolution_receipt is None or binding is not None:
        _fail("upstream_resolution_required")
    try:
        validated = validate_trace_bound_resolution_receipt(resolution_receipt)
    except ValueError:
        _fail("upstream_resolution_invalid")
    capability = validated.get("capability", {})
    expected_kind = "mcp_server" if prefix == "mcp-server" else "mcp_tool" if prefix == "mcp-tool" else "bos_service"
    if capability.get("id") != capability_id or capability.get("kind") != expected_kind:
        _fail("upstream_resolution_invalid")
    registry_digest = _digest(registry_content)
    if validated.get("registry_digest") != registry_digest:
        _fail("source_digest_mismatch")
    return dict(validated["binding"]), {
        "status": "verified",
        "schema": "capability-resolution-receipt/v1",
        "receipt_digest": str(validated["receipt_digest"]),
        "registry_digest": registry_digest,
    }


def inspect_native_capability(
    *,
    root: Path,
    capability_id: str,
    registry: Mapping[str, Any],
    registry_content: bytes,
    binding: Optional[Mapping[str, Any]] = None,  # noqa: UP045 -- Python 3.9 contract
    resolution_receipt: Optional[Mapping[str, Any]] = None,  # noqa: UP045 -- Python 3.9 contract
) -> dict[str, Any]:
    """Inspect one exact native declaration and return a non-execution receipt."""
    prefix, _kind, native_id = parse_native_selector(capability_id)
    canonical_binding, upstream = _validate_upstream(
        prefix, capability_id, binding, resolution_receipt, registry_content
    )
    if prefix == "skill":
        proof = _inspect_skill(root, native_id)
    elif prefix == "workflow":
        proof = _inspect_workflow(root, native_id)
    elif prefix in {"mcp-server", "mcp-tool"}:
        proof = _inspect_mcp(root, registry, prefix, native_id)
    else:
        proof = _inspect_bos(root, native_id)

    return build_native_inspection_receipt(
        capability_id=capability_id,
        binding=canonical_binding,
        proof=proof,
        upstream=upstream,
    )
