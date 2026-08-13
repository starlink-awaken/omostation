"""Regression tests for the orchestrator-neutral delivery contract MVP."""

from __future__ import annotations

import hashlib
import json

import pytest
from ecos.ssot.tools.work_packet_compiler import (
    build_command_check,
    build_verification_receipt,
    canonicalize,
    compute_packet_hash,
)

from omo.orchestration_contract import (
    KandevFixtureAdapter,
    OrchestrationContractCoordinator,
    OrchestrationContractError,
)
from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event

NOW = "2026-08-13T06:00:00Z"


def _packet() -> dict[str, object]:
    return {
        "packet_id": "WP-ORCH-001",
        "schema_version": "work-packet/v1",
        "blueprint_ref": "blueprint://orchestration-contract/001",
        "wave": "Y1Q2",
        "bet_id": "BET-Y1Q2-T1-14",
        "strategic_outcome": "orchestrator-neutral evidence chain",
        "objective": "connect a candidate manifest to mesh evidence",
        "why_now": "multiple external orchestrators need one delivery contract",
        "status": "active",
        "authority": {"strategist": "omo", "human_gate": False, "risk_level": "R1"},
        "scope": {
            "read_surfaces": ["projects/omo/src/omo/"],
            "write_surfaces": ["projects/omo/src/omo/", "README.md"],
            "non_goals": ["live Kandev", "scheduler"],
        },
        "dependencies": {
            "required_packets": [],
            "required_services": [],
            "required_decisions": [],
        },
        "acceptance": {
            "done_when": [
                {
                    "id": "AC1",
                    "assertion": "receipt is independently verifiable",
                    "evidence_type": "test_result",
                }
            ],
            "verify_commands": [["pytest", "-q"]],
        },
        "budgets": {
            "appetite_hours": 1.0,
            "max_elapsed_hours": 2.0,
            "max_changed_files": 2,
            "max_new_files": 2,
            "max_new_top_level_components": 1,
        },
        "rollback": {"strategy": "revert", "data_migration": False},
        "circuit_breaker": {"when": ["scope expansion"], "action": "interrupt"},
        "assignment": {
            "executor_class": "E1",
            "verifier_class": "V1",
            "same_model_verification_allowed": True,
            "expires_at": "2026-08-14T00:00:00+08:00",
        },
    }


def _hash(packet: dict[str, object]) -> str:
    return compute_packet_hash(canonicalize(packet))


def _manifest(
    packet: dict[str, object],
    *,
    changed_paths: list[str] | None = None,
    packet_hash: str | None = None,
) -> dict[str, object]:
    return {
        "packet_id": packet["packet_id"],
        "packet_hash": packet_hash or _hash(packet),
        "assignment_id": "ASG-ORCH-001",
        "agent_id": "kandev-fixture-agent",
        "status": "candidate",
        "changed_paths": changed_paths
        or ["projects/omo/src/omo/orchestration_contract.py"],
        "claims": [
            {
                "acceptance_id": "AC1",
                "assertion": "candidate ready",
                "evidence_refs": ["evidence://fixture"],
            }
        ],
        "checks": [build_command_check(["pytest", "-q"], 0, "fixture green")],
        "recommended_next": "verify",
        "surface_delta": {"files": 1, "loc": 20},
        "artifact_refs": ["git-object://" + "a" * 40],
    }


