"""Cross-provider attempt receipt contract for the blueprint worker transports."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "provider_conformance_contract",
    ROOT / "bin/plan/bet-ledger.py",
)
assert SPEC and SPEC.loader
contract = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = contract
SPEC.loader.exec_module(contract)


def _binding() -> dict[str, str]:
    return {
        "run_id": "20260821T111433Z-bet-execution-967f03e6",
        "packet_id": "WP-BET-Y1Q3-T4-01",
        "packet_hash": "sha256:" + "a" * 64,
        "instruction_digest": "sha256:" + "b" * 64,
    }


def _attempt(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "provider_id": "omlxc",
        "transport": "pi_cli",
        "route_ref": "bos://compute/aetherforge/infer",
        "binding_receipt": _binding(),
        "attempt_key": "pi-trial-001",
        "state": "succeeded",
        "evidence_digest": "sha256:" + "c" * 64,
        "workspace_admission": "not_required_read_only",
    }
    values.update(overrides)
    return contract.build_provider_attempt_receipt(**values)


def test_provider_attempt_digest_is_canonical_and_tamper_evident() -> None:
    receipt = _attempt()
    reordered = {key: receipt[key] for key in reversed(receipt)}

    assert contract.provider_attempt_digest(reordered) == receipt["receipt_digest"]
    assert contract.validate_provider_attempt_receipt(reordered) == receipt

    tampered = copy.deepcopy(receipt)
    tampered["route_ref"] = "direct-provider-fallback"
    with pytest.raises(contract.ProviderConformanceError, match="PROVIDER_ATTEMPT_ROUTE_REJECTED"):
        contract.validate_provider_attempt_receipt(tampered)


@pytest.mark.parametrize("transport", ["pi_cli", "omp_cli"])
def test_local_read_only_transports_require_aetherforge_route(transport: str) -> None:
    receipt = _attempt(transport=transport, attempt_key=f"{transport}-001")
    assert receipt["authority"] == {
        "operation_level": "L0",
        "workspace_admission": "not_required_read_only",
        "write_scope": "none",
    }

    with pytest.raises(contract.ProviderConformanceError, match="PROVIDER_ATTEMPT_ROUTE_REJECTED"):
        _attempt(transport=transport, route_ref="http://127.0.0.1:9290/v1")


def test_writer_transport_requires_verified_independent_clone() -> None:
    values = {
        "provider_id": "codex",
        "transport": "codex_exec",
        "route_ref": None,
        "binding_receipt": _binding(),
        "attempt_key": "codex-001",
        "state": "succeeded",
        "evidence_digest": "sha256:" + "d" * 64,
    }
    with pytest.raises(contract.ProviderConformanceError, match="PROVIDER_ATTEMPT_CLONE_REQUIRED"):
        contract.build_provider_attempt_receipt(
            **values,
            workspace_admission="linked_worktree",
        )

    receipt = contract.build_provider_attempt_receipt(
        **values,
        workspace_admission="verified_independent_clone",
    )
    assert receipt["authority"]["write_scope"] == "bounded"


def test_failed_quota_attempt_is_explicit_and_fallback_has_new_lineage() -> None:
    failed = _attempt(
        attempt_key="pi-quota-001",
        state="failed",
        error_code="provider_quota_exhausted",
        evidence_digest="sha256:" + "e" * 64,
    )
    fallback = _attempt(
        provider_id="codex",
        transport="codex_exec",
        route_ref=None,
        attempt_key="codex-fallback-001",
        workspace_admission="verified_independent_clone",
        evidence_digest="sha256:" + "f" * 64,
        previous_attempt=failed,
    )

    assert failed["outcome"] == "failed"
    assert failed["error_code"] == "provider_quota_exhausted"
    assert fallback["attempt_id"] != failed["attempt_id"]
    assert fallback["previous_attempt_id"] == failed["attempt_id"]
    assert contract.validate_provider_attempt_transition(failed, fallback) == fallback


def test_provider_switch_without_explicit_failed_lineage_is_rejected() -> None:
    previous = _attempt(attempt_key="pi-001")
    current = _attempt(
        provider_id="codex",
        transport="codex_exec",
        route_ref=None,
        attempt_key="codex-001",
        workspace_admission="verified_independent_clone",
    )

    with pytest.raises(contract.ProviderConformanceError, match="PROVIDER_ATTEMPT_LINEAGE_REQUIRED"):
        contract.validate_provider_attempt_transition(previous, current)


def test_awaiting_human_action_is_a_hard_fence_not_a_fallback_source() -> None:
    awaiting = _attempt(
        provider_id="codex",
        transport="orca_manual_break_glass",
        route_ref=None,
        attempt_key="orca-dispatch-001",
        state="awaiting_human_action",
        evidence_digest="sha256:" + "1" * 64,
        workspace_admission="verified_independent_clone",
    )
    assert awaiting["outcome"] == "not_proven"
    assert awaiting["human_action_required"] is True
    assert awaiting["completion_observed"] is False

    with pytest.raises(contract.ProviderConformanceError, match="PROVIDER_ATTEMPT_HUMAN_FENCE"):
        _attempt(
            attempt_key="pi-after-orca",
            previous_attempt=awaiting,
        )


def test_orca_settled_observation_does_not_claim_provider_success() -> None:
    awaiting = _attempt(
        provider_id="codex",
        transport="orca_manual_break_glass",
        route_ref=None,
        attempt_key="orca-dispatch-002",
        state="awaiting_human_action",
        evidence_digest="sha256:" + "1" * 64,
        workspace_admission="verified_independent_clone",
    )
    receipt = _attempt(
        provider_id="codex",
        transport="orca_manual_break_glass",
        route_ref=None,
        attempt_key="orca-dispatch-002",
        state="settled_observed",
        evidence_digest="sha256:" + "2" * 64,
        workspace_admission="verified_independent_clone",
        previous_attempt=awaiting,
    )

    assert receipt["attempt_id"] == awaiting["attempt_id"]
    assert receipt["revision"] == 2
    assert receipt["previous_receipt_digest"] == awaiting["receipt_digest"]
    assert receipt["outcome"] == "observed_not_adjudicated"
    assert receipt["human_action_required"] is True
    assert receipt["completion_observed"] is True
    assert contract.validate_provider_attempt_transition(awaiting, receipt) == receipt


def test_same_attempt_identity_cannot_be_replayed_with_changed_evidence() -> None:
    original = _attempt()
    replay = copy.deepcopy(original)
    replay["evidence_digest"] = "sha256:" + "9" * 64
    replay["receipt_digest"] = contract.provider_attempt_digest(replay)

    with pytest.raises(contract.ProviderConformanceError, match="PROVIDER_ATTEMPT_REPLAY_MISMATCH"):
        contract.validate_provider_attempt_transition(original, replay)


def test_provider_attempt_receipt_rejects_non_allowlisted_or_sensitive_fields() -> None:
    for field, value in (
        ("prompt", "secret task"),
        ("api_key", "secret"),
        ("workspace_root", "/Users/example/private-clone"),
        ("terminal_handle", "term-001"),
    ):
        receipt = _attempt()
        receipt[field] = value
        receipt["receipt_digest"] = contract.provider_attempt_digest(receipt)
        with pytest.raises(contract.ProviderConformanceError, match="PROVIDER_ATTEMPT_SHAPE_INVALID"):
            contract.validate_provider_attempt_receipt(receipt)
