"""Pure contract tests for B4-B resolution trace binding."""

from __future__ import annotations

import ast
import copy
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "lib" / "capability_trace_binding.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capability_trace_binding_fixture", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _binding() -> dict[str, str]:
    return {
        "correlation_id": "corr-b4b-001",
        "workflow_run_id": "run-b4b-001",
        "packet_id": "packet-b4b-001",
        "packet_hash": "sha256:" + "a" * 64,
        "assignment_id": "assignment-b4b-001",
        "dispatch_id": "dispatch-b4b-001",
        "actor_id": "blueprint-trace-binding",
        "delivery_attempt_id": "b4-b-20260823-01",
    }


def _raw_capability() -> dict[str, object]:
    return {
        "id": "mcp-tool:omo:inspect",
        "kind": "mcp_tool",
        "adapter": {"kind": "mcp_native", "target": "omo/inspect"},
    }


def _legacy_receipt(module: ModuleType) -> dict[str, object]:
    capability_id = "mcp-tool:omo:inspect"
    return {
        "schema": "capability-resolution-receipt/v1",
        "status": "resolved",
        "registry_digest": module._digest(b"canonical-projection"),
        "selector_digest": module._digest(module._canonical_json({"capability_id": capability_id})),
        "match_count": 1,
        "candidate_id_digests": [module._digest(capability_id.encode("utf-8"))],
        "admission": {"required": True, "decision": "not_evaluated"},
        "invocation": {
            "allowed": False,
            "route": "native_adapter_only",
            "reason": "admission_not_evaluated",
        },
        "capability_id": capability_id,
        "adapter": {"kind": "mcp_native", "target": "omo/inspect"},
    }


def _bound_receipt(module: ModuleType) -> dict[str, object]:
    return module.build_trace_bound_resolution_receipt(
        _legacy_receipt(module),
        status="resolved",
        raw_capability=_raw_capability(),
        selector={"capability_id": "mcp-tool:omo:inspect"},
        binding=_binding(),
        projection_metadata=module.CANONICAL_REGISTRY_METADATA,
    )


def test_binding_receipt_is_deterministic_replay_safe_and_value_isolated() -> None:
    module = _load()

    first = _bound_receipt(module)
    second = _bound_receipt(module)

    assert first == second
    assert first["trace_id"].startswith("sha256:")
    assert first["receipt_digest"].startswith("sha256:")
    assert first["resolution_source"] == {
        "authority": "projection",
        "digest": first["registry_digest"],
        "ref": "generated:capability-registry/v1",
    }
    assert first["capability"] == {
        "adapter_kind": "mcp_native",
        "id": "mcp-tool:omo:inspect",
        "kind": "mcp_tool",
        "native_owner": "mcp",
    }
    assert first["states"] == {"evidenced": False, "independently_verified": False, "invoked": False}
    assert first["value_indicator_policy"] is False
    assert module.validate_trace_bound_resolution_receipt(first) == first


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda value: value.update({"prompt": "secret prompt"}), "binding_unknown_fields"),
        (lambda value: value.__setitem__("actor_id", "/Users/private"), "binding_absolute_path_forbidden"),
        (lambda value: value.__setitem__("actor_id", "\\Users\\private"), "binding_absolute_path_forbidden"),
        (lambda value: value.__setitem__("actor_id", "agent with space"), "binding_identifier_invalid"),
        (lambda value: value.__setitem__("assignment_id", "assignment..parent"), "binding_identifier_invalid"),
        (lambda value: value.__setitem__("delivery_attempt_id", "a" * 257), "binding_identifier_invalid"),
        (lambda value: value.__setitem__("packet_hash", "not-a-digest"), "binding_packet_hash_invalid"),
    ],
)
def test_binding_rejects_sensitive_or_noncanonical_identities(mutation, reason) -> None:
    module = _load()
    binding = _binding()
    mutation(binding)

    with pytest.raises(module.TraceBindingError, match=reason):
        module.validate_trace_binding(binding)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda value: value["binding"].__setitem__("dispatch_id", "tampered-dispatch"), "trace_id_mismatch"),
        (lambda value: value.__setitem__("value_indicator_policy", True), "value_promotion_forbidden"),
        (lambda value: value.__setitem__("match_count", 2), "resolution_match_count_invalid"),
        (lambda value: value.__setitem__("candidate_id_digests", []), "resolution_candidate_digest_invalid"),
        (lambda value: value.__setitem__("selector_digest", "sha256:" + "b" * 64), "resolution_selector_digest_invalid"),
        (lambda value: value["capability"].__setitem__("native_owner", "agora"), "capability_semantics_invalid"),
    ],
)
def test_replay_validator_rejects_tampering_even_with_a_recomputed_receipt_digest(mutation, reason) -> None:
    module = _load()
    receipt = copy.deepcopy(_bound_receipt(module))
    mutation(receipt)
    without_digest = dict(receipt)
    without_digest.pop("receipt_digest")
    receipt["receipt_digest"] = module._digest(module._canonical_json(without_digest))

    with pytest.raises(module.TraceBindingError, match=reason):
        module.validate_trace_bound_resolution_receipt(receipt)


def test_replay_validator_rejects_plain_receipt_digest_tampering() -> None:
    module = _load()
    receipt = _bound_receipt(module)
    receipt["receipt_digest"] = "sha256:" + "b" * 64

    with pytest.raises(module.TraceBindingError, match="receipt_digest_mismatch"):
        module.validate_trace_bound_resolution_receipt(receipt)


@pytest.mark.parametrize(
    ("status", "metadata", "reason"),
    [
        ("not_found", None, "resolution_not_found"),
        ("ambiguous", None, "resolution_ambiguous"),
        ("resolved", {"schema": "capability-registry/v1"}, "source_unprovable"),
    ],
)
def test_bound_builder_fails_closed_for_unresolved_or_unproved_sources(status, metadata, reason) -> None:
    module = _load()

    with pytest.raises(module.TraceBindingError, match=reason):
        module.build_trace_bound_resolution_receipt(
            _legacy_receipt(module),
            status=status,
            raw_capability=_raw_capability(),
            selector={"capability_id": "mcp-tool:omo:inspect"},
            binding=_binding(),
            projection_metadata=metadata,
        )


@pytest.mark.parametrize(
    ("mutator", "reason"),
    [
        (lambda value: value.__setitem__("id", "mcp-tool:omo:unsafe command"), "capability_id_invalid"),
        (lambda value: value["adapter"].__setitem__("kind", "bos_native"), "capability_semantics_invalid"),
    ],
)
def test_bound_builder_rejects_unsafe_capability_identity_or_adapter(mutator, reason) -> None:
    module = _load()
    raw_capability = _raw_capability()
    mutator(raw_capability)

    with pytest.raises(module.TraceBindingError, match=reason):
        module.build_trace_bound_resolution_receipt(
            _legacy_receipt(module),
            status="resolved",
            raw_capability=raw_capability,
            selector={"capability_id": raw_capability["id"]},
            binding=_binding(),
            projection_metadata=module.CANONICAL_REGISTRY_METADATA,
        )


def test_library_is_python39_parseable_and_has_no_io_or_runtime_imports() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"), filename=str(MODULE), feature_version=(3, 9))
    imported = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )

    assert imported <= {"__future__", "hashlib", "json", "re", "collections", "typing"}
    assert "open(" not in MODULE.read_text(encoding="utf-8")
