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


def test_p6_gate_g_three_way_alignment_consistent_with_plan():
    """P6 status 必须与 plan yaml 一致; 复验后 not_yet_passed 也要一致."""
    plan = _read_yaml(".omo/tasks/planned/OPC-P6-EVOLUTION-LOOP.yaml")
    playbook = _read("docs/OPC-MASTER-EXECUTION-PLAYBOOK.md")

    g_statuses = {sg["id"]: sg["status"] for sg in plan["sub_gates"] if sg.get("id", "").startswith("P6-G")}
    assert len(g_statuses) == 4, f"应该 4 个 P6-G sub-gate, 实际 {len(g_statuses)}"

    # 无论 plan 是 passed 还是 not_yet_passed, signals 必须一致
    if plan.get("gate_status") == "not_yet_passed":
        assert all(
            s == "not_yet_passed" for s in g_statuses.values()
        ), f"P6 not_yet_passed 但 sub-gate 状态非全 not_yet_passed: {g_statuses}"
        # playbook 必须说 P6 仍 in progress, 不假装 passed
        assert "P6: opened for implementation; Gate G in progress" in playbook, (
            f"playbook 应反映 P6 not_yet_passed 状态: \n{playbook[:1000]}"
        )
        # gate_status=not_yet_passed 必须有匹配的 not_yet_passed signal
        assert any(
            "gate_g_not_yet_passed" in sig for sig in plan.get("signals", [])
        ), "P6 not_yet_passed 但缺 gate_g_not_yet_passed signal"
        return

    # passed 路径 (历史回放, 当前没启用)
    assert plan["gate_status"] == "passed"
    expected = {f"P6-G{i}": "passed" for i in range(1, 5)}
    assert g_statuses == expected


def test_p6_self_evolution_tasks_only_in_planned_directory():
    """P6 closeout: self-evolution tasks may only land in planned/, never active/."""
    planned_dir = ROOT / ".omo" / "tasks" / "planned"
    active_dir = ROOT / ".omo" / "tasks" / "active"
    self_evo_planned = list(planned_dir.glob("OPC-P6-SELF-EVOLUTION-*.yaml")) if planned_dir.exists() else []
    self_evo_active = list(active_dir.glob("OPC-P6-SELF-EVOLUTION-*.yaml")) if active_dir.exists() else []
    assert self_evo_active == [], (
        f"self-evolution task leaked into active/: {[p.name for p in self_evo_active]}"
    )
    # planned 中至少 1 条 (n-1 兜底 OR drift fix)
    assert self_evo_planned, "self-evolve produced no planned tasks (drift_count=0 expected 1 nop)"