def _manifest_digest(manifest: dict[str, object]) -> str:
    return compute_packet_hash(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _fixture(
    packet: dict[str, object],
    *,
    workflow_run_id: str = "run-orch",
    assignment_id: str = "ASG-ORCH-001",
    step_run_id: str = "run-orch:step-1",
    state: str = "succeeded",
    output_digest: str | None = None,
) -> dict[str, object]:
    return {
        "external_task_id": "kandev-task-001",
        "workflow_run_id": workflow_run_id,
        "bet_id": packet["bet_id"],
        "packet_id": packet["packet_id"],
        "packet_hash": _hash(packet),
        "assignment_id": assignment_id,
        "step_run_id": step_run_id,
        "adapter_metadata": {"source": "offline-fixture"},
        "state": state,
        "observed_at": NOW,
        "provenance_ref": "fixture://kandev/task-001",
        "output_digest": output_digest or hashlib.sha256(b"fixture output").hexdigest(),
    }


def _grant(run_id: str, step_run_id: str) -> dict[str, object]:
    grant: dict[str, object] = {
        "admission_id": f"adm-{run_id}",
        "status": "admitted",
        "workflow_run_id": run_id,
        "trace_id": run_id,
        "backend": "orchestration-contract-test",
        "step_run_ids": [step_run_id],
        "capabilities": ["execute"],
        "policy_digest": "orchestration-contract/v1",
        "issued_at": NOW,
        "expires_at": "2026-08-13T07:00:00Z",
    }
    canonical = json.dumps(
        grant, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    grant["proof"] = hashlib.sha256(canonical).hexdigest()
    return grant


def _seed_succeeded_run(tmp_path, run_id: str = "run-orch") -> str:
    step_run_id = f"{run_id}:step-1"
    grant = _grant(run_id, step_run_id)
    store = WorkflowMeshStore(tmp_path)
    store.append(
        new_workflow_event(
            "WorkflowRequested", run_id, payload={"bet_id": "BET-Y1Q2-T1-14"}
        )
    )
    store.append(
        new_workflow_event(
            "WorkflowAdmitted", run_id, payload={"admission": grant, **grant}
        )
    )
    context = {"step_run_id": step_run_id, "admission_id": grant["admission_id"]}
    store.append(new_workflow_event("StepDispatched", run_id, payload=context))
    store.append(new_workflow_event("StepStarted", run_id, payload=context))
    store.append(new_workflow_event("WorkflowSucceeded", run_id))
    return step_run_id


def _receipt(
    packet: dict[str, object],
    *,
    verdict: str = "accept",
    candidate_packet_hash: str | None = None,
    measured_packet_hash: str | None = None,
):
    packet_hash = _hash(packet)
    return build_verification_receipt(
        packet=packet,
        candidate_packet_hash=candidate_packet_hash or packet_hash,
        measured_packet_hash=measured_packet_hash or packet_hash,
        executor_model_family="fixture-executor",
        verifier_model_family="fixture-verifier",
        verdict=verdict,
        checks=[build_command_check(["pytest", "-q"], 0, "verified")],
    )


def test_fixture_metadata_is_not_part_of_packet_hash_and_live_transport_is_disabled():
    packet = _packet()
    adapter = KandevFixtureAdapter(_fixture(packet))

    assert _hash(packet) == _hash(
        {**packet, "adapter_metadata": {"ui_status": "polling"}}
    )
    assert adapter.collect("kandev-task-001")["external_task_id"] == "kandev-task-001"
    with pytest.raises(OrchestrationContractError, match="not_enabled"):
        adapter.dispatch(packet)


def test_candidate_evidence_then_acceptance_forms_one_identity_chain(tmp_path):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    coordinator = OrchestrationContractCoordinator(tmp_path)

    evidence = coordinator.record_kandev_candidate(
        workflow_run_id="run-orch",
        step_run_id=step_run_id,
        packet=packet,
        manifest=_manifest(packet),
        fixture=_fixture(packet),
    )
    verified = coordinator.accept_verification(
        workflow_run_id="run-orch",
        packet=packet,
        manifest=_manifest(packet),
        verification_receipt=_receipt(packet),
    )

    events = WorkflowMeshStore(tmp_path).events()
    assert evidence["event_type"] == "EvidenceRecorded"
    assert verified["event_type"] == "WorkflowVerified"
    assert evidence["payload"]["decision_factors"][
        "artifact_refs_digest"
    ] == compute_packet_hash(
        json.dumps(
            ["git-object://" + "a" * 40], ensure_ascii=False, separators=(",", ":")
        )
    )
    assert [event["event_type"] for event in events][-2:] == [
        "EvidenceRecorded",
        "WorkflowVerified",
    ]
    assert verified["payload"] | {"receipt_hash": None, "manifest_digest": None} == {
        "assignment_id": "ASG-ORCH-001",
        "manifest_digest": None,
        "packet_hash": _hash(packet),
        "packet_id": "WP-ORCH-001",
        "bet_id": packet["bet_id"],
        "step_run_id": step_run_id,
        "receipt_hash": None,
        "source_receipt_hash": _receipt(packet).receipt_hash,
    }
    assert verified["payload"]["receipt_hash"] == compute_packet_hash(
        f"run-orch\nASG-ORCH-001\n{packet['bet_id']}\n{step_run_id}\n"
        f"{verified['payload']['manifest_digest']}\n{_receipt(packet).receipt_hash}"
    )
    assert WorkflowMeshStore(tmp_path).snapshot("run-orch")["state"] == "verified"


@pytest.mark.parametrize(
    ("manifest", "reason"),
    [
        (
            lambda packet: _manifest(packet, packet_hash="sha256:" + "0" * 64),
            "packet_hash_mismatch",
        ),
        (
            lambda packet: _manifest(packet, changed_paths=["../../outside.py"]),
            "manifest_scope_violation",
        ),
    ],
)
def test_bad_candidate_never_records_evidence_or_verified(tmp_path, manifest, reason):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    coordinator = OrchestrationContractCoordinator(tmp_path)

    with pytest.raises(OrchestrationContractError, match=reason):
        coordinator.record_kandev_candidate(
            workflow_run_id="run-orch",
            step_run_id=step_run_id,
            packet=packet,
            manifest=manifest(packet),
            fixture=_fixture(packet),
        )

    assert [event["event_type"] for event in WorkflowMeshStore(tmp_path).events()] == [
        "WorkflowRequested",
        "WorkflowAdmitted",
        "StepDispatched",
        "StepStarted",
        "WorkflowSucceeded",
    ]


def test_transport_failure_never_records_succeeded_evidence(tmp_path):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()

    with pytest.raises(OrchestrationContractError, match="transport_failed"):
        OrchestrationContractCoordinator(tmp_path).record_kandev_candidate(
            workflow_run_id="run-orch",
            step_run_id=step_run_id,
            packet=packet,
            manifest=_manifest(packet),
            fixture=_fixture(packet, state="failed"),
        )

    assert all(
        event["event_type"] != "EvidenceRecorded"
        for event in WorkflowMeshStore(tmp_path).events()
    )


@pytest.mark.parametrize(
    ("verdict", "reason"),
    [("revise", "verification_revise"), ("reject", "verification_rejected")],
)
def test_non_accepting_verdict_never_appends_verified(tmp_path, verdict, reason):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    coordinator = OrchestrationContractCoordinator(tmp_path)
    coordinator.record_kandev_candidate(
        workflow_run_id="run-orch",
        step_run_id=step_run_id,
        packet=packet,
        manifest=_manifest(packet),
        fixture=_fixture(packet),
    )

    with pytest.raises(OrchestrationContractError, match=reason):
        coordinator.accept_verification(
            workflow_run_id="run-orch",
            packet=packet,
            manifest=_manifest(packet),
            verification_receipt=_receipt(packet, verdict=verdict),
        )

    assert WorkflowMeshStore(tmp_path).snapshot("run-orch")["state"] == "succeeded"


def test_same_receipt_replay_is_idempotent_but_conflicting_fixture_fails_closed(
    tmp_path,
):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    coordinator = OrchestrationContractCoordinator(tmp_path)
    kwargs = {
        "workflow_run_id": "run-orch",
        "step_run_id": step_run_id,
        "packet": packet,
        "manifest": _manifest(packet),
    }

    first = coordinator.record_kandev_candidate(**kwargs, fixture=_fixture(packet))
    assert (
        coordinator.record_kandev_candidate(**kwargs, fixture=_fixture(packet)) == first
    )
    with pytest.raises(OrchestrationContractError, match="manifest_conflict"):
        coordinator.record_kandev_candidate(
            **kwargs,
            fixture=_fixture(
                packet, output_digest=hashlib.sha256(b"changed").hexdigest()
            ),
        )

    receipt = _receipt(packet)
    verified = coordinator.accept_verification(
        workflow_run_id="run-orch",
        packet=packet,
        manifest=_manifest(packet),
        verification_receipt=receipt,
    )
    assert (
        coordinator.accept_verification(
            workflow_run_id="run-orch",
            packet=packet,
            manifest=_manifest(packet),
            verification_receipt=receipt,
        )
        == verified
    )
    assert [
        event["event_type"] for event in WorkflowMeshStore(tmp_path).events()
    ].count("WorkflowVerified") == 1


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("workflow_run_id", "run-other"),
        ("packet_id", "WP-OTHER"),
        ("packet_hash", "sha256:" + "e" * 64),
        ("assignment_id", "ASG-OTHER"),
    ],
)
def test_fixture_identity_must_match_current_workflow_packet_and_assignment(
    tmp_path, field, wrong_value
):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    bad_fixture = _fixture(packet)
    bad_fixture[field] = wrong_value

    with pytest.raises(OrchestrationContractError, match="verification_unprovable"):
        OrchestrationContractCoordinator(tmp_path).record_kandev_candidate(
            workflow_run_id="run-orch",
            step_run_id=step_run_id,
            packet=packet,
            manifest=_manifest(packet),
            fixture=bad_fixture,
        )


