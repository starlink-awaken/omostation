"""门禁命令旗标的归一化：两种策略来源都必须拿到 `--json`。

命令的权威面有两个：`projects/ecos` 的 sgf-policy.yaml（子模块在时它说了算）与
DEFAULT_POLICY（fallback）。2026-11-25 实测：只在 DEFAULT_POLICY 里加旗标时，
子模块策略会**整体绕过** ⇒ 依赖 `--json` 的「自报没测成」契约在 CI 与齐备检出上
从未生效（partial 树反而生效，恰好反了）。
"""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "gac" / "gac-local-gate.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("gate_cmd_norm", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _policy_without_flags(mod) -> dict:
    """模拟 submodule 策略：命令齐全但没有 --json。"""
    policy = {"gates": [{"id": name, "command": [cmd]} for name, cmd in (
        ("check-evidence-freshness", "bin/gac/check-evidence-freshness.py"),
        ("dependency-baseline-drift", "bin/mof/gen-dependency-baseline.py"),
        ("check-redline-coverage", "bin/gac/check-redline-coverage.py"),
    )]}
    return policy


def test_adds_required_flags_to_submodule_style_policy(mod):
    out = mod.normalize_gate_commands(_policy_without_flags(mod))
    cmds = {g["id"]: g["command"] for g in out["gates"]}
    assert cmds["check-evidence-freshness"] == ["bin/gac/check-evidence-freshness.py", "--json"]
    # 旗标是**追加**到命令列表, 不做分词
    assert cmds["dependency-baseline-drift"] == ["bin/mof/gen-dependency-baseline.py", "--json"]


def test_undeclared_checks_are_untouched(mod):
    out = mod.normalize_gate_commands(_policy_without_flags(mod))
    cmds = {g["id"]: g["command"] for g in out["gates"]}
    assert cmds["check-redline-coverage"] == ["bin/gac/check-redline-coverage.py"]


def test_idempotent_when_flags_already_present(mod):
    once = mod.normalize_gate_commands(_policy_without_flags(mod))
    snapshot = copy.deepcopy(once)
    twice = mod.normalize_gate_commands(once)
    assert twice == snapshot, "重复归一化必须无副作用"


def test_every_declared_flag_lands_on_both_sources(mod):
    """真实模块级校验：无论 POLICY 来自 submodule 还是 DEFAULT_POLICY，旗标都在。"""
    cmds = {g["id"]: g["command"] for g in mod.GATES_LIST}
    for name, flags in mod.REQUIRED_COMMAND_FLAGS.items():
        assert name in cmds, f"声明的 check 不在门禁集合里: {name}"
        for flag in flags:
            assert flag in cmds[name], f"{name} 缺旗标 {flag}: {cmds[name]}"
