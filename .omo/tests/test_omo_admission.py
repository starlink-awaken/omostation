from __future__ import annotations

from pathlib import Path

import yaml

from scripts.omo_admission import evaluate_worker_envelope, request_conditional_approval


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_evaluate_worker_envelope_returns_conditional_approval_for_wave3_dispatch() -> None:
    root = Path(__file__).resolve().parents[2]

    result = evaluate_worker_envelope(
        root,
        Path(".omo/workers/runs/phase9-wave3-identity-admission-envelope.yaml"),
    )

    assert result == {
        "space_ref": "spaces/system-space.yaml",
        "membership_ref": "system-governor-membership",
        "action": "project.dispatch",
        "required_capabilities": ["project.dispatch"],
        "granted_capabilities": [
            "governance.write",
            "project.dispatch",
            "runtime.mutate",
            "space.membership.manage",
        ],
        "missing_capabilities": [],
        "decision": "conditional_approval",
        "approval_required": True,
    }


def test_evaluate_worker_envelope_denies_when_membership_lacks_required_capability(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path / "spaces" / "contract.yaml",
        {
            "memberships": [
                {
                    "id": "limited-membership",
                    "actor_ref": "demo-actor",
                    "space_ref": "spaces/system-space.yaml",
                    "roles": ["observer"],
                }
            ],
            "capability_bindings": [
                {
                    "id": "observer-binding",
                    "membership_ref": "limited-membership",
                    "capabilities": ["runtime.observe"],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "matrix.yaml",
        {
            "rules": [
                {
                    "action": "project.dispatch",
                    "required_capabilities": ["project.dispatch"],
                    "decision": "conditional_approval",
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "limited-membership",
                "action": "project.dispatch",
                "admission_contract_ref": "spaces/contract.yaml",
                "required_capabilities": ["project.dispatch"],
                "decision_mode": "conditional_approval",
            }
        },
    )

    result = evaluate_worker_envelope(
        tmp_path,
        Path(".omo/workers/runs/example-envelope.yaml"),
        matrix_ref=Path("spaces/matrix.yaml"),
    )

    assert result == {
        "space_ref": "spaces/system-space.yaml",
        "membership_ref": "limited-membership",
        "action": "project.dispatch",
        "required_capabilities": ["project.dispatch"],
        "granted_capabilities": ["runtime.observe"],
        "missing_capabilities": ["project.dispatch"],
        "decision": "deny",
        "approval_required": False,
    }


def test_request_conditional_approval_creates_approval_record_and_governance_proposal(tmp_path: Path) -> None:
    _write_yaml(
        tmp_path / "spaces" / "contract.yaml",
        {
            "admission_matrix_ref": "spaces/matrix.yaml",
            "memberships": [
                {
                    "id": "governor-membership",
                    "actor_ref": "demo-actor",
                    "space_ref": "spaces/system-space.yaml",
                    "roles": ["governor"],
                }
            ],
            "capability_bindings": [
                {
                    "id": "governor-binding",
                    "membership_ref": "governor-membership",
                    "capabilities": ["project.dispatch"],
                }
            ],
        },
    )
    _write_yaml(
        tmp_path / "spaces" / "matrix.yaml",
        {
            "rules": [
                {
                    "action": "project.dispatch",
                    "required_capabilities": ["project.dispatch"],
                    "decision": "conditional_approval",
                }
            ]
        },
    )
    _write_yaml(
        tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml",
        {
            "task_id": "TASK-1",
            "worker_id": "copilot-cli",
            "run_ref": ".omo/workers/runs/example-dispatch.yaml",
            "task_yaml": ".omo/tasks/active/TASK-1.yaml",
            "handoff_refs": [".omo/workers/runs/example-review.md"],
            "gates": {"approval_ref": None},
            "execution_context": {
                "space_ref": "spaces/system-space.yaml",
                "membership_ref": "governor-membership",
                "action": "project.dispatch",
                "admission_contract_ref": "spaces/contract.yaml",
                "required_capabilities": ["project.dispatch"],
                "decision_mode": "conditional_approval",
            },
        },
    )

    result = request_conditional_approval(
        tmp_path,
        Path(".omo/workers/runs/example-envelope.yaml"),
        requested_by="copilot-cli",
        now="2026-05-31T12:30:00Z",
    )

    approval_path = tmp_path / result["approval_ref"]
    proposal_path = tmp_path / ".omo" / "_truth" / "task-center" / "proposals" / f"{result['proposal_id']}.yaml"
    envelope = yaml.safe_load((tmp_path / ".omo" / "workers" / "runs" / "example-envelope.yaml").read_text(encoding="utf-8"))

    assert approval_path.exists()
    assert proposal_path.exists()
    assert envelope["gates"]["approval_ref"] == result["approval_ref"]

    approval = yaml.safe_load(approval_path.read_text(encoding="utf-8"))
    assert approval["approval_status"] == "requested"
    assert approval["release_scope"]["exact_action"] == "project.dispatch"
    assert approval["refs"]["task_ref"] == ".omo/tasks/active/TASK-1.yaml"
    assert approval["refs"]["run_ref"] == ".omo/workers/runs/example-dispatch.yaml"
    assert approval["refs"]["review_ref"] == ".omo/workers/runs/example-review.md"

    proposal = yaml.safe_load(proposal_path.read_text(encoding="utf-8"))
    assert proposal["status"] == "proposed"
    assert proposal["target"]["ref"] == result["approval_ref"]
    assert proposal["changes"]["set"]["approval_status"] == "granted"
