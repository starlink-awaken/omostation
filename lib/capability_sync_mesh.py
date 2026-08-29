"""Mesh verification projector for bin/capability-sync.py (T10-65).

Read-only extraction: materializes only persisted Mesh v1 facts consumed by
verification.  Not a writer, registry, or independent authority.  Kept in a
sibling module so capability-sync stays under the 1500-line god-module gate.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from capability_trace_binding import (  # noqa: E402 -- sibling module, script dir on sys.path
    IDENTITY_RE,
    TraceBindingError,
    _canonical_json,
    _digest,
)
from capability_sync_verification_helpers import (  # noqa: E402
    verification_receipt as _verification_receipt,
)

try:
    from capability_native_execution_model import NativeExecutionReceiptError
    from capability_native_execution_receipt import validate_native_execution_material

    NATIVE_EXECUTION_LIBS_AVAILABLE = True
except ImportError:  # embedded minimal workspaces stay importable
    NATIVE_EXECUTION_LIBS_AVAILABLE = False

MAX_MESH_LOG_BYTES = 8 * 1024 * 1024
VERIFICATION_SCHEMA = "capability-admission-verification-request/v1"
VERIFICATION_RECEIPT_SCHEMA = "capability-admission-verification-receipt/v1"
PRINCIPAL_VERIFICATION_RECEIPT_SCHEMA = "principal-authority-verification-receipt/v1"
VERIFICATION_FIELDS = {"schema", "material", "request", "expected"}
VERIFICATION_EXPECTED_FIELDS = {"capability_id", "operation_id", "effect_classification"}
MESH_LOG = Path("_knowledge/workflow-mesh/events.jsonl")
VERIFICATION_MESH_EVENT_STATES = {
    "WorkflowRequested": "planned",
    "WorkflowAdmitted": "admitted",
    "StepDispatched": "dispatched",
    "StepStarted": "running",
    "WorkerAcknowledged": "dispatched",
    "WorkerLeaseRenewed": "running",
    "WorkerLeaseExpired": "unavailable",
    "AdmissionRenewed": "dispatched",
    "WorkerReclaimed": "running",
}

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
        if event_type not in VERIFICATION_MESH_EVENT_STATES:
            raise TraceBindingError("admission_receipt_invalid")
        if event_type == "AdmissionRenewed":
            raise TraceBindingError("admission_contradiction")
        if snapshot["state"] not in allowed_states[event_type]:
            raise TraceBindingError("admission_receipt_invalid")

        if event_type == "WorkflowRequested":
            snapshot["state"] = VERIFICATION_MESH_EVENT_STATES[event_type]
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
            snapshot["state"] = VERIFICATION_MESH_EVENT_STATES[event_type]
            continue

        admission = snapshot.get("admission")
        step_run_id = payload.get("step_run_id")
        if not step_run_id or not isinstance(admission, dict):
            raise TraceBindingError("admission_receipt_invalid")
        if payload.get("admission_id") != admission.get("admission_id"):
            raise TraceBindingError("admission_receipt_invalid")
        if not any(
            step_run_id == admitted or step_run_id.startswith(f"{admitted}:") for admitted in admission["step_run_ids"]
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
                    worker.get(key) != payload.get(key) for key in ("packet_id", "packet_hash", "instruction_binding")
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
            event_name: VERIFICATION_MESH_EVENT_STATES[event_name]
            for event_name in (
                "StepDispatched",
                "StepStarted",
                "WorkerLeaseRenewed",
                "WorkerLeaseExpired",
                "WorkerReclaimed",
            )
        }.get(event_type, step["state"])
        step["admission_id"] = payload.get("admission_id", step.get("admission_id"))

        if event_type == "StepDispatched":
            snapshot["state"] = (
                VERIFICATION_MESH_EVENT_STATES["StepStarted"]
                if snapshot["state"] == "running"
                else VERIFICATION_MESH_EVENT_STATES[event_type]
            )
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
                        "ack_decision": payload["ack_decision"],
                    }
                )
            elif event_type == "WorkerLeaseRenewed":
                worker["state"] = "active"
                snapshot["state"] = VERIFICATION_MESH_EVENT_STATES[event_type]
            elif event_type == "WorkerLeaseExpired":
                worker["state"] = "lease_expired"
                snapshot["state"] = VERIFICATION_MESH_EVENT_STATES[event_type]
            else:
                worker.update(
                    {
                        "state": "reclaimed",
                        "successor_worker_id": payload["successor_worker_id"],
                        "successor_dispatch_id": payload["successor_dispatch_id"],
                    }
                )
                snapshot["state"] = VERIFICATION_MESH_EVENT_STATES[event_type]
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


def _parse_verification_envelope(
    envelope: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
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
    if worker.get("ack_decision") == "stop":
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
    omo_dir: Union[Path, str],  # noqa: UP007 -- Python 3.9 compatibility contract
    envelope: Mapping[str, Any],  # noqa: UP007 -- Python 3.9 style
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
                not isinstance(capability, str) or not IDENTITY_RE.fullmatch(capability) or ".." in capability
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
