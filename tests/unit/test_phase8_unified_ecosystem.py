"""
Unit tests for Phase 8 Unified Ecosystem, Root Resolver, Watchdog, and Domain Scenarios.
"""

from __future__ import annotations

import ast
import builtins
import importlib
import importlib.util
import json
import re
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

WORKSPACE = Path(__file__).resolve().parents[2]

def _load_module_from_file(module_name: str, file_path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

env_resolver = _load_module_from_file(
    "env_resolver",
    WORKSPACE / "projects" / "cockpit" / "src" / "cockpit" / "env_resolver.py",
)
_ROOT = env_resolver.setup_workspace_paths()


daemon_watchdog = _load_module_from_file("daemon_watchdog", WORKSPACE / "bin" / "gac" / "daemon-watchdog.py")
real_scenario_runner = _load_module_from_file("real_scenario_runner", WORKSPACE / "bin" / "ssot" / "real-scenario-runner.py")

RETIRED_COMMANDS = ["daemon", "watchdog", "scenario", "top", "run"]
FORBIDDEN_VALUE_KEYS = {
    "human_verdict",
    "human_verdict_id",
    "decision_outcome",
    "decision_outcome_id",
    "personal_value",
    "value_indicator",
}
EXPECTED_REFUSAL = {
    "ok": False,
    "status": "retired",
    "successor": "Mesh-bound capability admission",
    "successor_status": "pending",
    "retirement_evidence": "Cockpit PR #78",
    "value_indicator_policy": False,
}

cockpit_globals = runpy.run_path(
    str(WORKSPACE / "bin" / "cockpit"), run_name="cockpit_test"
)
cockpit_main = cockpit_globals["main"]


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.parts
    }


def _sentinel(name: str):
    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError(f"retired refusal called forbidden {name}")

    return _raise


