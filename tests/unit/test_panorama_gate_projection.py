import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_gate_projection", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_gates_preserves_partial_results_when_wrapper_exits_nonzero(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    payload = {
        "all_ok": False,
        "gates": [
            {"gate": "A1 Workflow/Git", "ok": True, "exit_code": 0, "output": "PASS"},
            {"gate": "A2 Resident/Host", "ok": False, "exit_code": 1, "output": "non-zero: ['stale_beats']"},
        ],
    }
    monkeypatch.setattr(module, "run", lambda command, timeout=120: (1, json.dumps(payload)))
    monkeypatch.setattr(module, "collect_a6_gate", lambda: {"id": "A6", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a7_gate", lambda: {"id": "A7", "verdict": "NOT_ADMITTED"})
    monkeypatch.setattr(module, "collect_a8_gate", lambda: {"id": "A8", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None: {"id": "A9", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_rf0_gate", lambda: {"id": "RF0", "verdict": "NOT_ADMITTED"})

    gates = {gate["id"]: gate for gate in module.collect_gates()}

    assert gates["A1"]["verdict"] == "PASS"
    assert gates["A1"]["live"] is True
    assert gates["A2"]["verdict"] == "FAIL"
    assert gates["A2"]["live"] is True
    assert "stale_beats" in gates["A2"]["detail"]


def test_collect_gates_fails_closed_on_invalid_health_payload(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "run", lambda command, timeout=120: (1, "not-json"))
    monkeypatch.setattr(module, "collect_a6_gate", lambda: {"id": "A6", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a7_gate", lambda: {"id": "A7", "verdict": "NOT_ADMITTED"})
    monkeypatch.setattr(module, "collect_a8_gate", lambda: {"id": "A8", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None: {"id": "A9", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_rf0_gate", lambda: {"id": "RF0", "verdict": "NOT_ADMITTED"})

    gates = {gate["id"]: gate for gate in module.collect_gates()}

    assert [gates[gid]["verdict"] for gid in ("A1", "A2", "A3", "A4", "A5")] == ["FAIL"] * 5
    assert all(gates[gid]["live"] is False for gid in ("A1", "A2", "A3", "A4", "A5"))


def test_collect_gates_passes_runtime_and_code_roots(tmp_path, monkeypatch) -> None:
    module = _module()
    runtime_root = tmp_path / "runtime"
    code_root = tmp_path / "code"
    monkeypatch.setattr(module, "ROOT", runtime_root)
    monkeypatch.setattr(module, "CODE_ROOT", code_root)
    seen = {}

    def fake_run(command, timeout=120):
        seen["command"] = command
        payload = {
            "all_ok": True,
            "workspace": str(runtime_root),
            "code_root": str(code_root),
            "gates": [
                {"gate": "A1 Workflow/Git", "ok": True, "exit_code": 0, "output": "PASS"},
                {"gate": "A2 Resident/Host", "ok": True, "exit_code": 0, "output": "all technical checks pass"},
                {"gate": "A3 Governance Python", "ok": True, "exit_code": 0, "output": "PASS"},
                {"gate": "A4 Scheduler", "ok": True, "exit_code": 0, "output": "{}"},
                {"gate": "A5 Reference/Launchd", "ok": True, "exit_code": 0, "output": "all technical checks pass"},
            ],
        }
        return 0, json.dumps(payload)

    monkeypatch.setattr(module, "run", fake_run)
    monkeypatch.setattr(module, "collect_a6_gate", lambda: {"id": "A6", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a7_gate", lambda: {"id": "A7", "verdict": "NOT_ADMITTED"})
    monkeypatch.setattr(module, "collect_a8_gate", lambda: {"id": "A8", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None: {"id": "A9", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_rf0_gate", lambda: {"id": "RF0", "verdict": "NOT_ADMITTED"})

    gates = module.collect_gates()
    command = seen["command"]

    assert command[command.index("--workspace") + 1] == str(runtime_root)
    assert command[command.index("--code-root") + 1] == str(code_root)
    assert [gate["verdict"] for gate in gates[:5]] == ["PASS"] * 5