def test_p6_drift_detector_covers_all_four_kinds():
    """P6-G3: drift detector must scan 4 known kinds (entry/doc/duplicate_facts/agora_bypass)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "opc_p6_drift_detector", ROOT / "scripts" / "opc_p6_drift_detector.py"
    )
    assert spec is not None and spec.loader is not None
    expected = {"entry_drift", "doc_drift", "duplicate_facts", "agora_bypass"}
    import re

    src = (ROOT / "scripts" / "opc_p6_drift_detector.py").read_text(encoding="utf-8")
    found = {m.group(1) for m in re.finditer(r"detect_(\w+)\(", src) if not m.group(1).startswith("_")}
    assert expected.issubset(found), f"drift detector missing kinds: {expected - found}"


def test_p7_gate_h_three_way_alignment_closed_2026_06_12():
    """P7 status 必须与 plan yaml + 自身 phase-gate 报告一致.

    2026-06-12 复验: H2 closeout 自身 phase-gate 报告反证 (P7 not_yet_passed).
    防止 task yaml 标 passed 但 phase-gate 报告说不 passed 的自相矛盾.
    """
    plan = _read_yaml(".omo/tasks/planned/OPC-P7-RELEASE-TRAIN.yaml")
    playbook = _read("docs/OPC-MASTER-EXECUTION-PLAYBOOK.md")

    h_statuses = {sg["id"]: sg["status"] for sg in plan["sub_gates"] if sg.get("id", "").startswith("P7-H")}
    assert len(h_statuses) == 5, f"应该 5 个 P7-H sub-gate, 实际 {len(h_statuses)}"

    # 自洽: phase-gate 报告里 P7 | Gate H | not_yet_passed,
    # 则 plan.yaml 的 gate_status 也必须 not_yet_passed
    phase_gate_path = ROOT / ".omo" / "_delivery" / "phase-gate" / "2026-06-12.md"
    if phase_gate_path.exists():
        gate_report = phase_gate_path.read_text(encoding="utf-8")
        report_says_p7_not_passed = "P7 | Gate H | not_yet_passed" in gate_report
        report_says_p7_passed = "P7 | Gate H | passed" in gate_report
        if report_says_p7_not_passed:
            # 报告说 P7 没 passed → plan 不能说 passed
            assert plan.get("gate_status") != "passed", (
                "phase-gate 报告说 P7 not_yet_passed, 但 plan.yaml gate_status=passed. 自相矛盾."
            )
        if report_says_p7_passed:
            assert plan.get("gate_status") == "passed", (
                "phase-gate 报告说 P7 passed, 但 plan.yaml gate_status != passed. "
                "自相矛盾."
            )

    if plan.get("gate_status") == "not_yet_passed":
        # 当前状态: 复验后回退, H5 单独 passed, H1-H4 not_yet_passed
        assert any(
            s == "passed" for s in h_statuses.values()
        ), f"当前应至少 H5 passed: {h_statuses}"
        assert "P7: opened for implementation; Gate H in progress" in playbook
        # gate_status=not_yet_passed 必须有匹配的 not_yet_passed signal
        # (允许混有 passed sub-gate signal 如 h5_passed)
        assert any(
            "gate_h_not_yet_passed" in sig for sig in plan.get("signals", [])
        ), "P7 not_yet_passed 但缺 gate_h_not_yet_passed signal"
        return

    # 历史回放路径
    assert plan["gate_status"] == "passed"
    expected = {f"P7-H{i}": "passed" for i in range(1, 6)}
    assert h_statuses == expected


def test_p7_release_cycle_runner_wrote_three_artifacts():
    """P7-H1: release cycle runner must write notes (CHANGELOG), cycle json, retrospective."""
    notes_path = ROOT / ".omo" / "_delivery" / "release" / "CHANGELOG.md"
    assert notes_path.exists(), "release notes CHANGELOG.md not written"
    notes_text = notes_path.read_text(encoding="utf-8")
    assert "### Summary" in notes_text
    assert "### Validation" in notes_text
    assert "### Debt" in notes_text

    cycle_files = list((ROOT / ".omo" / "_delivery" / "release").glob("v*.json"))
    assert cycle_files, "no cycle json written"

    retro_dir = ROOT / ".omo" / "tasks" / "registry" / "done" / "OPC-P7-H1"
    retros = list(retro_dir.glob("retrospective-v*.md"))
    assert retros, "no retrospective written"


def test_p7_doc_lint_zero_drift_at_closeout():
    """P7-H4: doc lint must report drift_total=0 (or have an explicit evidence for any drift)."""
    import json
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lint_path = ROOT / ".omo" / "_delivery" / "doc-lint" / f"{today}.json"
    if not lint_path.exists():
        # fall back: any .json in dir from last 7 days
        candidates = sorted((ROOT / ".omo" / "_delivery" / "doc-lint").glob("*.json"))
        assert candidates, "no doc-lint output"
        lint_path = candidates[-1]
    payload = json.loads(lint_path.read_text(encoding="utf-8"))
    assert payload.get("drift_total") == 0, f"doc-lint reported drift_total={payload.get('drift_total')}"


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
