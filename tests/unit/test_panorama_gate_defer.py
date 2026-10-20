"""The gate round defers instead of manufacturing FAIL verdicts under load.

Observed on this host: load 7-76 on 18 logical cores made the A1-A5 wrapper and
the A7 read-only API matrix exceed their budgets, so A4/A7 went red on the board
while running them directly by hand passed.  A red board for host reasons is a
false signal; deferring is the honest one.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _load(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("panorama_gate_defer", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "CODE_ROOT", tmp_path)
    home = tmp_path / "home"
    (home / ".local/share/zhixing-dashboard").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    return module


def _stub_collectors(monkeypatch, module):
    monkeypatch.setattr(module, "collect_a6_gate", lambda: {"id": "A6", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a7_gate", lambda: {"id": "A7", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a8_gate", lambda: {"id": "A8", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None, **kwargs: {"id": "A9", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_rf0_gate", lambda: {"id": "RF0", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_reference_cell_gate", lambda: {"id": "RC", "verdict": "PASS"})


def test_gate_round_defers_without_running_the_wrapper(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path)
    _stub_collectors(monkeypatch, module)
    monkeypatch.setattr(module, "gate_round_overloaded", lambda: True)
    calls = []
    monkeypatch.setattr(module, "run", lambda command, timeout=120: calls.append(command) or (0, "{}"))

    gates = {gate["id"]: gate for gate in module.collect_gates()}

    assert calls == []
    assert [gates[gid]["verdict"] for gid in ("A1", "A2", "A3", "A4", "A5")] == ["DEFERRED"] * 5
    assert all(gates[gid]["live"] is False for gid in ("A1", "A2", "A3", "A4", "A5"))
    assert all("load above budget" in gates[gid]["detail"] for gid in ("A1", "A2", "A3", "A4", "A5"))


def test_gate_round_runs_the_wrapper_when_not_overloaded(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path)
    _stub_collectors(monkeypatch, module)
    monkeypatch.setattr(module, "gate_round_overloaded", lambda: False)
    monkeypatch.setattr(module, "run", lambda command, timeout=120: (
        0, json.dumps({"all_ok": True, "gates": [
            {"gate": "A1 Workflow/Git", "ok": True, "exit_code": 0, "output": "PASS"},
            {"gate": "A2 Resident/Host", "ok": True, "exit_code": 0, "output": "PASS"},
            {"gate": "A3 Governance Python", "ok": True, "exit_code": 0, "output": "PASS"},
            {"gate": "A4 Scheduler", "ok": True, "exit_code": 0, "output": "PASS"},
            {"gate": "A5 Reference/Launchd", "ok": True, "exit_code": 0, "output": "PASS"},
        ]})
    ))

    gates = {gate["id"]: gate for gate in module.collect_gates()}

    assert [gates[gid]["verdict"] for gid in ("A1", "A2", "A3", "A4", "A5")] == ["PASS"] * 5
    assert all(gates[gid]["live"] is True for gid in ("A1", "A2", "A3", "A4", "A5"))


def test_a7_defers_without_invoking_the_verifier(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path)
    verifier = tmp_path / "bin/gac/multica-as0-verify.py"
    verifier.parent.mkdir(parents=True)
    verifier.touch()
    monkeypatch.setattr(module, "gate_round_overloaded", lambda: True)
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: calls.append((a, k)) or None)

    report = module.collect_a7_gate()

    assert calls == []
    assert report["verdict"] == "DEFERRED"
    assert "load above budget" in report["detail"]
    assert report["live"] is False
    assert report["depends_on"] == ["A8"]


def test_missing_verifier_still_reports_not_admitted_when_overloaded(monkeypatch, tmp_path):
    """A missing verifier is a real state, not a load artifact; it wins."""
    module = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(module, "gate_round_overloaded", lambda: True)

    report = module.collect_a7_gate()

    assert report["verdict"] == "NOT_ADMITTED"
    assert report["detail"] == "Multica AS0 verifier missing"


def test_overload_threshold_is_configurable_and_validated(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path)

    monkeypatch.delenv("ZHIXING_MAX_LOAD", raising=False)
    assert module._configured_gate_max_load() == module.GATE_MAX_LOAD
    assert module.GATE_MAX_LOAD > 0

    monkeypatch.setenv("ZHIXING_MAX_LOAD", "42")
    assert module._configured_gate_max_load() == 42.0

    for raw in ("0", "-1", "nan", "inf", "not-a-number"):
        monkeypatch.setenv("ZHIXING_MAX_LOAD", raw)
        with pytest.raises(ValueError):
            module._configured_gate_max_load()


def test_overload_check_compares_the_one_minute_load_average(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path)
    samples = iter([12.5, module.GATE_MAX_LOAD + 1.0])
    monkeypatch.setattr(module, "os", SimpleNamespace(
        environ={}, getloadavg=lambda: (next(samples), 0.0, 0.0),
    ))

    assert module.gate_round_overloaded() is False
    assert module.gate_round_overloaded() is True


def test_overload_check_fails_open_when_load_average_is_unavailable(monkeypatch, tmp_path):
    module = _load(monkeypatch, tmp_path)
    monkeypatch.setattr(module, "os", SimpleNamespace(
        environ={}, getloadavg=lambda: (_ for _ in ()).throw(OSError("no loadavg")),
    ))

    assert module.gate_round_overloaded() is False
