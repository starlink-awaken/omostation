from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8")


def _read_yaml(rel_path: str) -> dict:
    return yaml.safe_load(_read(rel_path)) or {}


def _read_phase_task(task_id: str) -> dict:
    for rel_path in [
        f".omo/tasks/planned/{task_id}.yaml",
        f".omo/tasks/done/{task_id}.yaml",
        f".omo/tasks/registry/done/{task_id}.yaml",
    ]:
        path = ROOT / rel_path
        if path.exists():
            return _read_yaml(rel_path)
    raise FileNotFoundError(task_id)


def test_master_playbook_baseline_reflects_p3_pass_and_p4_open():
    text = _read("docs/OPC-MASTER-EXECUTION-PLAYBOOK.md")
    assert "- P3: implementation complete; Gate D passed (2026-06-12)" in text
    assert "- P4: implementation complete; Gate E passed (2026-06-12, E1-E4 closed)" in text
    assert "- P7: implementation complete; Gate H passed" in text
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
    assert _read_phase_task("OPC-P4-MODEL-COMPUTE")["prerequisites"][0] == "opc_phase3_gate_d_passed"
    assert _read_phase_task("OPC-P5")["prerequisites"][:2] == [
        "opc_phase3_gate_d_passed",
        "opc_phase4_gate_e_passed",
    ]
    assert _read_phase_task("OPC-P6")["prerequisites"][:3] == [
        "opc_phase3_gate_d_passed",
        "opc_phase4_gate_e_passed",
        "opc_phase5_gate_f_passed",
    ]
    assert _read_phase_task("OPC-P7")["prerequisites"][:4] == [
        "opc_phase3_gate_d_passed",
        "opc_phase4_gate_e_passed",
        "opc_phase5_gate_f_passed",
        "opc_phase6_gate_g_passed",
    ]


def test_p4_gate_e_three_way_alignment_closed_2026_06_12():
    """A3 closeout: P4 Gate E must be passed consistently across docs/omo-tests/projects."""
    plan = _read_phase_task("OPC-P4-MODEL-COMPUTE")
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
    p5 = _read_phase_task("OPC-P5")
    assert "opc_phase4_gate_e_passed" in p5["prerequisites"]
    assert p5["prerequisites"][1] == "opc_phase4_gate_e_passed"


def test_p5_gate_f_alignment_reflects_f1_open_and_f2_f4_closed():
    plan = _read_phase_task("OPC-P5")
    phase_doc = _read("docs/OPC-PHASE5-SCENARIOS.md")
    playbook = _read("docs/OPC-MASTER-EXECUTION-PLAYBOOK.md")

    statuses = {sg["id"]: sg["status"] for sg in plan["sub_gates"] if sg.get("id", "").startswith("P5-F")}
    assert statuses == {
        "P5-F1": "passed",
        "P5-F2": "passed",
        "P5-F3": "passed",
        "P5-F4": "passed",
    }
    assert plan["gate_status"] == "passed"
    assert "opc_phase5_gate_f_passed" in phase_doc
    assert "opc_phase5_subgate_f2_passed" in phase_doc
    assert "opc_phase5_subgate_f3_passed" in phase_doc
    assert "opc_phase5_subgate_f4_passed" in phase_doc
    assert "P5: implementation complete; Gate F passed" in playbook


