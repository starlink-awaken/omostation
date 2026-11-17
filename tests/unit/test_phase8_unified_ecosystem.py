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


def _cockpit_missing(exc: ModuleNotFoundError) -> bool:
    name = exc.name or ""
    return name == "cockpit" or name.startswith("cockpit.")


def _load_optional(module_name: str, file_path: Path) -> Any:
    """子模块 (cockpit) 未检出时返回 None, 由依赖它的用例各自 skip。

    2026-11-18: 本文件有 4 处模块级加载最终都 `import cockpit` (含两份住在校内
    `bin/_archive/` 的归档脚本)。子模块未检出时模块级加载失败 ⇒ **整份文件**
    collection error, 而 9 条用例里只有 5 条真的需要 cockpit —— 与 2026-09-20/21
    那次「9 个 collection error, 含 3 个与之无关的」是同一形状, 不再重演。
    只吞 `cockpit` 的 ModuleNotFoundError, 其余照常抛 (避免掩盖真缺陷)。
    """
    if not file_path.is_file():
        return None
    try:
        return _load_module_from_file(module_name, file_path)
    except ModuleNotFoundError as exc:
        if not _cockpit_missing(exc):
            raise
        return None


def _require(mod: Any, label: str) -> Any:
    if mod is None:
        pytest.skip(f"cockpit 子模块未检出, {label} 不可用 (检出形态, 不是回归)")
    return mod


# 2026-11-18: `env_resolver` 属 projects/cockpit (子模块)。模块级无条件加载会让
# **整份文件** 在子模块未检出的树上 collection error —— 而 9 条用例里只有
# `test_env_resolver_workspace_paths` 一条真的需要它, 其余 8 条测的是仓内脚本。
# 这与 2026-09-20/21 那次「9 个 collection error, 含 3 个与之无关的」是同一形状。
_ENV_RESOLVER_PATH = WORKSPACE / "projects" / "cockpit" / "src" / "cockpit" / "env_resolver.py"
env_resolver = _load_optional("env_resolver", _ENV_RESOLVER_PATH)


# 2026-09-20/21: 这两个脚本因 bin 配额 (add1=delete1, AGENTS.md §Step B.0.5) 被归档 ——
# 活跃路径已不存在, 但归档物仍在仓 (bin/_archive/)。此前测试仍指向活跃路径,
# 导致模块级 import 失败 → 本文件全部 9 个测试 collection error (含 3 个与之无关的)。
# 修复: 从归档路径加载 (保留行为契约), 并新增退役状态断言。
_DAEMON_WATCHDOG_ARCHIVE = WORKSPACE / "bin" / "_archive" / "2026-09-20-bin-quota-offset" / "daemon-watchdog.py"
_SCENARIO_RUNNER_ARCHIVE = WORKSPACE / "bin" / "_archive" / "2026-09-21-bin-quota-offset" / "real-scenario-runner.py"
DAEMON_WATCHDOG_RETIRED_PATH = WORKSPACE / "bin" / "gac" / "daemon-watchdog.py"
SCENARIO_RUNNER_RETIRED_PATH = WORKSPACE / "bin" / "ssot" / "real-scenario-runner.py"

daemon_watchdog = _load_optional("daemon_watchdog", _DAEMON_WATCHDOG_ARCHIVE)
real_scenario_runner = _load_optional("real_scenario_runner", _SCENARIO_RUNNER_ARCHIVE)

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

_COCKPIT_ENTRY = WORKSPACE / "bin" / "cockpit"
try:
    cockpit_globals = runpy.run_path(str(_COCKPIT_ENTRY), run_name="cockpit_test")
except ModuleNotFoundError as exc:
    if not _cockpit_missing(exc):
        raise
    cockpit_globals = None
cockpit_main = cockpit_globals["main"] if cockpit_globals else None


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
    _require(cockpit_main, "bin/cockpit")
    argv = ["cockpit", "--help"]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        cockpit_main()
    assert exc.value.code == 0
    output = capsys.readouterr()
    assert "cockpit — Workspace L3 统一入口" in output.out or "快速入口" in output.out


def test_retired_governance_scripts_refuse_before_effects(tmp_path, monkeypatch, capsys):
    _require(daemon_watchdog, "daemon_watchdog")
    _require(real_scenario_runner, "real_scenario_runner")
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
    _require(daemon_watchdog, "daemon_watchdog")
    _require(real_scenario_runner, "real_scenario_runner")
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
    _require(daemon_watchdog, "daemon_watchdog")
    assert daemon_watchdog.HEALTH_URL.endswith("/health")
    assert daemon_watchdog.STATUS_FILE.name == "daemon-watchdog.json"


def test_retired_scripts_are_archived_not_active():
    """退役状态: 活跃路径不得回潮, 归档物须在仓 (防"误恢复一个已腐化脚本")。

    2026-09-20/21 bin 配额归档后, services.yaml 已以
    `enabled: false + disabled_reason` 登记, cockpit 侧为 deprecated stub。
    本测试锁住对应的文件层事实。
    """
    for retired, archived in (
        (DAEMON_WATCHDOG_RETIRED_PATH, _DAEMON_WATCHDOG_ARCHIVE),
        (SCENARIO_RUNNER_RETIRED_PATH, _SCENARIO_RUNNER_ARCHIVE),
    ):
        assert not retired.exists(), f"退役脚本不得回到活跃路径: {retired}"
        assert archived.is_file(), f"归档物须在仓: {archived}"


def test_root_retirement_contract_covers_all_bypasses():
    assert {"daemon", "watchdog", "scenario", "top", "run"} == set(RETIRED_COMMANDS)


def test_scenario_runner_defers_yaml_import():
    tree = ast.parse(_SCENARIO_RUNNER_ARCHIVE.read_text(encoding="utf-8"))
    top_level_yaml_imports = [
        node
        for node in tree.body
        if (isinstance(node, ast.Import) and any(alias.name == "yaml" for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "yaml")
    ]
    assert not top_level_yaml_imports

    load_scenario = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "load_scenario"
    )
    assert any(
        (isinstance(node, ast.Import) and any(alias.name == "yaml" for alias in node.names))
        or (isinstance(node, ast.ImportFrom) and node.module == "yaml")
        for node in load_scenario.body
    )


def test_env_resolver_workspace_paths():
    _require(env_resolver, f"env_resolver ({_ENV_RESOLVER_PATH})")
    # 本用例断言 setup_workspace_paths() 把这三个子模块的 src 加进 sys.path,
    # 缺任一个都会让断言失真 —— 那时 skip 比 fail 诚实 (检出形态, 不是回归)。
    for _proj in ("omo", "ecos", "agora"):
        if not (WORKSPACE / "projects" / _proj / "src").is_dir():
            pytest.skip(f"projects/{_proj} 未检出 —— 本用例断言其 src 被加进 sys.path")
    root = env_resolver.get_workspace_root()
    assert (root / "AGENTS.md").exists()
    assert (root / "projects").is_dir()
    assert str(root / "projects" / "omo" / "src") in sys.path
    assert str(root / "projects" / "ecos" / "src") in sys.path
    assert str(root / "projects" / "agora" / "src") in sys.path


def test_weijian_domain_scenario_evaluation():
    _require(real_scenario_runner, "real_scenario_runner")
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
    _require(real_scenario_runner, "real_scenario_runner")
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
