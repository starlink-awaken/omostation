"""P86 ABCD close: designed-class retest + STOP gate blocks new no-evidence ADV.

Drives real shipped entry points:
- bin/collab/scenario_lib.run_scenario
- bin/gac/check-scenario-growth.main
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCN = ROOT / ".omo/_delivery/collab-scenarios"
sys.path.insert(0, str(ROOT / "bin/collab"))

from scenario_lib import load_scenario, run_scenario  # noqa: E402

DESIGNED = [
    "ADV01-circular-dependency.yaml",
    "ADV03-deadlock-unresolved.yaml",
    "ADV05-broken-chain.yaml",
    "ADV07-double-claim.yaml",
    "ADV09-partial-failure.yaml",
    "ADV11-resource-starvation.yaml",
]


def test_designed_conflict_classes_pass_rate_ge_60pct() -> None:
    """已设计类复测: 成功率 ≥60% (本集 6 场景)."""
    results = []
    for name in DESIGNED:
        path = SCN / name
        assert path.is_file(), f"missing designed scenario {name}"
        r = run_scenario(load_scenario(path))
        results.append((name, r.passed))
    passed = sum(1 for _, ok in results if ok)
    rate = passed / len(results)
    assert rate >= 0.60, f"designed-class pass rate {rate:.0%} < 60%: {results}"
    assert passed == len(results), f"expected all designed pass, got {results}"


def test_scenario_growth_blocks_new_adv_without_evidence() -> None:
    """STOP: 新增 ADV 无 real_occurrence_evidence → check-scenario-growth exit 1."""
    with tempfile.TemporaryDirectory() as td:
        tw = Path(td)
        # minimal workspace layout for the gate
        scen = tw / ".omo/_delivery/collab-scenarios"
        reg = tw / ".omo/_truth/registry"
        scen.mkdir(parents=True)
        reg.mkdir(parents=True)
        # empty baselines → any no-evidence ADV is blocking
        (reg / "baseline-scenario-growth.txt").write_text("# empty freeze\n", encoding="utf-8")
        (reg / "baseline-scenario-detectors.txt").write_text("0\n", encoding="utf-8")
        # stub scenario_lib with zero detectors (avoid detector_growth noise)
        lib = tw / "bin/collab"
        lib.mkdir(parents=True)
        (lib / "scenario_lib.py").write_text("# stub\n", encoding="utf-8")
        # new ADV without evidence (number > default irrelevant; not in baseline)
        (scen / "ADV999-stop-gate-probe.yaml").write_text(
            "id: ADV999-stop-gate-probe\nadversarial: true\n"
            "description: probe\ninject: []\nverdict: []\n",
            encoding="utf-8",
        )
        # copy gate script from repo
        gate_src = ROOT / "bin/gac/check-scenario-growth.py"
        gate_dst = tw / "bin/gac"
        gate_dst.mkdir(parents=True)
        shutil.copy(gate_src, gate_dst / "check-scenario-growth.py")
        proc = subprocess.run(
            [
                sys.executable,
                str(gate_dst / "check-scenario-growth.py"),
                "--workspace",
                str(tw),
                "--json",
            ],
            capture_output=True,
            text=True,
            cwd=str(tw),
        )
        assert proc.returncode != 0, f"expected blocking fail, stdout={proc.stdout}"
        assert "no_evidence_blocking" in proc.stdout or "ADV999" in proc.stdout


def test_scenario_growth_pass_on_repo_stock() -> None:
    """Stock tree after ABCD freeze: check-scenario-growth exit 0."""
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "bin/gac/check-scenario-growth.py"),
            "--workspace",
            str(ROOT),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


def test_a2_map_true_dispatch_three_types_and_type1_demoted() -> None:
    """Multi-agent 真 dispatch table = types 2–4 only; type1/batch5 demoted.

    - 5.4x must not be a live 优 claim
    - shortfall vs ≥4 multi-agent types must be explicit
    - batch5 must be labeled demote / non multi-agent
    - each of the 3 true-dispatch types links an on-disk audit with ≥2 Ns clocks
    """
    import re

    map_path = ROOT / ".omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md"
    text = map_path.read_text(encoding="utf-8")
    assert "shortfall" in text.lower() or "Shortfall" in text
    assert "3 类型" in text or "仅 3" in text or "3 类" in text
    assert not re.search(r"优\s*\*?\*?5\.4x", text), "5.4x must not be a live 优 claim"
    assert "1.65x" not in text.split("## 定论表")[1].split("## 附录")[0] if "## 定论表" in text else True
    # demote language for batch5
    assert "降级" in text or "DEMOTE" in text or "微基准" in text
    assert "不得" in text or "禁止" in text

    batch5 = ROOT / ".omo/_knowledge/audits/2026-07-29-p86-a2-batch5-simple-independent-equal-work.md"
    b5 = batch5.read_text(encoding="utf-8")
    assert "DEMOTE" in b5 or "降级" in b5
    assert ("不是" in b5 or "非" in b5) and ("真 dispatch" in b5 or "多 agent" in b5)
    assert "禁止" in b5

    true_dispatch = [
        ("ordered + read", "2026-07-29-p86-r1-a2-rejudgment-outputfile.md"),
        ("coupled + write", "2026-07-29-p86-a2-batch3-coupled-write.md"),
        ("independent + write", "2026-07-29-p86-a2-batch4-independent-write.md"),
    ]
    # only the 定论表 section (before 附录) should sell multi-agent clocks
    body = text
    if "## 附录" in text:
        body = text.split("## 附录")[0]
    for marker, audit_name in true_dispatch:
        assert marker in body, f"missing true-dispatch type {marker}"
        assert audit_name in body or audit_name.replace(".md", "") in body
        audit_path = ROOT / ".omo/_knowledge/audits" / audit_name
        assert audit_path.is_file(), f"audit missing: {audit_name}"
        clocks = re.findall(r"\b\d+(?:\.\d+)?s\b", audit_path.read_text(encoding="utf-8"))
        assert len(clocks) >= 2, f"{audit_name} needs collab+solo clocks, got {clocks!r}"

    # 定论表 needs ≥6 wall-clock cells (3× collab+solo), not counting appendix microbench only
    map_clocks = re.findall(r"\b\d+(?:\.\d+)?s\b", body)
    assert len(map_clocks) >= 6, f"true-dispatch section needs ≥6 clocks, got {map_clocks}"


def test_export_dualtrack_w3_target_is_15() -> None:
    """C 波: shipped export target is 15, not obsolete 30/45/60."""
    src = (ROOT / "bin/collab/export-dualtrack.py").read_text(encoding="utf-8")
    assert "W3_DONE_TARGET = 15" in src
    assert "W3_DONE_TARGET = 30" not in src
    state = (ROOT / ".omo/state/collab-dualtrack.yaml").read_text(encoding="utf-8")
    assert "w3_done_target: 15" in state or "w3_done_target:15" in state
    assert "w3_done_target: 30" not in state


def test_brief_monthly_15_and_obsolete_ramp() -> None:
    text = (ROOT / "BRIEF.md").read_text(encoding="utf-8")
    assert "**15**" in text or "| **15**" in text or "15" in text
    assert "作废" in text
    assert "30" in text and "45" in text and "60" in text
    assert "简单独立批量" in text


def test_adr_0247_amend_aligned_with_shortfall() -> None:
    """ADR-0247 amend must not claim 4-type true-dispatch or 5.4x as evidence."""
    text = (ROOT / ".omo/_knowledge/decisions/0247-strategic-pivot-collab-first-physical-deferred.md").read_text(
        encoding="utf-8"
    )
    assert "Amend" in text
    assert "4 类型真 dispatch" not in text
    assert "3 类型" in text or "shortfall" in text.lower() or "Shortfall" in text or "ADR-0289" in text
    assert "未闭环" in text or "政策" in text


def test_brief_dualtrack_pointer_no_hardcoded_scenario_total() -> None:
    """BRIEF collab section points to dualtrack SSOT; no stale scenario_total hardcode block."""
    text = (ROOT / "BRIEF.md").read_text(encoding="utf-8")
    assert "collab-dualtrack.yaml" in text
    assert "勿抄" in text or "禁止在本文件硬编码" in text
    # removed stale snapshot lines
    assert "场景总数: `134`" not in text
    assert "对抗集: `30`" not in text


def test_high_traffic_audits_have_a2_supersede_banner() -> None:
    required = [
        "2026-07-29-p86-c-wave-escalation.md",
        "2026-07-29-p86-a3-completion-rootcause.md",
        "2026-07-29-p86-ab-wave-progress.md",
    ]
    for name in required:
        p = ROOT / ".omo/_knowledge/audits" / name
        t = p.read_text(encoding="utf-8")
        assert "A2 SSOT 已 supersede" in t, f"{name} missing supersede banner"
        assert "2026-07-29-p86-a2-collaboration-gain-map.md" in t