def test_claim_or_check_change_for_same_external_task_is_a_manifest_conflict(tmp_path):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    coordinator = OrchestrationContractCoordinator(tmp_path)
    fixture = _fixture(packet)
    coordinator.record_kandev_candidate(
        workflow_run_id="run-orch",
        step_run_id=step_run_id,
        packet=packet,
        manifest=_manifest(packet),
        fixture=fixture,
    )
    changed = _manifest(packet)
    changed["claims"] = [
        {
            "acceptance_id": "AC1",
            "assertion": "altered",
            "evidence_refs": ["evidence://fixture"],
        }
    ]

    with pytest.raises(OrchestrationContractError, match="manifest_conflict"):
        coordinator.record_kandev_candidate(
            workflow_run_id="run-orch",
            step_run_id=step_run_id,
            packet=packet,
            manifest=changed,
            fixture=fixture,
        )


def test_accept_requires_evidence_binds_candidate_hash_and_allows_independent_measurement(
    tmp_path,
):
    _seed_succeeded_run(tmp_path)
    packet = _packet()
    coordinator = OrchestrationContractCoordinator(tmp_path)

    with pytest.raises(OrchestrationContractError, match="evidence_missing"):
        coordinator.accept_verification(
            workflow_run_id="run-orch",
            packet=packet,
            manifest=_manifest(packet),
            verification_receipt=_receipt(packet),
        )

    step_run_id = "run-orch:step-1"
    coordinator.record_kandev_candidate(
        workflow_run_id="run-orch",
        step_run_id=step_run_id,
        packet=packet,
        manifest=_manifest(packet),
        fixture=_fixture(packet),
    )
    with pytest.raises(OrchestrationContractError, match="packet_hash_mismatch"):
        coordinator.accept_verification(
            workflow_run_id="run-orch",
            packet=packet,
            manifest=_manifest(packet),
            verification_receipt=_receipt(
                packet, candidate_packet_hash="sha256:" + "e" * 64
            ),
        )
    accepted = coordinator.accept_verification(
        workflow_run_id="run-orch",
        packet=packet,
        manifest=_manifest(packet),
        verification_receipt=_receipt(
            packet, measured_packet_hash="sha256:" + "f" * 64
        ),
    )
    assert accepted["event_type"] == "WorkflowVerified"


