from __future__ import annotations

from pathlib import Path

from omo.omo_rollout import evaluate_rollout_envelope


def test_evaluate_rollout_envelope_accepts_multi_document_yaml(tmp_path: Path) -> None:
    approval = tmp_path / ".omo" / "workers" / "runs" / "demo-approval.yaml"
    policy = tmp_path / ".omo" / "_truth" / "policies" / "rollout.yaml"
    runtime_boundary = tmp_path / ".omo" / "_truth" / "policies" / "runtime-boundary.yaml"
    envelope = tmp_path / ".omo" / "workers" / "runs" / "demo-envelope.yaml"
    evidence = tmp_path / ".omo" / "_knowledge" / "audits" / "evidence.md"
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("ok\n", encoding="utf-8")
    approval.parent.mkdir(parents=True, exist_ok=True)
    policy.parent.mkdir(parents=True, exist_ok=True)
    runtime_boundary.parent.mkdir(parents=True, exist_ok=True)
    envelope.parent.mkdir(parents=True, exist_ok=True)

    approval.write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "approval_status: granted\n",
        encoding="utf-8",
    )
    policy.write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "rules:\n"
        "  - action: rollout_accept\n"
        "    required_evidence_refs:\n"
        "      - .omo/_knowledge/audits/evidence.md\n"
        "    required_approval_status: granted\n",
        encoding="utf-8",
    )
    runtime_boundary.write_text(
        "---\nstatus: active\nowner: runtime\n---\n---\n"
        "allowed_runtime_roots:\n"
        "  - runtime/logs\n",
        encoding="utf-8",
    )
    envelope.write_text(
        "---\nstatus: active\nowner: runtime\n---\n---\n"
        "execution_context:\n"
        "  space_ref: bos://spaces/demo\n"
        "  membership_ref: demo\n"
        "  action: rollout_accept\n"
        "rollout_context:\n"
        "  rollout_policy_ref: .omo/_truth/policies/rollout.yaml\n"
        "  runtime_boundary_ref: .omo/_truth/policies/runtime-boundary.yaml\n"
        "  runtime_residue_paths:\n"
        "    - runtime/logs/demo.log\n"
        "gates:\n"
        "  approval_ref: .omo/workers/runs/demo-approval.yaml\n",
        encoding="utf-8",
    )

    result = evaluate_rollout_envelope(tmp_path, Path(".omo/workers/runs/demo-envelope.yaml"))

    assert result["decision"] == "allow"
    assert result["acceptance_ready"] is True
    assert result["missing_evidence_refs"] == []
    assert result["disallowed_runtime_paths"] == []
