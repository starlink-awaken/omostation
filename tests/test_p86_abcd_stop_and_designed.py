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


def test_a2_map_ssot_has_four_true_dispatch_types() -> None:
    """Structural: A2 map documents ≥4 types with evidence paths."""
    p = ROOT / ".omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md"
    text = p.read_text(encoding="utf-8")
    assert "4/4" in text or "定论" in text
    for marker in ("independent + none", "ordered + read", "coupled + write", "independent + write"):
        assert marker in text, f"missing type row {marker}"
    assert "batch3" in text and "batch4" in text
    assert "禁止混" in text or "不得" in text


def test_brief_monthly_15_and_obsolete_ramp() -> None:
    text = (ROOT / "BRIEF.md").read_text(encoding="utf-8")
    assert "**15**" in text or "| **15**" in text or "15" in text
    assert "作废" in text
    assert "30" in text and "45" in text and "60" in text
    assert "简单独立批量" in text
