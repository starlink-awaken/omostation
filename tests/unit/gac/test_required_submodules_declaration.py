"""门禁的「check 声明所需子模块」机制。

用途：子模块未检出时，那些**不可能测出结论**的 check 归 not_measured
（reason=dependencies_unchecked），不再与真缺陷同形。判据是**声明**，不是报错文本匹配；
CI 递归检出全部子模块 ⇒ 这张表在 CI 永不触发。见债条目 GATE-CLEAN-CHECKOUT-NOISE。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "gac" / "gac-local-gate.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("gate_required_submodules", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_no_declaration_is_not_classified(mod):
    assert mod._dependencies_unchecked("some-other-check", {"projects/ecos"}) == (None, {})


def test_all_required_checked_out_is_not_classified(mod):
    unchecked: set[str] = set()
    assert mod._dependencies_unchecked("test-gac-engine", unchecked) == (None, {})


def test_unchecked_dependency_is_classified(mod):
    reason, detail = mod._dependencies_unchecked("governance-evolution", {"projects/agora"})
    assert reason == "dependencies_unchecked"
    # 只报真正未检出的那一个（cockpit 假定已检出）
    assert detail["unchecked"] == ["projects/agora"]
    assert detail["required_submodules"] == ["projects/agora", "projects/cockpit"]


def test_one_of_several_checked_out_still_classifies(mod):
    """部分检出 ⇒ 仍属输入没备齐（声明里任一条缺席都算）。"""
    reason, _ = mod._dependencies_unchecked(
        "governance-evolution", {"projects/agora", "projects/cockpit"}
    )
    assert reason == "dependencies_unchecked"


def test_declaration_table_has_no_dead_check_ids(mod):
    """防漂移：表里每个 id 必须真的在门禁 check 全集里，否则声明静默失效。"""
    known = {g["id"] for g in mod.GATES_LIST}
    dead = sorted(set(mod.REQUIRED_SUBMODULES) - known)
    assert dead == [], f"声明了不存在的 check id: {dead}"


def test_declared_paths_exist_in_gitmodules(mod):
    """防拼错：声明的子模块路径必须在 .gitmodules 里。"""
    text = (mod.WORKSPACE / ".gitmodules").read_text(encoding="utf-8")
    declared = {p for paths in mod.REQUIRED_SUBMODULES.values() for p in paths}
    missing = sorted(p for p in declared if f"path = {p}" not in text)
    assert missing == [], f"声明的子模块路径不在 .gitmodules 里: {missing}"


def test_key_declarations_are_present(mod):
    """抽样钉住关键条目 —— 防「声明被静默删掉而其后果无人察觉」。

    不复制整张表（那会变成第二份真相源）；只钉本机制建立时覆盖的几类。
    """
    assert mod.REQUIRED_SUBMODULES["agent-workflow-lint"] == ("projects/omo",)
    assert mod.REQUIRED_SUBMODULES["doc-ssot-lint"] == ("projects/ecos",)
    assert mod.REQUIRED_SUBMODULES["governance-semantic-gate"] == ("projects/ecos",)
    assert mod.REQUIRED_SUBMODULES["mof-capabilities-drift-check"] == ("projects/ecos",)
    assert mod.REQUIRED_SUBMODULES["m4-bootstrap-reflex"] == ("projects/ecos",)
    assert mod.REQUIRED_SUBMODULES["test-gac-engine"] == ("projects/ecos",)
    assert mod.REQUIRED_SUBMODULES["check-cockpit-ui-dist"] == ("projects/cockpit-ui",)
    assert mod.REQUIRED_SUBMODULES["governance-evolution"] == (
        "projects/agora",
        "projects/cockpit",
    )
