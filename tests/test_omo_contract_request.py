from __future__ import annotations


def test_contract_request_ref_uses_task_id_and_timestamp_slug():
    from omo.omo_contract_request import contract_request_ref

    assert contract_request_ref("P19-W4-TASK-001", "2026-06-03T12:30:45Z") == (
        ".omo/workers/runs/P19-W4-TASK-001-contract-request-2026-06-03T12-30-45Z.yaml"
    )


def test_build_contract_request_creates_structured_artifact_with_deliverables():
    from omo.omo_contract_request import build_contract_request, contract_request_ref

    request_ref = contract_request_ref("P19-W4-TASK-001", "2026-06-03T12:00:00Z")
    deliverables = [
        ".omo/deliverables/test-report.md",
        ".omo/deliverables/implementation.py",
    ]

    record = build_contract_request(
        task_id="P19-W4-TASK-001",
        task_ref=".omo/tasks/active/P19-W4-TASK-001.yaml",
        deliverables=deliverables,
        requested_at="2026-06-03T12:00:00Z",
        requested_by="copilot-cli",
        request_ref=request_ref,
    )

    assert record["version"] == 1
    assert record["request_id"] == "P19-W4-TASK-001-contract-request-2026-06-03T12-00-00Z"
    assert record["task_id"] == "P19-W4-TASK-001"
    assert record["request_status"] == "requested"
    assert record["deliverables"] == deliverables
    assert record["requested_at"] == "2026-06-03T12:00:00Z"
    assert record["requested_by"] == "copilot-cli"
    assert record["refs"]["task_ref"] == ".omo/tasks/active/P19-W4-TASK-001.yaml"


def test_build_contract_proposal_targets_task_yaml_and_sets_deliverables():
    from omo.omo_contract_request import build_contract_proposal, contract_request_ref

    request_ref = contract_request_ref("P19-W4-TASK-001", "2026-06-03T12:00:00Z")
    task_ref = ".omo/tasks/active/P19-W4-TASK-001.yaml"
    deliverables = [
        ".omo/deliverables/test-report.md",
        ".omo/deliverables/implementation.py",
    ]

    proposal = build_contract_proposal(
        task_id="P19-W4-TASK-001",
        task_ref=task_ref,
        deliverables=deliverables,
        requested_by="copilot-cli",
        request_ref=request_ref,
    )

    assert proposal["id"] == "P19-W4-TASK-001-contract-request-2026-06-03T12-00-00Z-proposal"
    assert proposal["title"] == "Declare contract deliverables for P19-W4-TASK-001"
    assert proposal["operation_level"] == "L2"
    assert proposal["requested_by"] == "copilot-cli"
    assert proposal["target"]["ref"] == task_ref
    assert proposal["changes"]["set"]["deliverables"] == deliverables
    assert "change_summary" in proposal
    assert "impact" in proposal
    assert "verification_plan" in proposal
    assert "rollback_plan" in proposal
    assert "secret_refs" in proposal
    assert "trace_id" in proposal


def test_contract_request_and_proposal_use_consistent_references():
    from omo.omo_contract_request import (
        build_contract_proposal,
        build_contract_request,
        contract_request_ref,
    )

    task_id = "P19-W4-TASK-001"
    task_ref = ".omo/tasks/active/P19-W4-TASK-001.yaml"
    now = "2026-06-03T12:00:00Z"
    deliverables = [".omo/deliverables/test-report.md"]
    request_ref = contract_request_ref(task_id, now)

    request = build_contract_request(
        task_id=task_id,
        task_ref=task_ref,
        deliverables=deliverables,
        requested_at=now,
        requested_by="copilot-cli",
        request_ref=request_ref,
    )

    proposal = build_contract_proposal(
        task_id=task_id,
        task_ref=task_ref,
        deliverables=deliverables,
        requested_by="copilot-cli",
        request_ref=request_ref,
    )

    request_id = request["request_id"]
    assert proposal["id"] == f"{request_id}-proposal"
    assert request["refs"]["task_ref"] == task_ref
    assert proposal["target"]["ref"] == task_ref
    assert request["deliverables"] == deliverables
    assert proposal["changes"]["set"]["deliverables"] == deliverables
    assert proposal["trace_id"].startswith("trace-")
    assert request_id in proposal["trace_id"]
