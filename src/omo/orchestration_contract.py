"""Thin OMO coordinator for ECOS WorkPacket delivery contracts.

External orchestrators only transport a candidate.  This module deliberately
does not schedule work, start a provider, or own a second workflow state
machine: it validates ECOS contracts and appends the existing Mesh evidence
and verification events.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from ecos.ssot.mof.generated.control.mof_control_models import (
    CompletionManifest as CompletionManifestModel,
)
from ecos.ssot.mof.generated.control.mof_control_models import WorkPacket
from ecos.ssot.tools.work_packet_compiler import (
    VerificationReceipt,
    build_verification_receipt,
    canonicalize,
    compute_packet_hash,
)

from .omo_external_receipt import ExternalReceiptError, record_external_receipt
from .workflow_mesh import WorkflowMeshEventError, WorkflowMeshStore, new_workflow_event


class OrchestrationContractError(ValueError):
    """A candidate cannot be promoted through the delivery contract."""

    def __init__(self, reason: str, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(f"{reason}: {message or reason}")


class OrchestratorAdapter(Protocol):
    """Transport-only boundary; adapters never own Workspace truth."""

    def dispatch(self, packet: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def observe(self, external_task_id: str) -> Mapping[str, Any]: ...

    def interrupt(self, external_task_id: str) -> Mapping[str, Any]: ...

    def collect(self, external_task_id: str) -> Mapping[str, Any]: ...


class KandevFixtureAdapter:
    """Pure offline Kandev mapper used only for adapter conformance tests."""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        self._fixture = dict(fixture)

    def dispatch(self, packet: Mapping[str, Any]) -> Mapping[str, Any]:
        del packet
        raise OrchestrationContractError(
            "not_enabled", "live Kandev dispatch is disabled"
        )

    def observe(self, external_task_id: str) -> Mapping[str, Any]:
        del external_task_id
        raise OrchestrationContractError(
            "not_enabled", "live Kandev observe is disabled"
        )

    def interrupt(self, external_task_id: str) -> Mapping[str, Any]:
        del external_task_id
        raise OrchestrationContractError(
            "not_enabled", "live Kandev interrupt is disabled"
        )

    def collect(self, external_task_id: str) -> Mapping[str, Any]:
        task_id = _required_text(external_task_id, "external_task_id")
        if self._fixture.get("external_task_id") != task_id:
            raise OrchestrationContractError(
                "transport_failed", "fixture task identity mismatch"
            )
        return dict(self._fixture)


def _required_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise OrchestrationContractError(
            "verification_unprovable", f"missing {field_name}"
        )
    return text


def _manifest_digest(manifest: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(manifest), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return compute_packet_hash(canonical)


def _artifact_refs_digest(artifact_refs: list[Any]) -> str:
    canonical = json.dumps(
        sorted(str(ref) for ref in artifact_refs),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return compute_packet_hash(canonical)


def _normalise_relative_path(value: Any) -> str:
    path = _required_text(value, "changed_path")
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise OrchestrationContractError(
            "manifest_scope_violation", f"unsafe path: {path}"
        )
    path = path.removeprefix("./")
    if not path or path == ".":
        raise OrchestrationContractError(
            "manifest_scope_violation", "empty changed path"
        )
    return path


def _path_is_allowed(changed_path: str, surface: str) -> bool:
    normalized_surface = _normalise_relative_path(surface)
    if surface.endswith("/"):
        return changed_path.startswith(normalized_surface.rstrip("/") + "/")
    return changed_path == normalized_surface


def _validate_candidate(
    packet: Mapping[str, Any], manifest: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], str]:
    try:
        packet_value = WorkPacket.model_validate(packet).model_dump(mode="json")
        manifest_value = CompletionManifestModel.model_validate(manifest).model_dump(
            mode="json"
        )
    except Exception as exc:  # Pydantic's error is intentionally boundary-local.
        raise OrchestrationContractError(
            "verification_unprovable", "invalid ECOS contract"
        ) from exc

    expected_hash = compute_packet_hash(canonicalize(packet_value))
    if manifest_value["packet_hash"] != expected_hash:
        raise OrchestrationContractError(
            "packet_hash_mismatch", "manifest hash differs from ECOS canonical packet"
        )
    if manifest_value["packet_id"] != packet_value["packet_id"]:
        raise OrchestrationContractError(
            "packet_hash_mismatch", "manifest packet identity differs"
        )
    if (
        manifest_value["status"] != "candidate"
        or manifest_value["recommended_next"] != "verify"
    ):
        raise OrchestrationContractError(
            "verification_unprovable", "only candidate manifests may enter verification"
        )
    if not manifest_value["claims"] or not manifest_value["checks"]:
        raise OrchestrationContractError(
            "verification_unprovable", "candidate requires claims and checks"
        )
    if any(check.get("returncode") != 0 for check in manifest_value["checks"]):
        raise OrchestrationContractError(
            "verification_unprovable", "candidate checks must all pass"
        )
    for claim in manifest_value["claims"]:
        if not str(claim.get("assertion") or "").strip() or not claim.get(
            "evidence_refs"
        ):
            raise OrchestrationContractError(
                "verification_unprovable",
                "every claim requires assertion and evidence_refs",
            )
    required_acceptance_ids = {
        str(item.get("id"))
        for item in packet_value["acceptance"].get("done_when", [])
        if isinstance(item, Mapping) and item.get("id")
    }
    claimed_acceptance_ids = {
        str(item.get("acceptance_id"))
        for item in manifest_value["claims"]
        if isinstance(item, Mapping) and item.get("acceptance_id")
    }
    if not required_acceptance_ids.issubset(claimed_acceptance_ids):
        raise OrchestrationContractError(
            "verification_unprovable", "candidate does not cover every acceptance id"
        )
    surface_delta = manifest_value["surface_delta"]
    if any(
        not isinstance(surface_delta.get(key), int) or surface_delta[key] < 0
        for key in ("files", "loc")
    ):
        raise OrchestrationContractError(
            "verification_unprovable", "surface_delta must be non-negative integers"
        )
    max_changed_files = packet_value["budgets"].get("max_changed_files")
    if not isinstance(max_changed_files, int) or max_changed_files < 0:
        raise OrchestrationContractError(
            "verification_unprovable", "packet max_changed_files is invalid"
        )
    if (
        surface_delta["files"] > max_changed_files
        or len(manifest_value["changed_paths"]) > max_changed_files
    ):
        raise OrchestrationContractError(
            "verification_unprovable", "candidate exceeds changed-file budget"
        )
    unique_changed_paths = set(manifest_value["changed_paths"])
    if len(unique_changed_paths) != len(manifest_value["changed_paths"]):
        raise OrchestrationContractError(
            "verification_unprovable", "candidate changed_paths must be unique"
        )
    if surface_delta["files"] != len(unique_changed_paths):
        raise OrchestrationContractError(
            "verification_unprovable",
            "surface_delta.files must match unique changed paths",
        )
    artifact_refs = manifest_value.get("artifact_refs")
    if not artifact_refs or any(
        not re.fullmatch(
            r"git-object://[0-9a-f]{40}|git-tag://\S+|pr://[0-9]+", str(ref)
        )
        for ref in artifact_refs
    ):
        raise OrchestrationContractError(
            "verification_unprovable", "candidate requires durable artifact refs"
        )

    write_surfaces = packet_value["scope"].get("write_surfaces", [])
    if not isinstance(write_surfaces, list):
        raise OrchestrationContractError(
            "manifest_scope_violation", "write surfaces must be a list"
        )
    for changed in manifest_value["changed_paths"]:
        changed_path = _normalise_relative_path(changed)
        if not any(
            _path_is_allowed(changed_path, str(surface)) for surface in write_surfaces
        ):
            raise OrchestrationContractError(
                "manifest_scope_violation", f"undeclared path: {changed_path}"
            )
    return packet_value, manifest_value, expected_hash


def _validate_mesh_binding(
    store: WorkflowMeshStore,
    *,
    workflow_run_id: str,
    step_run_id: str,
    bet_id: str,
) -> str:
    try:
        snapshot = store.snapshot(workflow_run_id)
    except WorkflowMeshEventError as exc:
        raise OrchestrationContractError(
            "verification_unprovable", "workflow run cannot be projected"
        ) from exc
    state = snapshot.get("state")
    if state not in {"succeeded", "verified"}:
        raise OrchestrationContractError(
            "verification_unprovable", "workflow run has not succeeded"
        )
    requested = next(
        (
            event
            for event in store.events()
            if event.get("workflow_run_id") == workflow_run_id
            and event.get("event_type") == "WorkflowRequested"
        ),
        None,
    )
    if (
        not isinstance(requested, Mapping)
        or requested.get("payload", {}).get("bet_id") != bet_id
    ):
        raise OrchestrationContractError(
            "verification_unprovable", "workflow run BET identity mismatch"
        )
    if step_run_id not in snapshot.get("step_runs", {}):
        raise OrchestrationContractError(
            "verification_unprovable", "step run is not admitted by workflow run"
        )
    return str(state)


def _external_evidence_payload(
    receipt: Mapping[str, Any], *, workflow_run_id: str, step_run_id: str
) -> dict[str, Any]:
    resource_id = str(receipt["resource_id"])
    receipt_id = str(receipt["receipt_id"])
    return {
        "evidence_id": f"external:{resource_id}:{receipt_id}",
        "evidence_schema": "external-connection-receipt/v1",
        "kind": "external_connection",
        "uri": f"external://{resource_id}/{receipt['operation']}",
        "sha256": receipt["output_digest"],
        "resource_id": resource_id,
        "trace_id": receipt["trace_id"],
        "workflow_run_id": workflow_run_id,
        "result_state": receipt["result_state"],
        "observed_at": receipt["observed_at"],
        "provenance_ref": receipt["provenance_ref"],
        "policy_digest": receipt["policy_digest"],
        "receipt_id": receipt_id,
        "decision_factors": dict(receipt["decision_factors"]),
        "step_run_id": step_run_id,
    }


def _fresh_verification_receipt(
    packet: Mapping[str, Any], supplied: VerificationReceipt
) -> VerificationReceipt:
    """Reject mutation of ECOS's mutable receipt dataclass after hash creation."""
    try:
        fresh = build_verification_receipt(
            packet=dict(packet),
            candidate_packet_hash=supplied.candidate_packet_hash,
            measured_packet_hash=supplied.measured_packet_hash,
            executor_model_family=supplied.executor_model_family,
            verifier_model_family=supplied.verifier_model_family,
            verdict=supplied.verdict,
            read_only=supplied.read_only,
            direct_measurement=supplied.direct_measurement,
            allow_same_model=supplied.allow_same_model,
            checks=[
                {
                    "command": list(check.command),
                    "returncode": check.returncode,
                    "stdout_hash": check.stdout_hash,
                }
                for check in supplied.checks
            ],
            notes=supplied.notes,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise OrchestrationContractError(
            "verification_unprovable", "verification receipt is invalid"
        ) from exc
    if fresh.receipt_hash != supplied.receipt_hash:
        raise OrchestrationContractError(
            "verification_unprovable", "verification receipt hash is stale"
        )
    return fresh


def _evidence_matches(
    store: WorkflowMeshStore,
    workflow_run_id: str,
    *,
    packet_id: str,
    packet_hash: str,
    assignment_id: str,
    manifest_digest: str,
) -> Mapping[str, Any] | None:
    for event in store.events():
        if (
            event.get("workflow_run_id") != workflow_run_id
            or event.get("event_type") != "EvidenceRecorded"
        ):
            continue
        factors = event.get("payload", {}).get("decision_factors", {})
        if not isinstance(factors, Mapping):
            continue
        identity = (
            factors.get("packet_id"),
            factors.get("packet_hash"),
            factors.get("assignment_id"),
        )
        if identity != (packet_id, packet_hash, assignment_id):
            continue
        if factors.get("manifest_digest") != manifest_digest:
            raise OrchestrationContractError(
                "manifest_conflict", "candidate manifest changed after collection"
            )
        payload = event.get("payload")
        return payload if isinstance(payload, Mapping) else None
    return None


def _verified_event(
    workflow_run_id: str,
    packet_id: str,
    packet_hash: str,
    assignment_id: str,
    bet_id: str,
    step_run_id: str,
    source_receipt_hash: str,
    manifest_digest: str,
    occurred_at: str,
) -> dict[str, Any]:
    binding_hash = compute_packet_hash(
        f"{workflow_run_id}\n{assignment_id}\n{bet_id}\n{step_run_id}\n{manifest_digest}\n{source_receipt_hash}"
    )
    payload = {
        "packet_id": packet_id,
        "packet_hash": packet_hash,
        "assignment_id": assignment_id,
        "bet_id": bet_id,
        "step_run_id": step_run_id,
        "receipt_hash": binding_hash,
        "source_receipt_hash": source_receipt_hash,
        "manifest_digest": manifest_digest,
    }
    event = new_workflow_event(
        "WorkflowVerified",
        workflow_run_id,
        producer="omo-orchestration-contract",
        payload=payload,
        idempotency_key=f"verification:{workflow_run_id}:{binding_hash}",
    )
    event["event_id"] = (
        "verification:"
        + hashlib.sha256(f"{workflow_run_id}\n{binding_hash}".encode()).hexdigest()
    )
    event["occurred_at"] = occurred_at
    return event


class OrchestrationContractCoordinator:
    """Validate a candidate and append only legal existing Mesh events."""

    def __init__(self, omo_dir: Path | str) -> None:
        self._omo_dir = Path(omo_dir)

    def record_kandev_candidate(
        self,
        *,
        workflow_run_id: str,
        step_run_id: str,
        packet: Mapping[str, Any],
        manifest: Mapping[str, Any],
        fixture: Mapping[str, Any],
    ) -> dict[str, Any]:
        packet_value, manifest_value, packet_hash = _validate_candidate(
            packet, manifest
        )
        store = WorkflowMeshStore(self._omo_dir)
        run_state = _validate_mesh_binding(
            store,
            workflow_run_id=workflow_run_id,
            step_run_id=step_run_id,
            bet_id=packet_value["bet_id"],
        )
        adapter = KandevFixtureAdapter(fixture)
        task_id = _required_text(fixture.get("external_task_id"), "external_task_id")
        collected = adapter.collect(task_id)
        expected_identity = {
            "workflow_run_id": _required_text(workflow_run_id, "workflow_run_id"),
            "packet_id": packet_value["packet_id"],
            "packet_hash": packet_hash,
            "assignment_id": manifest_value["assignment_id"],
            "bet_id": packet_value["bet_id"],
            "step_run_id": step_run_id,
        }
        for key, expected in expected_identity.items():
            if collected.get(key) != expected:
                raise OrchestrationContractError(
                    "verification_unprovable",
                    f"fixture {key} does not bind current candidate",
                )
        if str(collected.get("state") or "").lower() != "succeeded":
            raise OrchestrationContractError(
                "transport_failed", "fixture did not succeed"
            )
        output_digest = _required_text(collected.get("output_digest"), "output_digest")
        if len(output_digest) != 64 or any(
            char not in "0123456789abcdef" for char in output_digest.lower()
        ):
            raise OrchestrationContractError(
                "transport_failed", "fixture output_digest is invalid"
            )

        receipt = {
            "receipt_id": f"kandev:{task_id}",
            "trace_id": _required_text(workflow_run_id, "workflow_run_id"),
            "resource_id": task_id,
            "operation": "collect",
            "result_state": "succeeded",
            "observed_at": _required_text(collected.get("observed_at"), "observed_at"),
            "provenance_ref": _required_text(
                collected.get("provenance_ref"), "provenance_ref"
            ),
            "policy_digest": "orchestration-contract/v1",
            "output_digest": output_digest.lower(),
            "decision_factors": {
                "packet_id": packet_value["packet_id"],
                "packet_hash": packet_hash,
                "assignment_id": manifest_value["assignment_id"],
                "external_task_id": task_id,
                "bet_id": packet_value["bet_id"],
                "manifest_digest": _manifest_digest(manifest_value),
                "artifact_refs_digest": _artifact_refs_digest(
                    manifest_value["artifact_refs"] or []
                ),
            },
        }
        expected_payload = _external_evidence_payload(
            receipt, workflow_run_id=workflow_run_id, step_run_id=step_run_id
        )
        idempotency_key = f"external-evidence:{workflow_run_id}:{receipt['receipt_id']}"
        for existing in store.events():
            if existing.get("idempotency_key") != idempotency_key:
                continue
            if existing.get("payload") == expected_payload:
                return existing
            raise OrchestrationContractError(
                "manifest_conflict", "external task receipt conflicts"
            )
        if run_state != "succeeded":
            raise OrchestrationContractError(
                "verification_unprovable",
                "verified workflow cannot record new evidence",
            )
        try:
            return record_external_receipt(
                self._omo_dir,
                receipt,
                workflow_run_id=workflow_run_id,
                step_run_id=step_run_id,
                producer="omo-orchestration-contract",
            )
        except WorkflowMeshEventError as exc:
            if "Conflicting duplicate" in str(exc):
                raise OrchestrationContractError(
                    "manifest_conflict", "conflicting external candidate receipt"
                ) from exc
            raise OrchestrationContractError(
                "verification_unprovable", "Mesh rejected candidate evidence"
            ) from exc
        except ExternalReceiptError as exc:
            raise OrchestrationContractError(
                "verification_unprovable", "external receipt is invalid"
            ) from exc

    def accept_verification(
        self,
        *,
        workflow_run_id: str,
        packet: Mapping[str, Any],
        manifest: Mapping[str, Any],
        verification_receipt: VerificationReceipt,
    ) -> dict[str, Any]:
        packet_value, manifest_value, packet_hash = _validate_candidate(
            packet, manifest
        )
        receipt = _fresh_verification_receipt(packet_value, verification_receipt)
        if (
            receipt.packet_id != packet_value["packet_id"]
            or receipt.candidate_packet_hash != packet_hash
        ):
            raise OrchestrationContractError(
                "packet_hash_mismatch",
                "verification receipt does not bind candidate packet",
            )
        if not receipt.read_only or not receipt.direct_measurement:
            raise OrchestrationContractError(
                "verification_unprovable",
                "verification must be read-only direct measurement",
            )
        if not receipt.checks or any(check.returncode != 0 for check in receipt.checks):
            raise OrchestrationContractError(
                "verification_unprovable", "verification checks must all pass"
            )
        if receipt.verdict == "revise":
            raise OrchestrationContractError(
                "verification_revise", "verifier requested revision"
            )
        if receipt.verdict == "reject":
            raise OrchestrationContractError(
                "verification_rejected", "verifier rejected candidate"
            )
        if receipt.verdict != "accept":
            raise OrchestrationContractError(
                "verification_unprovable", "unknown verification verdict"
            )

        store = WorkflowMeshStore(self._omo_dir)
        evidence = _evidence_matches(
            store,
            workflow_run_id,
            packet_id=packet_value["packet_id"],
            packet_hash=packet_hash,
            assignment_id=manifest_value["assignment_id"],
            manifest_digest=_manifest_digest(manifest_value),
        )
        if evidence is None:
            raise OrchestrationContractError(
                "evidence_missing", "matching external evidence is required"
            )
        evidence_factors = evidence.get("decision_factors", {})
        if not isinstance(evidence_factors, Mapping):
            raise OrchestrationContractError(
                "evidence_missing", "evidence lacks identity factors"
            )
        step_run_id = evidence.get("step_run_id")
        if not isinstance(step_run_id, str) or not step_run_id:
            raise OrchestrationContractError(
                "evidence_missing", "evidence lacks step identity"
            )
        if evidence_factors.get("bet_id") != packet_value["bet_id"]:
            raise OrchestrationContractError(
                "evidence_missing", "evidence lacks BET identity"
            )

        event = _verified_event(
            workflow_run_id,
            packet_value["packet_id"],
            packet_hash,
            manifest_value["assignment_id"],
            packet_value["bet_id"],
            step_run_id,
            receipt.receipt_hash,
            _manifest_digest(manifest_value),
            receipt.created_at,
        )
        for existing in store.events():
            if (
                existing.get("event_type") != "WorkflowVerified"
                or existing.get("payload", {}).get("source_receipt_hash")
                != receipt.receipt_hash
            ):
                continue
            payload = existing.get("payload", {})
            existing_binding = (
                existing.get("workflow_run_id"),
                payload.get("assignment_id"),
                payload.get("bet_id"),
                payload.get("step_run_id"),
                payload.get("manifest_digest"),
            )
            current_binding = (
                workflow_run_id,
                manifest_value["assignment_id"],
                packet_value["bet_id"],
                step_run_id,
                _manifest_digest(manifest_value),
            )
            if existing_binding == current_binding:
                return existing
            raise OrchestrationContractError(
                "manifest_conflict", "source receipt crosses binding"
            )
        try:
            return store.append(event)
        except WorkflowMeshEventError as exc:
            raise OrchestrationContractError(
                "verification_unprovable", "Mesh rejected verification event"
            ) from exc


__all__ = [
    "KandevFixtureAdapter",
    "OrchestrationContractCoordinator",
    "OrchestrationContractError",
    "OrchestratorAdapter",
]