def _refusal_payload(message: str) -> dict[str, Any]:
    for line in reversed(message.splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return {"message": message}


def _walk_keys(value: Any):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_keys(nested)


def _assert_refusal_firewall(message: str) -> None:
    payload = _refusal_payload(message)
    assert set(payload) == {*EXPECTED_REFUSAL, "command", "message"}
    assert {key: payload[key] for key in EXPECTED_REFUSAL} == EXPECTED_REFUSAL
    assert isinstance(payload["command"], str)
    assert isinstance(payload["message"], str)
    assert FORBIDDEN_VALUE_KEYS.isdisjoint(set(_walk_keys(payload)))
    assert all(
        not re.search(rf"(?<![A-Za-z0-9_]){re.escape(token)}(?![A-Za-z0-9_])", message)
        for token in FORBIDDEN_VALUE_KEYS
    )
    assert "Mesh successor is pending" in payload["message"]
    assert "retirement evidence only" in payload["message"]
    assert "never the delivered successor" in payload["message"]


def _guard_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runpy, "run_path", _sentinel("runpy.run_path"))
    monkeypatch.setattr(runpy, "run_module", _sentinel("runpy.run_module"))
    monkeypatch.setattr(subprocess, "run", _sentinel("subprocess.run"))
    monkeypatch.setattr(importlib, "import_module", _sentinel("importlib.import_module"))
    monkeypatch.setattr(builtins, "open", _sentinel("builtins.open"))
    monkeypatch.setattr(Path, "mkdir", _sentinel("pathlib.Path.mkdir"))
    monkeypatch.setattr(Path, "open", _sentinel("pathlib.Path.open"))
    monkeypatch.setattr(Path, "write_text", _sentinel("pathlib.Path.write_text"))
    for module in (daemon_watchdog, real_scenario_runner):
        monkeypatch.setattr(module.urllib.request, "Request", _sentinel("urllib.request.Request"))
        monkeypatch.setattr(module.urllib.request, "urlopen", _sentinel("urllib.request.urlopen"))

    original_import = builtins.__import__

    def _project_import(name: str, *args: Any, **kwargs: Any):
        if name.split(".", 1)[0] in {"agora", "cockpit", "ecos", "omo"}:
            raise AssertionError(f"retired refusal imported project module {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _project_import)


def test_root_cockpit_entrypoint_help(monkeypatch, capsys):
    argv = ["cockpit", "--help"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        cockpit_main()
    assert exc.value.code == 0
    output = capsys.readouterr()
    assert "cockpit — Workspace L3 统一入口" in output.out or "快速入口" in output.out


def test_retired_governance_scripts_refuse_before_effects(tmp_path, monkeypatch, capsys):
    before = _snapshot(tmp_path)
    _guard_effects(monkeypatch)
    for module, argv in (
        (daemon_watchdog, ["daemon-watchdog", "--json"]),
        (real_scenario_runner, ["real-scenario-runner", "--dir", str(tmp_path)]),
    ):
        monkeypatch.setattr(module, "_ROOT", tmp_path)
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as exc:
            module.main()
        assert exc.value.code != 0
        output = capsys.readouterr()
        _assert_refusal_firewall(output.out + output.err)

    assert _snapshot(tmp_path) == before


def test_effectful_imported_helpers_refuse_before_effects(tmp_path, monkeypatch, capsys):
    before = _snapshot(tmp_path)
    _guard_effects(monkeypatch)
    calls = (
        (daemon_watchdog.check_daemon_health, (), {}),
        (daemon_watchdog.restart_daemon, (), {}),
        (daemon_watchdog.log_event, ("should not write",), {}),
        (daemon_watchdog.run_watchdog, (), {}),
        (real_scenario_runner.publish_to_bus, ({"status": "APPROVED"},), {}),
        (real_scenario_runner.record_resident_decision, ({"scenario_id": "SC"},), {}),
        (real_scenario_runner.run_all_scenarios, (tmp_path,), {}),
    )

    for helper, args, kwargs in calls:
        with pytest.raises(SystemExit) as exc:
            helper(*args, **kwargs)
        assert exc.value.code != 0
        output = capsys.readouterr()
        _assert_refusal_firewall(output.out + output.err)

    assert _snapshot(tmp_path) == before


def test_daemon_watchdog_retirement_contract():
    assert daemon_watchdog.HEALTH_URL.endswith("/health")
    assert daemon_watchdog.STATUS_FILE.name == "daemon-watchdog.json"


def test_root_retirement_contract_covers_all_bypasses():
    assert {"daemon", "watchdog", "scenario", "top", "run"} == set(RETIRED_COMMANDS)


def test_scenario_runner_defers_yaml_import():
    tree = ast.parse(
        (WORKSPACE / "bin" / "ssot" / "real-scenario-runner.py").read_text(
            encoding="utf-8"
        )
    )
    top_level_yaml_imports = [
        node
        for node in tree.body
        if (
            isinstance(node, ast.Import)
            and any(alias.name == "yaml" for alias in node.names)
        )
        or (isinstance(node, ast.ImportFrom) and node.module == "yaml")
    ]
    assert not top_level_yaml_imports

    load_scenario = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "load_scenario"
    )
    assert any(
        (
            isinstance(node, ast.Import)
            and any(alias.name == "yaml" for alias in node.names)
        )
        or (isinstance(node, ast.ImportFrom) and node.module == "yaml")
        for node in load_scenario.body
    )


def test_env_resolver_workspace_paths():
    root = env_resolver.get_workspace_root()
    assert (root / "AGENTS.md").exists()
    assert (root / "projects").is_dir()
    assert str(root / "projects" / "omo" / "src") in sys.path
    assert str(root / "projects" / "ecos" / "src") in sys.path
    assert str(root / "projects" / "agora" / "src") in sys.path


def test_weijian_domain_scenario_evaluation():
    sc_path = WORKSPACE / "spaces" / "domain-scenarios" / "weijian_hospital_cloud_review.yaml"
    assert sc_path.exists()
    manifest = real_scenario_runner.load_scenario(sc_path)

    res = real_scenario_runner.evaluate_weijian_scenario(manifest)
    assert res["scenario_id"] == "SC-WJ-HOSPITAL-CLOUD-001"
    assert res["domain"] == "work-weijian"
    assert res["status"] == "APPROVED"
    assert len(res["evaluations"]) == 2
    assert res["evaluations"][0]["rule_id"] == "E-POL-WJ-001"
    assert res["evaluations"][0]["verdict"] == "PASS"
    assert res["evaluations"][1]["rule_id"] == "E-POL-WJ-002"
    assert res["evaluations"][1]["verdict"] == "PASS"


def test_tech_transfer_domain_scenario_evaluation():
    sc_path = WORKSPACE / "spaces" / "domain-scenarios" / "tech_transfer_team_allocation.yaml"
    assert sc_path.exists()
    manifest = real_scenario_runner.load_scenario(sc_path)

    res = real_scenario_runner.evaluate_transfer_scenario(manifest)
    assert res["scenario_id"] == "SC-TF-SURGICAL-NAV-001"
    assert res["domain"] == "work-transfer"
    assert res["status"] == "APPROVED"
    assert len(res["evaluations"]) == 2
    assert res["evaluations"][0]["rule_id"] == "E-POL-TF-001"
    assert res["evaluations"][0]["verdict"] == "PASS"
    assert res["evaluations"][1]["rule_id"] == "E-POL-TF-002"
    assert res["evaluations"][1]["verdict"] == "PASS"