def test_candidate_must_cover_every_acceptance_id_and_verification_checks_must_pass(
    tmp_path,
):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    packet["acceptance"] = {
        **packet["acceptance"],
        "done_when": [
            *packet["acceptance"]["done_when"],
            {
                "id": "AC2",
                "assertion": "second measurement",
                "evidence_type": "test_result",
            },
        ],
    }
    coordinator = OrchestrationContractCoordinator(tmp_path)
    with pytest.raises(OrchestrationContractError, match="verification_unprovable"):
        coordinator.record_kandev_candidate(
            workflow_run_id="run-orch",
            step_run_id=step_run_id,
            packet=packet,
            manifest=_manifest(packet),
            fixture=_fixture(packet),
        )

    baseline = _packet()
    coordinator.record_kandev_candidate(
        workflow_run_id="run-orch",
        step_run_id=step_run_id,
        packet=baseline,
        manifest=_manifest(baseline),
        fixture=_fixture(baseline),
    )
    receipt = _receipt(baseline)
    receipt.checks[0].returncode = 1
    with pytest.raises(OrchestrationContractError, match="verification_unprovable"):
        coordinator.accept_verification(
            workflow_run_id="run-orch",
            packet=baseline,
            manifest=_manifest(baseline),
            verification_receipt=receipt,
        )


