"""门禁报告必须自报「子模块包解析到哪棵树」。

背景: 主检出 venv 装了指向 canonical 的 path hook (docs/pitfalls.md
「canonical venv 的 path hook 把 worktree 里的 import omo 静默指向主检出」)。
用该 venv 在 worktree 里跑门禁/测试时, 子模块代码其实来自 canonical ——
读数看着正常, 量的却是另一棵树。2026-11-18 本轮因此污染了 #5410 的验证读数
(那次的「pass」对 import 型加载不成立)。

本文件钉住门禁侧的处置: `interpreter_roots` 字段 + 人在场时可见的横幅。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "gac-local-gate.py"


def _load():
    spec = importlib.util.spec_from_file_location("gac_local_gate_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gac_local_gate_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_report_shape_and_self_consistency():
    mod = _load()
    rep = mod.interpreter_roots_report()
    assert rep["workspace"] == str(mod.WORKSPACE)
    assert set(rep["resolved"]) == set(mod.IMPORT_PROBE_PACKAGES)
    assert set(rep["inside_workspace"]) == set(mod.IMPORT_PROBE_PACKAGES)
    # outside_workspace 必须恰好是 inside_workspace 里为 False 的那些
    assert rep["outside_workspace"] == sorted(
        n for n, ok in rep["inside_workspace"].items() if ok is False
    )


def test_package_resolving_outside_workspace_is_reported(monkeypatch, tmp_path):
    """解析到本树之外的包必须被点名 —— 这正是 path hook 污染形态。"""
    mod = _load()
    outside = tmp_path / "somewhere_else" / "omo" / "__init__.py"
    monkeypatch.setattr(
        mod.importlib.util,
        "find_spec",
        lambda name: SimpleNamespace(origin=str(outside)) if name == "omo" else None,
    )
    rep = mod.interpreter_roots_report()
    assert rep["resolved"]["omo"] == str(outside)
    assert rep["inside_workspace"]["omo"] is False
    assert "omo" in rep["outside_workspace"]


def test_unimportable_package_is_null_not_outside(monkeypatch):
    """探不到的包报 null, 不得被算成「树外」—— 两者含义不同。"""
    mod = _load()

    def _raise(name):
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)

    monkeypatch.setattr(mod.importlib.util, "find_spec", _raise)
    rep = mod.interpreter_roots_report()
    assert rep["resolved"]["cockpit"] is None
    assert rep["inside_workspace"]["cockpit"] is None
    assert rep["outside_workspace"] == []


def test_banner_only_when_something_resolves_outside(capsys):
    mod = _load()
    mod._print_interpreter_roots({"interpreter_roots": {"outside_workspace": []}})
    assert "本工作区之外" not in capsys.readouterr().err

    mod._print_interpreter_roots(
        {
            "interpreter_roots": {
                "outside_workspace": ["omo"],
                "resolved": {"omo": "/somewhere/else/omo/__init__.py"},
            }
        }
    )
    err = capsys.readouterr().err
    assert "本工作区之外" in err
    assert "/somewhere/else/omo/__init__.py" in err


def test_banner_survives_missing_field(capsys):
    mod = _load()
    capsys.readouterr()  # 清掉 import 期 SGF 降级告警, 只留横幅本身
    mod._print_interpreter_roots({})
    mod._print_interpreter_roots({"interpreter_roots": None})
    assert capsys.readouterr().err == ""


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
