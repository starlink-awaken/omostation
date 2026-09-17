import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin/gac/ruflo-rf0-verify.py"


def _module():
    spec = importlib.util.spec_from_file_location("ruflo_rf0_verify", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _result(argv: list[str], *, rc: int, stdout: str, stderr: str = "") -> dict:
    return {"argv": argv, "rc": rc, "stdout": stdout, "stderr": stderr}


def test_dependency_guard_accepts_only_the_four_read_only_ruflo_probes() -> None:
    module = _module()
    results = [
        _result([module.RUFLO, "version"], rc=0, stdout="3.42.2"),
        _result([module.RUFLO, "doctor"], rc=0, stdout="Summary: 13 passed, 15 warnings"),
        _result([module.RUFLO, "daemon", "status"], rc=0, stdout="Status: STOPPED"),
        _result([module.RUFLO, "status"], rc=1, stdout="not initialized"),
    ]
    ok, offenders = module._dependency_guard(results)
    assert ok is True
    assert offenders == []


def test_dependency_guard_rejects_writer_and_cross_agent_commands() -> None:
    module = _module()
    ok, offenders = module._dependency_guard(
        [
            _result([module.RUFLO, "init"], rc=0, stdout=""),
            _result(["orca", "status", "--json"], rc=0, stdout="{}"),
        ]
    )
    assert ok is False
    assert offenders == ["init", "non-ruflo-command"]


def test_build_report_is_green_only_for_stopped_read_only_isolated_state(
    monkeypatch,
) -> None:
    module = _module()

    def fake_run(argv: list[str], cwd: Path) -> dict:
        assert str(cwd).startswith("/tmp") or "ruflo-rf0-verify-" in str(cwd)
        if argv == [module.RUFLO, "version"]:
            return _result(argv, rc=0, stdout="3.42.2\n")
        if argv == [module.RUFLO, "doctor"]:
            return _result(
                argv,
                rc=0,
                stdout="Summary: 13 passed, 15 warnings\nAll checks passed with some warnings.",
            )
        if argv == [module.RUFLO, "daemon", "status"]:
            return _result(
                argv,
                rc=0,
                stdout="Status: ○ STOPPED\nAI Workers: off (local-only, default)",
            )
        assert argv == [module.RUFLO, "status"]
        return _result(argv, rc=1, stdout="", stderr="RuFlo is not initialized in this directory")

    monkeypatch.setattr(module, "_run", fake_run)
    report = module.build_report()
    assert report["schema"] == "ruflo-rf0-verify/v1"
    assert report == {
        "schema": "ruflo-rf0-verify/v1",
        "ok": True,
        "checks": {
            "binary": True,
            "doctor": True,
            "daemon_stopped": True,
            "workers_off": True,
            "no_second_queue": True,
            "cross_agent_dependency_zero": True,
        },
        "version": "3.42.2",
        "doctor_summary": {"passed": 13, "warnings": 15},
        "daemon": {"status": "STOPPED", "workers_off": True},
        "guard": {"offenders": []},
    }


def test_json_main_fails_closed_without_raw_ruflo_output(monkeypatch, capsys) -> None:
    module = _module()
    monkeypatch.setattr(
        module,
        "build_report",
        lambda: {
            "schema": "ruflo-rf0-verify/v1",
            "ok": False,
            "checks": {"binary": False},
            "raw": "should not leak",
        },
    )
    assert module.main(["--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "ruflo-rf0-verify/v1"
    assert payload["ok"] is False
    assert payload["checks"]["binary"] is False