@pytest.mark.parametrize("case", ["wrong_bet", "unknown_step", "not_succeeded"])
def test_candidate_must_bind_to_a_succeeded_mesh_run_bet_and_admitted_step(
    tmp_path, case
):
    packet = _packet()
    run_id = "run-orch"
    step_run_id = _seed_succeeded_run(tmp_path, run_id)
    if case == "wrong_bet":
        packet["bet_id"] = "BET-OTHER"
    elif case == "unknown_step":
        step_run_id = "run-orch:step-unknown"
    else:
        run_id = "run-incomplete"
        step_run_id = "run-incomplete:step-1"
        WorkflowMeshStore(tmp_path).append(
            new_workflow_event(
                "WorkflowRequested", run_id, payload={"bet_id": packet["bet_id"]}
            )
        )

    with pytest.raises(OrchestrationContractError, match="verification_unprovable"):
        OrchestrationContractCoordinator(tmp_path).record_kandev_candidate(
            workflow_run_id=run_id,
            step_run_id=step_run_id,
            packet=packet,
            manifest=_manifest(packet),
            fixture=_fixture(packet, workflow_run_id=run_id),
        )


@pytest.mark.parametrize(
    "case",
    [
        "failed_check",
        "empty_evidence",
        "budget_files",
        "changed_path_count",
        "count_mismatch",
        "missing_artifact",
        "bad_artifact",
        "duplicate_path",
        "prefix_escape",
    ],
)
def test_candidate_manifest_requires_passing_checks_claim_evidence_and_budget(
    tmp_path, case
):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    manifest = _manifest(packet)
    if case == "failed_check":
        manifest["checks"] = [build_command_check(["pytest", "-q"], 1, "fixture red")]
    elif case == "empty_evidence":
        manifest["claims"] = [
            {
                "acceptance_id": "AC1",
                "assertion": "candidate ready",
                "evidence_refs": [],
            }
        ]
    elif case == "budget_files":
        manifest["surface_delta"] = {"files": 3, "loc": 20}
    elif case == "count_mismatch":
        manifest["surface_delta"] = {"files": 2, "loc": 20}
    elif case == "missing_artifact":
        manifest["artifact_refs"] = []
    elif case == "bad_artifact":
        manifest["artifact_refs"] = ["file:///tmp/not-durable"]
    elif case == "duplicate_path":
        packet["scope"] = {**packet["scope"], "write_surfaces": ["README.md"]}
        packet["budgets"] = {**packet["budgets"], "max_changed_files": 2}
        manifest = _manifest(packet, changed_paths=["README.md", "README.md"])
        manifest["surface_delta"] = {"files": 1, "loc": 20}
    elif case == "prefix_escape":
        manifest = _manifest(packet, changed_paths=["projects/omo/src/omox/evil.py"])
    else:
        packet["scope"] = {
            **packet["scope"],
            "write_surfaces": ["README.md", "NOTICE.md", "LICENSE.md"],
        }
        packet["budgets"] = {**packet["budgets"], "max_changed_files": 2}
        manifest = _manifest(
            packet, changed_paths=["README.md", "NOTICE.md", "LICENSE.md"]
        )

    expected_reason = (
        "manifest_scope_violation"
        if case == "prefix_escape"
        else "verification_unprovable"
    )
    with pytest.raises(OrchestrationContractError, match=expected_reason):
        OrchestrationContractCoordinator(tmp_path).record_kandev_candidate(
            workflow_run_id="run-orch",
            step_run_id=step_run_id,
            packet=packet,
            manifest=manifest,
            fixture=_fixture(packet),
        )