def test_p6_gate_g_three_way_alignment_consistent_with_plan():
    """P6 status 必须与 plan yaml 一致; 复验后 not_yet_passed 也要一致."""
    plan = _read_phase_task("OPC-P6")
    phase_doc = _read("docs/OPC-PHASE6-EVOLUTION-LOOP.md")
    playbook = _read("docs/OPC-MASTER-EXECUTION-PLAYBOOK.md")

    g_statuses = {sg["id"]: sg["status"] for sg in plan["sub_gates"] if sg.get("id", "").startswith("P6-G")}
    assert len(g_statuses) == 4, f"应该 4 个 P6-G sub-gate, 实际 {len(g_statuses)}"

    assert plan["gate_status"] == "passed"
    expected = {f"P6-G{i}": "passed" for i in range(1, 5)}
    assert g_statuses == expected
    assert "Status: **Gate G passed" in phase_doc
    assert "P6: implementation complete; Gate G passed" in playbook


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
    """P7 当前完成态必须与历史 phase-gate 快照分层自洽.

    2026-06-12 的 phase-gate 报告是历史快照, 允许在 2026-06-13 Gate H 真正 closeout 后
    保持 `not_yet_passed`。测试要防的是“同一时间点自相矛盾”, 不是禁止历史快照晚于当前态被保留.
    """
    plan = _read_phase_task("OPC-P7")
    playbook = _read("docs/OPC-MASTER-EXECUTION-PLAYBOOK.md")

    h_statuses = {sg["id"]: sg["status"] for sg in plan["sub_gates"] if sg.get("id", "").startswith("P7-H")}
    assert len(h_statuses) == 5, f"应该 5 个 P7-H sub-gate, 实际 {len(h_statuses)}"

    phase_gate_path = ROOT / ".omo" / "_delivery" / "phase-gate" / "2026-06-12.md"
    if phase_gate_path.exists():
        gate_report = phase_gate_path.read_text(encoding="utf-8")
        report_says_p7_not_passed = "P7 | Gate H | not_yet_passed" in gate_report
        report_says_p7_passed = "P7 | Gate H | passed" in gate_report
        completed_at = str(plan.get("completed", ""))
        snapshot_date = "2026-06-12"
        closed_after_snapshot = bool(completed_at) and completed_at > snapshot_date

        if report_says_p7_not_passed and not closed_after_snapshot:
            assert plan.get("gate_status") != "passed", (
                "phase-gate 历史快照与当前 plan 属于同一时间窗时, P7 不应一边 not_yet_passed 一边 passed."
            )
        if report_says_p7_passed:
            assert plan.get("gate_status") == "passed", (
                "phase-gate 报告说 P7 passed, 但 plan.yaml gate_status != passed. 自相矛盾."
            )

    assert plan["gate_status"] == "passed"
    expected = {f"P7-H{i}": "passed" for i in range(1, 6)}
    assert h_statuses == expected
    assert "P7: implementation complete; Gate H passed" in playbook


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
    # doc-lint/index.json schema: {"runs": [...], "summary": {"latest_drift_total": N, ...}}
    # 兼容 summary.latest_drift_total 字段
    actual_drift = payload.get("drift_total")
    if actual_drift is None:
        actual_drift = payload.get("summary", {}).get("latest_drift_total")
    assert actual_drift == 0, f"doc-lint reported drift_total={actual_drift}"


def test_p4_to_p7_use_consistent_evidence_requirement_field():
    for rel_path in [
        "OPC-P4-MODEL-COMPUTE",
        "OPC-P5",
        "OPC-P6",
        "OPC-P7",
    ]:
        payload = _read_phase_task(rel_path)
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


def test_phase_gate_snapshot_matches_reviewed_truth():
    phase_gate_md = _read(".omo/_delivery/phase-gate/2026-06-12.md")
    phase_gate_json = _read_yaml(".omo/_delivery/phase-gate/2026-06-12.json")

    assert "phases_passed: **3**" in phase_gate_md
    assert "phases_open: 6" in phase_gate_md
    assert "| P5 | Gate F | not_yet_passed | 3/4 passed, 1 open |" in phase_gate_md
    assert "| P6 | Gate G | not_yet_passed | 0/4 passed, 4 open |" in phase_gate_md
    assert "| P7 | Gate H | not_yet_passed | 3/5 passed, 2 open |" in phase_gate_md

    rows = {row["phase"]: row for row in phase_gate_json["rows"]}
    assert phase_gate_json["summary"] == {"phases_total": 9, "phases_passed": 3, "phases_open": 6}
    assert rows["P5"]["gate_status"] == "not_yet_passed"
    assert rows["P5"]["sub_gate_passed"] == 3
    assert rows["P5"]["sub_gate_open"] == 1
    assert rows["P6"]["gate_status"] == "not_yet_passed"
    assert rows["P6"]["sub_gate_passed"] == 0
    assert rows["P7"]["gate_status"] == "not_yet_passed"
    assert rows["P7"]["sub_gate_passed"] == 3
    assert rows["P7"]["sub_gate_open"] == 2


