"""B4-D1 frozen v1 native execution receipt and replay contract tests."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "lib") not in sys.path:
    sys.path.insert(0, str(ROOT / "lib"))

import capability_native_execution_receipt as native  # noqa: E402


def _digest(seed: str) -> str:
    return "sha256:" + seed * 64


def _binding() -> dict[str, str]:
    return {
        "correlation_id": "corr-b4d-001",
        "workflow_run_id": "run-b4d-001",
        "packet_id": "packet-b4d-001",
        "packet_hash": _digest("a"),
        "assignment_id": "assignment-b4d-001",
        "dispatch_id": "dispatch-b4d-001",
        "actor_id": "blueprint-native-execution-receipts",
        "delivery_attempt_id": "b4-d-20260823-01",
    }


def _material(
    *,
    capability_id: str = "mcp-tool:omo:inspect",
    capability_kind: str = "mcp_tool",
    effect_classification: str = "effectful",
) -> dict[str, Any]:
    return native.build_native_execution_material(
        binding=_binding(),
        capability={"kind": capability_kind, "id": capability_id},
        inspection={"receipt_digest": _digest("1"), "source_digest": _digest("2")},
        operation_id="inspect",
        request_digest=_digest("3"),
        admission={
            "receipt_digest": _digest("4"),
            "admission_id": "admission-b4d-001",
            "step_run_id": "step-b4d-001",
            "worker": {"status": "bound", "id": "worker-b4d-001"},
        },
        authorization_source="mcp-pep",
        effect_classification=effect_classification,
        execution_attempt=1,
    )


def _cleanup(
    material: Optional[dict[str, Any]] = None,  # noqa: UP045 -- Python 3.9 contract
    *,
    status: str = "proved",
) -> dict[str, Any]:
    bound = material or _material()
    proved = status == "proved"
    return native.build_native_cleanup_proof(
        capability_kind=bound["capability"]["kind"],
        invocation_id=native.derive_invocation_id(bound),
        ownership_scope="mcp_proxy_entry",
        baseline_digest=_digest("b"),
        terminal_digest=_digest("b") if proved else _digest("c"),
        measurements={
            "owned_lock_count": 0 if proved else 1,
            "reference_count_delta": 0,
            "connection_created": True,
            "connection_disconnected": True,
            "owned_residue_count": 0,
        },
        status=status,
        failure_code=None if proved else "cleanup_unproven",
    )


def _action(status: str) -> dict[str, Any]:
    if status == "terminal":
        return {"status": status, "id": "action-b4d-001", "digest": _digest("d")}
    return {"status": status, "id": None, "digest": None}


def _receipt(
    *,
    effect_classification: str = "effectful",
    transport_state: str = "confirmed",
) -> dict[str, Any]:
    material = _material(effect_classification=effect_classification)
    if transport_state == "confirmed":
        outcome, failure_code, result_digest = "succeeded", None, _digest("6")
    elif transport_state == "failed":
        outcome, failure_code, result_digest = "failed", "native_invocation_failed", _digest("6")
    else:
        outcome, failure_code, result_digest = "unknown", None, None
    action_status = "missing" if transport_state == "uncertain" else (
        "terminal" if effect_classification == "effectful" else "not_applicable"
    )
    cleanup = _cleanup(material, status="unproven" if transport_state == "uncertain" else "proved")
    return native.build_native_execution_receipt(
        material=material,
        transport_state=transport_state,
        outcome=outcome,
        failure_code=failure_code,
        result_digest=result_digest,
        action_receipt=_action(action_status),
        cleanup_proof=cleanup,
    )


def _rehash(receipt: dict[str, Any]) -> None:
    receipt["receipt_digest"] = native.canonical_digest(
        {key: value for key, value in receipt.items() if key != "receipt_digest"}
    )


def test_material_v1_binds_canonical_b4b_identity_and_complete_native_inputs() -> None:
    material = _material()
    assert material["schema"] == "native-execution-material/v1"
    assert material["binding"] == _binding()
    assert material["capability"] == {"kind": "mcp_tool", "id": "mcp-tool:omo:inspect"}
    assert material["inspection"] == {"receipt_digest": _digest("1"), "source_digest": _digest("2")}
    assert material["admission"]["worker"] == {"status": "bound", "id": "worker-b4d-001"}
    assert native.validate_native_execution_material(material) == material
    assert native.derive_invocation_id(material) == native.derive_invocation_id(copy.deepcopy(material))


@pytest.mark.parametrize(
    ("capability", "authorization_source", "worker", "ownership_scope"),
    [
        (
            {"kind": "workflow", "id": "workflow:governance-audit"},
            "workflow-controller",
            {"status": "not_applicable", "id": None},
            "workflow_child_run",
        ),
        (
            {"kind": "bos_service", "id": "bos-service:bos://governance/demo"},
            "bos-pep",
            {"status": "bound", "id": "worker-bos-001"},
            "bos_action_lease",
        ),
    ],
)
def test_workflow_and_bos_material_and_cleanup_scopes_are_native_kind_bound(
    capability: dict[str, str],
    authorization_source: str,
    worker: dict[str, Any],
    ownership_scope: str,
) -> None:
    material = native.build_native_execution_material(
        binding=_binding(),
        capability=capability,
        inspection={"receipt_digest": _digest("1"), "source_digest": _digest("2")},
        operation_id="invoke",
        request_digest=_digest("3"),
        admission={
            "receipt_digest": _digest("4"),
            "admission_id": "admission-native-001",
            "step_run_id": "step-native-001",
            "worker": worker,
        },
        authorization_source=authorization_source,
        effect_classification="effectful",
        execution_attempt=1,
    )
    cleanup = native.build_native_cleanup_proof(
        capability_kind=capability["kind"],
        invocation_id=native.derive_invocation_id(material),
        ownership_scope=ownership_scope,
        baseline_digest=_digest("b"),
        terminal_digest=_digest("b"),
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
    assert cleanup["capability_kind"] == capability["kind"]
    assert cleanup["ownership_scope"] == ownership_scope


@pytest.mark.parametrize(
    ("capability_id", "kind", "code"),
    [
        ("skill:workflow:mini", "skill", "native_execution_unprovable"),
        ("mcp-server:omo", "mcp_server", "native_execution_unprovable"),
        ("mcp-tool:omo", "mcp_tool", "native_route_unprovable"),
        ("unknown:thing", "unknown", "native_route_unprovable"),
        ("workflow:/Users/private", "workflow", "native_route_unprovable"),
        ("mcp-tool:omo:inspect", "workflow", "native_route_unprovable"),
    ],
)
def test_material_selector_and_executable_kind_policy_fail_closed(
    capability_id: str, kind: str, code: str
) -> None:
    with pytest.raises(native.NativeExecutionReceiptError, match=code):
        _material(capability_id=capability_id, capability_kind=kind)


@pytest.mark.parametrize(
    ("capability", "wrong_source"),
    [
        ({"kind": "workflow", "id": "workflow:governance-audit"}, "mcp-pep"),
        ({"kind": "workflow", "id": "workflow:governance-audit"}, "bos-pep"),
        ({"kind": "mcp_tool", "id": "mcp-tool:omo:inspect"}, "workflow-controller"),
        ({"kind": "mcp_tool", "id": "mcp-tool:omo:inspect"}, "bos-pep"),
        ({"kind": "bos_service", "id": "bos-service:bos://governance/demo"}, "workflow-controller"),
        ({"kind": "bos_service", "id": "bos-service:bos://governance/demo"}, "mcp-pep"),
    ],
)
def test_authorization_source_is_exactly_bound_to_native_kind_even_after_rebuild(
    capability: dict[str, str], wrong_source: str
) -> None:
    with pytest.raises(native.NativeExecutionReceiptError, match="authorization_required"):
        native.build_native_execution_material(
            binding=_binding(),
            capability=capability,
            inspection={"receipt_digest": _digest("1"), "source_digest": _digest("2")},
            operation_id="invoke",
            request_digest=_digest("3"),
            admission={
                "receipt_digest": _digest("4"),
                "admission_id": "admission-native-001",
                "step_run_id": "step-native-001",
                "worker": {"status": "bound", "id": "worker-native-001"},
            },
            authorization_source=wrong_source,
            effect_classification="effectful",
            execution_attempt=1,
        )


def test_material_rejects_omission_tamper_worker_and_attempt_shape() -> None:
    material = _material()
    cases = [
        (lambda item: item.pop("inspection"), "native_route_unprovable"),
        (lambda item: item["binding"].update({"prompt": "secret"}), "native_route_unprovable"),
        (lambda item: item["inspection"].update({"source_digest": []}), "inspection_receipt_invalid"),
        (lambda item: item["admission"]["worker"].update({"status": "bound", "id": None}), "admission_receipt_invalid"),
        (lambda item: item.update({"execution_attempt": True}), "native_route_unprovable"),
        (lambda item: item.update({"execution_attempt": 0}), "native_route_unprovable"),
        (lambda item: item.update({"operation_id": "/private/run"}), "native_route_unprovable"),
    ]
    for mutation, code in cases:
        changed = copy.deepcopy(material)
        mutation(changed)
        with pytest.raises(native.NativeExecutionReceiptError, match=code):
            native.validate_native_execution_material(changed)


def test_every_material_component_changes_the_invocation_identity_without_collision() -> None:
    base = _material()
    identities = {native.derive_invocation_id(base)}
    mutations = [
        lambda item: item["binding"].update({"dispatch_id": "dispatch-b4d-002"}),
        lambda item: item["inspection"].update({"source_digest": _digest("7")}),
        lambda item: item.update({"operation_id": "inspect-again"}),
        lambda item: item.update({"request_digest": _digest("8")}),
        lambda item: item["admission"].update({"admission_id": "admission-b4d-002"}),
        lambda item: item.update({"effect_classification": "read_only"}),
        lambda item: item.update({"execution_attempt": 2}),
    ]
    for mutation in mutations:
        changed = copy.deepcopy(base)
        mutation(changed)
        identities.add(native.derive_invocation_id(changed))
    assert len(identities) == len(mutations) + 1


def test_pre_cas_replay_never_grants_a_call_and_started_is_always_uncertain() -> None:
    material = _material()
    invocation_id = native.derive_invocation_id(material)
    assert native.classify_native_execution_replay(None, material) == {
        "classification": "needs_durable_start",
        "call_allowed": False,
        "invocation_id": invocation_id,
    }
    marker = native.build_native_execution_marker(material)
    assert marker["schema"] == "native-execution-marker/v1"
    with pytest.raises(native.NativeExecutionReceiptError, match="transport_uncertain"):
        native.classify_native_execution_replay(marker, material)

    foreign_material = copy.deepcopy(material)
    foreign_material["execution_attempt"] = 2
    foreign_marker = native.build_native_execution_marker(foreign_material)
    with pytest.raises(native.NativeExecutionReceiptError, match="execution_conflict"):
        native.classify_native_execution_replay(foreign_marker, material)

    tampered = copy.deepcopy(marker)
    tampered["material_digest"] = _digest("f")
    with pytest.raises(native.NativeExecutionReceiptError, match="native_execution_unprovable"):
        native.validate_native_execution_marker(tampered)


def test_completed_replay_returns_existing_and_material_drift_conflicts_without_call() -> None:
    material = _material()
    receipt = _receipt()
    assert native.classify_native_execution_replay(receipt, material) == {
        "classification": "existing",
        "call_allowed": False,
        "invocation_id": native.derive_invocation_id(material),
        "receipt": receipt,
    }
    drifted = copy.deepcopy(material)
    drifted["execution_attempt"] = 2
    with pytest.raises(native.NativeExecutionReceiptError, match="execution_conflict"):
        native.classify_native_execution_replay(receipt, drifted)


def test_cleanup_proved_and_unproven_v1_are_semantically_distinct() -> None:
    proved, unproven = _cleanup(), _cleanup(status="unproven")
    assert proved["status"] == "proved" and proved["failure_code"] is None
    assert proved["baseline_digest"] == proved["terminal_digest"]
    assert proved["measurements"] == {
        "owned_lock_count": 0,
        "reference_count_delta": 0,
        "connection_created": True,
        "connection_disconnected": True,
        "owned_residue_count": 0,
    }
    assert unproven["status"] == "unproven" and unproven["failure_code"] == "cleanup_unproven"
    assert native.validate_native_cleanup_proof(proved) == proved
    assert native.validate_native_cleanup_proof(unproven) == unproven


@pytest.mark.parametrize("invalid", [True, 1.0, "0", None, [], {}])
def test_cleanup_measurement_ints_are_bounded_non_bool_and_never_leak_typeerror(invalid: object) -> None:
    proof = _cleanup()
    proof["measurements"]["owned_lock_count"] = invalid
    _rehash(proof)
    with pytest.raises(native.NativeExecutionReceiptError, match="cleanup_unproven"):
        native.validate_native_cleanup_proof(proof)


def test_cleanup_proved_requires_zero_owned_residue_and_complete_connection_teardown() -> None:
    for field, value in [
        ("owned_lock_count", 1),
        ("reference_count_delta", 1),
        ("owned_residue_count", 1),
        ("connection_disconnected", False),
    ]:
        proof = _cleanup()
        proof["measurements"][field] = value
        _rehash(proof)
        with pytest.raises(native.NativeExecutionReceiptError, match="cleanup_unproven"):
            native.validate_native_cleanup_proof(proof)


@pytest.mark.parametrize(
    ("effect", "transport", "action_status", "outcome"),
    [
        ("read_only", "confirmed", "not_applicable", "succeeded"),
        ("read_only", "failed", "not_applicable", "failed"),
        ("effectful", "confirmed", "terminal", "succeeded"),
        ("effectful", "failed", "terminal", "failed"),
        ("read_only", "uncertain", "missing", "unknown"),
        ("effectful", "uncertain", "missing", "unknown"),
    ],
)
def test_transport_action_cross_product_is_explicit(
    effect: str, transport: str, action_status: str, outcome: str
) -> None:
    receipt = _receipt(effect_classification=effect, transport_state=transport)
    assert receipt["transport_state"] == transport
    assert receipt["action_receipt"]["status"] == action_status
    assert receipt["outcome"]["status"] == outcome
    assert receipt["states"] == {"invoked": True, "evidenced": False, "independently_verified": False}
    assert native.validate_native_execution_receipt(receipt) == receipt


@pytest.mark.parametrize(
    ("effect", "transport", "action_status"),
    [
        ("effectful", "confirmed", "missing"),
        ("effectful", "failed", "not_applicable"),
        ("read_only", "confirmed", "terminal"),
        ("effectful", "uncertain", "terminal"),
    ],
)
def test_transport_action_invalid_cross_product_is_rejected(
    effect: str, transport: str, action_status: str
) -> None:
    receipt = _receipt(effect_classification=effect, transport_state=transport)
    receipt["action_receipt"] = _action(action_status)
    _rehash(receipt)
    with pytest.raises(native.NativeExecutionReceiptError, match="execution_evidence_missing"):
        native.validate_native_execution_receipt(receipt)


def test_action_and_cleanup_digests_bind_the_nested_receipts() -> None:
    receipt = _receipt()
    assert receipt["cleanup_digest"] == receipt["cleanup_proof"]["receipt_digest"]
    cleanup_tamper = copy.deepcopy(receipt)
    cleanup_tamper["cleanup_digest"] = _digest("9")
    _rehash(cleanup_tamper)
    with pytest.raises(native.NativeExecutionReceiptError, match="cleanup_unproven"):
        native.validate_native_execution_receipt(cleanup_tamper)
    action_tamper = copy.deepcopy(receipt)
    action_tamper["action_receipt"]["digest"] = []
    _rehash(action_tamper)
    with pytest.raises(native.NativeExecutionReceiptError, match="execution_evidence_missing"):
        native.validate_native_execution_receipt(action_tamper)


@pytest.mark.parametrize("invalid", [0, 1, "true", None, [], {}])
def test_invoked_state_is_exact_bool_and_other_states_never_promote(invalid: object) -> None:
    receipt = _receipt()
    receipt["states"]["invoked"] = invalid
    _rehash(receipt)
    with pytest.raises(native.NativeExecutionReceiptError, match="native_execution_unprovable"):
        native.validate_native_execution_receipt(receipt)
    for field in ("evidenced", "independently_verified"):
        promoted = _receipt()
        promoted["states"][field] = invalid
        _rehash(promoted)
        with pytest.raises(native.NativeExecutionReceiptError, match="value_promotion_forbidden"):
            native.validate_native_execution_receipt(promoted)


@pytest.mark.parametrize("field", ["humanVerdict", "decisionOutcome", "valueMetric", "personalScore"])
def test_camel_case_value_promotion_is_rejected_after_rehash(field: str) -> None:
    receipt = _receipt()
    receipt[field] = "accepted"
    _rehash(receipt)
    with pytest.raises(native.NativeExecutionReceiptError, match="value_promotion_forbidden"):
        native.validate_native_execution_receipt(receipt)


@pytest.mark.parametrize(
    "failure_code",
    [
        "admission_receipt_invalid",
        "execution_conflict",
        "cleanup_unproven",
        "execution_evidence_missing",
        "value_promotion_forbidden",
    ],
)
def test_completed_native_outcome_rejects_other_phase_failure_codes(failure_code: str) -> None:
    receipt = _receipt(transport_state="failed")
    receipt["outcome"]["failure_code"] = failure_code
    _rehash(receipt)
    with pytest.raises(native.NativeExecutionReceiptError, match="native_invocation_failed"):
        native.validate_native_execution_receipt(receipt)


def test_completed_receipt_rejects_omission_unknown_fields_and_raw_result_after_rehash() -> None:
    for mutation in [
        lambda item: item.pop("cleanup_digest"),
        lambda item: item.update({"raw_result": "secret"}),
        lambda item: item["action_receipt"].update({"provider": "secret"}),
    ]:
        receipt = _receipt()
        mutation(receipt)
        _rehash(receipt)
        with pytest.raises(native.NativeExecutionReceiptError):
            native.validate_native_execution_receipt(receipt)


@pytest.mark.parametrize("invalid", [[], ["x"], {"x": []}])
def test_public_validators_reject_non_mapping_and_non_hashable_shapes_without_typeerror(invalid: object) -> None:
    validators = [
        native.validate_native_execution_material,
        native.validate_native_cleanup_proof,
        native.validate_native_execution_receipt,
        native.validate_native_execution_marker,
    ]
    for validator in validators:
        with pytest.raises(native.NativeExecutionReceiptError):
            validator(invalid)


def test_nested_non_hashable_enum_values_never_leak_typeerror() -> None:
    material = _material()
    for field in ("authorization_source", "effect_classification"):
        changed = copy.deepcopy(material)
        changed[field] = []
        with pytest.raises(native.NativeExecutionReceiptError):
            native.validate_native_execution_material(changed)

    cleanup = _cleanup()
    cleanup["capability_kind"] = []
    _rehash(cleanup)
    with pytest.raises(native.NativeExecutionReceiptError):
        native.validate_native_cleanup_proof(cleanup)

    receipt = _receipt()
    receipt["transport_state"] = []
    _rehash(receipt)
    with pytest.raises(native.NativeExecutionReceiptError):
        native.validate_native_execution_receipt(receipt)

    receipt = _receipt()
    receipt["action_receipt"]["status"] = []
    _rehash(receipt)
    with pytest.raises(native.NativeExecutionReceiptError):
        native.validate_native_execution_receipt(receipt)
