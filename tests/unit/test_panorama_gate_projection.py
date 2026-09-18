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
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None, **kwargs: {"id": "A9", "verdict": "PASS"})
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
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None, **kwargs: {"id": "A9", "verdict": "PASS"})
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
    monkeypatch.setattr(module, "collect_a9_gate", lambda payload=None, **kwargs: {"id": "A9", "verdict": "PASS"})
    monkeypatch.setattr(module, "collect_rf0_gate", lambda: {"id": "RF0", "verdict": "NOT_ADMITTED"})

    gates = module.collect_gates()
    command = seen["command"]

    assert command[command.index("--workspace") + 1] == str(runtime_root)
    assert command[command.index("--code-root") + 1] == str(code_root)
    assert [gate["verdict"] for gate in gates[:5]] == ["PASS"] * 5


def test_admission_verifiers_use_code_root_but_runtime_root_cwd(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    runtime_root = tmp_path / "runtime"
    code_root = tmp_path / "code"
    verifier_dir = code_root / "bin/gac"
    verifier_dir.mkdir(parents=True)
    for name in (
        "ruflo-rf0-verify.py", "orca-r0-verify.py", "multica-as0-verify.py",
    ):
        (verifier_dir / name).touch()
    monkeypatch.setattr(module, "ROOT", runtime_root)
    monkeypatch.setattr(module, "CODE_ROOT", code_root)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs.get("cwd")))
        report = {
            "ruflo-rf0-verify.py": {
                "ok": True,
                "checks": {
                    "binary": True, "doctor": True, "daemon_stopped": True,
                    "workers_off": True, "no_second_queue": True,
                    "cross_agent_dependency_zero": True,
                },
                "version": "3.42.2",
                "doctor_summary": {"passed": 13, "warnings": 0},
            },
            "orca-r0-verify.py": {
                "ok": True, "runtime_ready": True,
                "probes": {"passed": 6, "total": 6},
                "r0_transactions": {"accepted": 1, "transactions": [{"ok": True}]},
                "trust": {"write_argv_guard": {"ok": True}},
            },
            "multica-as0-verify.py": {
                "ok": True,
                "api": {"passed": 30, "total": 30},
                "topology": {"passed": 7, "total": 7},
                "trust": {"passed": 3, "total": 3},
            },
        }[Path(command[1]).name]
        return type("Completed", (), {"stdout": json.dumps(report)})()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    reports = [
        module.collect_rf0_gate(),
        module.collect_a6_gate(),
        module.collect_a7_gate(),
    ]

    assert all(report["verdict"] == "PASS" for report in reports)
    assert len(calls) == 3
    for command, cwd in calls:
        assert command[1].startswith(str(code_root / "bin/gac/"))
        assert cwd == runtime_root


def test_multica_gate_budgets_full_readonly_matrix_and_bypasses_hosts(
    tmp_path, monkeypatch
) -> None:
    module = _module()
    runtime_root = tmp_path / "runtime"
    code_root = tmp_path / "code"
    verifier = code_root / "bin/gac/multica-as0-verify.py"
    verifier.parent.mkdir(parents=True)
    verifier.touch()
    monkeypatch.setattr(module, "ROOT", runtime_root)
    monkeypatch.setattr(module, "CODE_ROOT", code_root)
    monkeypatch.setenv("NO_PROXY", "internal.example")
    monkeypatch.setenv("no_proxy", "internal.example")
    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen.update(kwargs)
        return type(
            "Completed",
            (),
            {
                "stdout": json.dumps({
                    "ok": True,
                    "api": {"passed": 30, "total": 30},
                    "topology": {"passed": 7, "total": 7},
                    "trust": {"passed": 3, "total": 3},
                })
            },
        )()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    report = module.collect_a7_gate()

    assert report["verdict"] == "PASS"
    assert module.MULTICA_AS0_TIMEOUT_S >= 240
    assert seen["timeout"] == module.MULTICA_AS0_TIMEOUT_S
    assert seen["cwd"] == runtime_root
    for key in ("NO_PROXY", "no_proxy"):
        hosts = seen["env"][key].split(",")
        assert "internal.example" in hosts
        assert "multica.ai" in hosts
        assert ".multica.ai" in hosts


def test_code_root_health_reports_synced_and_stale(tmp_path, monkeypatch) -> None:
    module = _module()
    runtime_root = tmp_path / "runtime"
    code_root = tmp_path / "code"
    monkeypatch.setattr(module, "ROOT", runtime_root)
    monkeypatch.setattr(module, "CODE_ROOT", code_root)

    def fake_run(command, timeout=120):
        assert command[:3] == ["git", "-C", str(code_root)]
        args = command[3:]
        if args == ["rev-parse", "HEAD"]:
            return 0, "head-oid"
        if args == ["rev-parse", "refs/remotes/origin/main"]:
            return 0, "origin-oid"
        if args == ["status", "--porcelain", "--untracked-files=no"]:
            return 0, ""
        if args == ["rev-list", "--left-right", "--count", "origin/main...HEAD"]:
            return 0, "1\t0"
        raise AssertionError(command)

    monkeypatch.setattr(module, "run", fake_run)
    report = module.collect_code_root_health()
    assert report["verdict"] == "STALE"
    assert report["behind_origin_main"] == 1
    assert report["ahead_origin_main"] == 0
    assert report["dirty_count"] == 0
    assert report["auto_update_performed"] is False
