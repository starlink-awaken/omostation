"""Tests for ADR-0223 phase-gate-check (real module)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "bin/gac/phase-gate-check.py"
    name = "phase_gate_check_mod"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_blocks_delivery_when_phase2_locked(tmp_path: Path):
    mod = _load()
    # minimal scope + locked verdict
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/phase-scope.yaml").write_text(
        """
version: 1
escape_dir: .omo/_delivery/phase-escape
phases:
  phase2:
    id: phase2
    name: delivery
    unlock: {verdict_key: phases.phase2.unlocked, equals: true}
    paths: ["bin/delivery/**"]
""",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_truth/registry/phase-verdict.yaml").write_text(
        """
version: 1
phases:
  phase2:
    unlocked: false
""",
        encoding="utf-8",
    )
    r = mod.check_phases(tmp_path, ["bin/delivery/scheduler.py"])
    assert r["ok"] is False
    assert r["blocks"]
    assert r["blocks"][0]["phase"] == "phase2"


def test_allows_when_unlocked(tmp_path: Path):
    mod = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/phase-scope.yaml").write_text(
        """
version: 1
phases:
  phase2:
    id: phase2
    unlock: {verdict_key: phases.phase2.unlocked, equals: true}
    paths: ["bin/delivery/**"]
""",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_truth/registry/phase-verdict.yaml").write_text(
        """
phases:
  phase2: {unlocked: true}
""",
        encoding="utf-8",
    )
    r = mod.check_phases(tmp_path, ["bin/delivery/x.py"])
    assert r["ok"] is True


def test_escape_allows_locked_phase(tmp_path: Path):
    mod = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_delivery/phase-escape").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/phase-scope.yaml").write_text(
        """
version: 1
escape_dir: .omo/_delivery/phase-escape
phases:
  phase2:
    id: phase2
    unlock: {verdict_key: phases.phase2.unlocked, equals: true}
    paths: ["bin/delivery/**"]
""",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_truth/registry/phase-verdict.yaml").write_text(
        "phases:\n  phase2: {unlocked: false}\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_delivery/phase-escape/hot.json").write_text(
        json.dumps(
            {
                "id": "hot-escape",
                "phase": "phase2",
                "pr_number": "999",
                "reason": "test",
                "active": True,
            }
        ),
        encoding="utf-8",
    )
    r = mod.check_phases(
        tmp_path,
        ["bin/delivery/x.py"],
        escape_id="hot-escape",
        pr="999",
    )
    assert r["ok"] is True
    assert r["allowed"][0]["reason"] == "escape"


def test_unrelated_paths_allowed_when_locked(tmp_path: Path):
    mod = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/phase-scope.yaml").write_text(
        """
phases:
  phase2:
    id: phase2
    unlock: {verdict_key: phases.phase2.unlocked, equals: true}
    paths: ["bin/delivery/**"]
