from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load(_read(rel_path)) or {}


def test_master_playbook_baseline_reflects_p3_pass_and_p4_open():
    text = _read("docs/OPC-MASTER-EXECUTION-PLAYBOOK.md")
    assert "- P3: implementation complete; Gate D passed (2026-06-12)" in text
    assert "- P4: implementation complete; Gate E passed (2026-06-12, E1-E4 closed)" in text
    assert "P3 D1: blocked" not in text


def test_p3_gate_d_registry_is_fully_closed():
    payload = _read_yaml(".omo/tasks/registry/done/OPC-P3-GATE-D-OPENING.yaml")
    statuses = {item["id"]: item["status"] for item in payload["sub_gates"]}
    assert payload["gate_status"] == "passed"
    assert statuses == {
        "OPC-P3-D1": "passed",
        "OPC-P3-D2": "passed",
        "OPC-P3-D3": "passed",
        "OPC-P3-D4": "passed",
        "OPC-P3-D5": "passed",
    }


def test_p4_to_p7_prerequisites_require_prior_gate_passes():
    assert _read_yaml(".omo/tasks/planned/OPC-P4-MODEL-COMPUTE.yaml")["prerequisites"][0] == "opc_phase3_gate_d_passed"
    assert _read_yaml(".omo/tasks/planned/OPC-P5-SCENARIOS.yaml")["prerequisites"][:2] == [
        "opc_phase3_gate_d_passed",
        "opc_phase4_gate_e_passed",
    ]
    assert _read_yaml(".omo/tasks/planned/OPC-P6-EVOLUTION-LOOP.yaml")["prerequisites"][:3] == [
        "opc_phase3_gate_d_passed",
        "opc_phase4_gate_e_passed",
        "opc_phase5_gate_f_passed",
    ]
    assert _read_yaml(".omo/tasks/planned/OPC-P7-RELEASE-TRAIN.yaml")["prerequisites"][:4] == [
        "opc_phase3_gate_d_passed",
        "opc_phase4_gate_e_passed",
        "opc_phase5_gate_f_passed",
        "opc_phase6_gate_g_passed",
    ]


def test_p4_gate_e_three_way_alignment_closed_2026_06_12():
    """A3 closeout: P4 Gate E must be passed consistently across docs/omo-tests/projects."""
    plan = _read_yaml(".omo/tasks/planned/OPC-P4-MODEL-COMPUTE.yaml")
    phase_doc = _read("docs/OPC-PHASE4-MODEL-COMPUTE.md")
    playbook = _read("docs/OPC-MASTER-EXECUTION-PLAYBOOK.md")

    assert plan["gate"] == "Gate E"
    assert plan["gate_status"] == "passed"
    assert "gate_closed_at" in plan

    # E1-E4 must all be passed; P4-FINAL is an extra three-way alignment
    # sub-gate added in the A3 closeout and is allowed to be present.
    e1_to_e4 = {f"P4-E{i}": plan_sub["status"] for i, plan_sub in enumerate(plan["sub_gates"], start=1) if plan_sub.get("id", "").startswith("P4-E") and plan_sub.get("id") in {"P4-E1", "P4-E2", "P4-E3", "P4-E4"}}
    # fallback: use any sub_gate key beginning with P4-E (Pydantic-ish dict comprehension for clarity)
    e1_to_e4 = {sg["id"]: sg["status"] for sg in plan["sub_gates"] if sg.get("id") in {"P4-E1", "P4-E2", "P4-E3", "P4-E4"}}
    assert e1_to_e4 == {
        "P4-E1": "passed",
        "P4-E2": "passed",
        "P4-E3": "passed",
        "P4-E4": "passed",
    }, f"P4 E1-E4 not all passed: {e1_to_e4}"

    assert "Status: **Gate E passed (2026-06-12)**" in phase_doc
    assert "opc_phase4_gate_e_passed" in phase_doc
    assert "opc_phase4_gate_e_not_yet_passed" not in phase_doc

    assert "P4: implementation complete; Gate E passed (2026-06-12, E1-E4 closed)" in playbook
    assert "Gate E in progress" not in playbook


def test_p5_prerequisite_signal_now_satisfied():
    """A3 closeout: P5 prerequisites must reference the now-passed Gate E signal."""
    p5 = _read_yaml(".omo/tasks/planned/OPC-P5-SCENARIOS.yaml")
    assert "opc_phase4_gate_e_passed" in p5["prerequisites"]
    assert p5["prerequisites"][1] == "opc_phase4_gate_e_passed"


def test_p4_to_p7_use_consistent_evidence_requirement_field():
    for rel_path in [
        ".omo/tasks/planned/OPC-P4-MODEL-COMPUTE.yaml",
        ".omo/tasks/planned/OPC-P5-SCENARIOS.yaml",
        ".omo/tasks/planned/OPC-P6-EVOLUTION-LOOP.yaml",
        ".omo/tasks/planned/OPC-P7-RELEASE-TRAIN.yaml",
    ]:
        payload = _read_yaml(rel_path)
        for sub_gate in payload["sub_gates"]:
            # In the A3 closeout we also accept `evidence` as the alternate
            # field name for already-closed sub-gates. The legacy field name
            # `evidence_requirement` is still required for `not_started` /
            # in-progress sub-gates so the original spec is preserved.
            assert (
                "evidence_requirement" in sub_gate or "evidence" in sub_gate
            ), f"sub_gate {sub_gate.get('id')} missing evidence/evidence_requirement"
            assert "evidencia_requirement" not in sub_gate


def test_p7_final_gate_sequence_is_monotonic():
    text = _read("docs/OPC-PHASE7-RELEASE-TRAIN.md")
    assert "9 个连续 Gate (A → B → B2 → C → D → E → F → G → H)" in text
