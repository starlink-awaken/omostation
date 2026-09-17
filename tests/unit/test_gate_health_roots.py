import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _module(relative: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_meta_doctor_separates_runtime_state_from_reference_root(
    tmp_path, monkeypatch, capsys
) -> None:
    module = _module("bin/gac/meta-doctor.py", "meta_doctor_roots_test")
    runtime_root = tmp_path / "runtime"
    reference_root = tmp_path / "code"
    calls = {}

    monkeypatch.setattr(
        module,
        "check_heartbeats",
        lambda ws_root: (calls.__setitem__("heartbeats", ws_root), [])[1],
    )
    monkeypatch.setattr(
        module,
        "collect_references",
        lambda ref_root: (calls.__setitem__("references", ref_root), [])[1],
    )
    monkeypatch.setattr(
        module,
        "annotate_tracking",
        lambda refs, ref_root: (calls.__setitem__("tracking", ref_root), [])[1],
    )
    monkeypatch.setattr(
        module,
        "_script_registry_coverage",
        lambda refs, ref_root: (calls.__setitem__("registry", ref_root), [])[1],
    )
    monkeypatch.setattr(
        module,
        "_submodule_ff_check",
        lambda ref_root: (calls.__setitem__("submodules", ref_root), [])[1],
    )
    monkeypatch.setattr(module, "check_ritual", lambda ws_root: [])

    code = module.main([
        "--workspace", str(runtime_root),
        "--reference-root", str(reference_root),
    ])
    report = json.loads(capsys.readouterr().out)

    assert code == 0
    assert calls["heartbeats"] == runtime_root.resolve()
    assert calls["references"] == reference_root.resolve()
    assert calls["tracking"] == reference_root.resolve()
    assert calls["registry"] == reference_root.resolve()
    assert calls["submodules"] == reference_root.resolve()
    assert report["workspace"] == str(runtime_root.resolve())
    assert report["reference_root"] == str(reference_root.resolve())


def test_gate_health_passes_split_roots_to_reference_checks(
    tmp_path, monkeypatch, capsys
) -> None:
    module = _module("bin/gac/gate-health-check.py", "gate_health_roots_test")
    runtime_root = tmp_path / "runtime"
    code_root = tmp_path / "code"
    calls = []

    def fake_check(name, command, expect_exit=0, cwd=None):
        calls.append({"kind": "check", "name": name, "command": command, "cwd": cwd})
        return {"gate": name, "ok": True, "exit_code": 0, "output": "PASS"}

    def fake_subchecks(name, command, zero_keys, cwd=None):
        calls.append({"kind": "subchecks", "name": name, "command": command, "cwd": cwd})
        return {"gate": name, "ok": True, "exit_code": 0, "output": "all technical checks pass"}

    monkeypatch.setattr(module, "check", fake_check)
    monkeypatch.setattr(module, "check_json_subchecks", fake_subchecks)

    code = module.main([
        "--json", "--workspace", str(runtime_root), "--code-root", str(code_root),
    ])
    report = json.loads(capsys.readouterr().out)
    by_name = {item["name"]: item for item in calls}
    meta_command = by_name["A2 Resident/Host"]["command"]
    scheduler_command = by_name["A4 Scheduler"]["command"]

    assert code == 0
    assert report["workspace"] == str(runtime_root.resolve())
    assert report["code_root"] == str(code_root.resolve())
    assert meta_command[1] == str(code_root.resolve() / "bin/gac/meta-doctor.py")
    assert meta_command[meta_command.index("--workspace") + 1] == str(runtime_root.resolve())
    assert meta_command[meta_command.index("--reference-root") + 1] == str(code_root.resolve())
    assert scheduler_command[1] == str(code_root.resolve() / "bin/scheduler-compile.py")