""",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_truth/registry/phase-verdict.yaml").write_text(
        "phases:\n  phase2: {unlocked: false}\n",
        encoding="utf-8",
    )
    r = mod.check_phases(tmp_path, ["README.md", "docs/OTHER.md"])
    assert r["ok"] is True


def _sample_caliber() -> dict:
    return {
        "scheme": "A",
        "physical_gates": [
            {
                "id": "g_del_1",
                "gate": "G-DEL.1",
                "metric_keys": ["g_del_1"],
                "min_physical_hosts": 4,
                "status": "BLOCKED",
                "blocked_reason": "reachable_physical_hosts=2 < 4",
                "physical_only_true_fields": ["meets_physical_gate", "meets_gate"],
            },
            {
                "id": "g_del_3",
                "gate": "G-DEL.3",
                "metric_keys": ["g_del_3"],
                "min_physical_hosts": 2,
                "status": "OPEN",
                "physical_only_true_fields": ["meets_physical_gate", "meets_gate"],
            },
        ],
    }


def test_caliber_rejects_sim_claiming_physical_pass():
    """Sim metrics with meets_gate=true on G-DEL.1 must fail ADR-0225 check."""
    mod = _load()
    report = {
        "env_class": "in-process_simulation",
        "g_del_1": {
            "env": "in-process multi-node simulation (not physical multi-host)",
            "env_class": "in-process_simulation",
            "meets_sim_harness": True,
            "meets_physical_gate": True,  # dishonest
            "meets_gate": True,
        },
        "g_del_3": {
            "env_class": "in-process_simulation",
            "meets_gate": False,
            "meets_physical_gate": False,
        },
    }
    r = mod.check_metrics_caliber(report, _sample_caliber())
    assert r["ok"] is False
    assert any(v["metric_key"] == "g_del_1" for v in r["violations"])


def test_caliber_allows_honest_sim_m2a_style():
    """Honest sim: meets_sim_harness true, physical false → pass caliber."""
    mod = _load()
    report = {
        "env_class": "in-process_simulation",
        "g_del_1": {
            "env": "in-process multi-node simulation (not physical multi-host)",
            "env_class": "in-process_simulation",
            "meets_sim_harness": True,
            "meets_physical_gate": False,
            "meets_gate": False,
        },
        "g_del_3": {
            "env_class": "in-process_simulation",
            "meets_sim_harness": True,
            "meets_physical_gate": False,
            "meets_gate": False,
        },
        "all_physical_gates_pass": False,
        "all_sim_harness_pass": True,
    }
    r = mod.check_metrics_caliber(report, _sample_caliber())
    assert r["ok"] is True
    assert r["violations"] == []


def test_caliber_allows_physical_labeled_pass():
    mod = _load()
    report = {
        "env_class": "physical_multi_host",
        "g_del_1": {
            "env": "physical multi-host mesh",
            "env_class": "physical_multi_host",
            "meets_physical_gate": False,
            "meets_gate": False,
            "physical_hosts": 2,
            "gate_status": "BLOCKED",
        },
        "g_del_3": {
            "env_class": "physical_multi_host",
            "meets_physical_gate": True,
            "meets_gate": True,
            "physical_hosts": 2,
        },
    }
    r = mod.check_metrics_caliber(report, _sample_caliber())
    assert r["ok"] is True


def test_caliber_rejects_g_del_1_pass_with_only_two_hosts():
    """ADR-0226: 2-host physical pass on G-DEL.1 is a violation."""
    mod = _load()
    report = {
        "env_class": "physical_multi_host",
        "g_del_1": {
            "env_class": "physical_multi_host",
            "meets_physical_gate": True,
            "meets_gate": True,
            "physical_hosts": 2,
        },
    }
    r = mod.check_metrics_caliber(report, _sample_caliber())
    assert r["ok"] is False
    rules = {v["rule"] for v in r["violations"]}
    assert "min-hosts-for-physical-pass" in rules or "g-del-1-blocked-fail-closed" in rules


def test_caliber_rejects_blocked_gate_claiming_pass():
    mod = _load()
    report = {
        "g_del_1": {
            "env_class": "physical_multi_host",
            "physical_hosts": 4,
            "meets_gate": True,
            "meets_physical_gate": True,
        }
    }
    r = mod.check_metrics_caliber(report, _sample_caliber())
    assert r["ok"] is False
    assert any(v["rule"] == "g-del-1-blocked-fail-closed" for v in r["violations"])


def test_cli_check_caliber_with_honest_measure(tmp_path: Path):
    """Drive real phase-gate-check --metrics path against live measure_all output."""
    import subprocess

    measure = subprocess.run(
        [sys.executable, str(ROOT / "bin/delivery/measure_all.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert measure.returncode == 0, measure.stderr
    metrics_path = tmp_path / "m.json"
    metrics_path.write_text(measure.stdout, encoding="utf-8")
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "bin/gac/phase-gate-check.py"),
            "--root",
            str(ROOT),
            "--files",
            "README.md",
            "--metrics",
            str(metrics_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert data.get("caliber", {}).get("ok") is True