def test_mutated_verification_receipt_with_stale_hash_is_unprovable(tmp_path):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    coordinator = OrchestrationContractCoordinator(tmp_path)
    coordinator.record_kandev_candidate(
        workflow_run_id="run-orch",
        step_run_id=step_run_id,
        packet=packet,
        manifest=_manifest(packet),
        fixture=_fixture(packet),
    )

    revised = _receipt(packet, verdict="revise")
    revised.verdict = "accept"
    with pytest.raises(OrchestrationContractError, match="verification_unprovable"):
        coordinator.accept_verification(
            workflow_run_id="run-orch",
            packet=packet,
            manifest=_manifest(packet),
            verification_receipt=revised,
        )

    failed_check = build_verification_receipt(
        packet=packet,
        candidate_packet_hash=_hash(packet),
        measured_packet_hash="sha256:" + "f" * 64,
        executor_model_family="fixture-executor",
        verifier_model_family="fixture-verifier",
        verdict="accept",
        checks=[build_command_check(["pytest", "-q"], 1, "failed verification")],
    )
    stale_hash = failed_check.receipt_hash
    failed_check.checks[0].returncode = 0
    assert failed_check.receipt_hash == stale_hash
    with pytest.raises(OrchestrationContractError, match="verification_unprovable"):
        coordinator.accept_verification(
            workflow_run_id="run-orch",
            packet=packet,
            manifest=_manifest(packet),
            verification_receipt=failed_check,
        )


def test_verified_run_replays_identical_evidence_but_rejects_changed_candidate(
    tmp_path,
):
    step_run_id = _seed_succeeded_run(tmp_path)
    packet = _packet()
    coordinator = OrchestrationContractCoordinator(tmp_path)
    kwargs = {
        "workflow_run_id": "run-orch",
        "step_run_id": step_run_id,
        "packet": packet,
        "manifest": _manifest(packet),
    }
    first = coordinator.record_kandev_candidate(**kwargs, fixture=_fixture(packet))
    coordinator.accept_verification(
        workflow_run_id="run-orch",
        packet=packet,
        manifest=_manifest(packet),
        verification_receipt=_receipt(packet),
    )

    assert (
        coordinator.record_kandev_candidate(**kwargs, fixture=_fixture(packet)) == first
    )
    with pytest.raises(OrchestrationContractError, match="manifest_conflict"):
        coordinator.record_kandev_candidate(
            **kwargs,
            fixture=_fixture(
                packet,
                output_digest=hashlib.sha256(b"changed after verify").hexdigest(),
            ),
        )


def test_source_receipt_cannot_cross_run_or_assignment_binding(tmp_path):
    packet = _packet()
    first_step = _seed_succeeded_run(tmp_path, "run-first")
    second_step = _seed_succeeded_run(tmp_path, "run-second")
    coordinator = OrchestrationContractCoordinator(tmp_path)
    receipt = _receipt(packet)
    first_manifest = _manifest(packet)
    coordinator.record_kandev_candidate(
        workflow_run_id="run-first",
        step_run_id=first_step,
        packet=packet,
        manifest=first_manifest,
        fixture=_fixture(packet, workflow_run_id="run-first", step_run_id=first_step),
    )
    coordinator.accept_verification(
        workflow_run_id="run-first",
        packet=packet,
        manifest=first_manifest,
        verification_receipt=receipt,
    )

    second_manifest = {**_manifest(packet), "assignment_id": "ASG-ORCH-002"}
    coordinator.record_kandev_candidate(
        workflow_run_id="run-second",
        step_run_id=second_step,
        packet=packet,
        manifest=second_manifest,
        fixture=_fixture(
            packet,
            workflow_run_id="run-second",
            assignment_id="ASG-ORCH-002",
            step_run_id=second_step,
        ),
    )
    with pytest.raises(OrchestrationContractError, match="manifest_conflict"):
        coordinator.accept_verification(
            workflow_run_id="run-second",
            packet=packet,
            manifest=second_manifest,
            verification_receipt=receipt,
        )