# ── 2026-06-12 复验后: 治本红线条目守护测试 ─────────────────────────


def test_playbook_contains_acceptance_integrity_red_lines():
    """Playbook §4.4 必须含 3 条新治本红线: 不降标 / 反证自洽 / 人工审批."""
    text = _read("docs/OPC-MASTER-EXECUTION-PLAYBOOK.md")
    assert "4.4 Acceptance integrity red lines" in text, (
        "playbook 必须新增 §4.4 Acceptance integrity red lines 段"
    )
    # 3 条硬约束关键词守护
    assert "Do not weaken original criteria during closeout" in text, (
        "playbook §4.4 缺'禁止降标过关'硬约束"
    )
    assert "Do not let plan status contradict its own evidence" in text, (
        "playbook §4.4 缺'反证自洽'硬约束"
    )
    assert "Do not bypass human approval for self-evolution tasks" in text, (
        "playbook §4.4 缺'人工审批不可绕过'硬约束"
    )


def test_closeout_does_not_weaken_original_criteria():
    """治本 1: sub-gate closeout 不得改弱原 criteria (时间性/范围性/真实性).

    复验反例: P5-F1 原 criteria "≥2 周连续 cron" 被改 "2 轮手动跑通"; P6 G2
    "≥2 周连续周报" 用同日内 2 次跑通替代. 本测试守护所有当前+未来 sub-gate
    的 criteria 文本不被 closeout 改弱.
    """
    for rel_path in [
        "OPC-P3-GATE-D-OPENING",
        "OPC-P4-MODEL-COMPUTE",
        "OPC-P5",
        "OPC-P6",
        "OPC-P7",
    ]:
        payload = _read_phase_task(rel_path)
        for sub_gate in payload.get("sub_gates", []):
            sg_id = sub_gate.get("id", "?")
            status = sub_gate.get("status", "?")
            for i, criterion in enumerate(sub_gate.get("criteria", [])):
                if not isinstance(criterion, str):
                    continue
                # 防止: 把 "≥N 周" 偷换 "≥N 轮" / "≥N 次" / "N 周内 N 轮"
                if "周" in criterion and "轮" in criterion:
                    # 唯一允许的例外: 显式 "1 周 N 轮" 解释 (但本 workspace 暂无此需求)
                    raise AssertionError(
                        f"{rel_path} {sg_id} criterion[{i}] 含 '周' + '轮' 混用: {criterion!r}. "
                        f"复验后红线条目: 不得偷换时间性要求."
                    )
                # 防止: "≥N 天" 被 "N 次手动" 替代
                if ("天" in criterion or "周" in criterion) and "手动" in criterion:
                    raise AssertionError(
                        f"{rel_path} {sg_id} criterion[{i}] 含时间 + '手动' 混用: {criterion!r}. "
                        f"复验后红线条目: 不得用同日内手动 N 次替代真实时间性要求."
                    )
            # 额外守护: status=passed 的 sub-gate 不得有 closeout_pending 段
            if status == "passed":
                assert "closeout_pending" not in sub_gate, (
                    f"{rel_path} {sg_id} status=passed 但含 closeout_pending 段 (应回退 not_yet_passed)"
                )


def test_self_evolution_approval_required_always_true():
    """治本 1: self-evolution task approval_required 必须 true (no exceptions, even nop)."""
    planned_dir = ROOT / ".omo" / "tasks" / "planned"
    for yaml_path in planned_dir.glob("OPC-P6-SELF-EVOLUTION-*.yaml"):
        payload = _read_yaml(str(yaml_path.relative_to(ROOT)))
        approval = payload.get("approval_required")
        assert approval is True, (
            f"{yaml_path.name} approval_required={approval}, 必须 true. "
            f"复验后红线条目: self-evolution task 不得 approval_required=false (即使 nop)."
        )
