"""登记描述不得再恒为空 —— 有 docstring 的脚本必须派生出描述。

缺陷（2026-11-24 实测）：`bin/ssot/script-registry.py::register()` 把 `description`
硬写成 `""`，且没有任何回填；744 条登记里 **587 条为空**。登记面的意义是**可发现性**，
空描述等于放弃这个字段 —— 而脚本自己的模块 docstring 就是现成的、由维护者手写的权威摘要。

回填后仍空的 46 条**全部**是「脚本自身没有模块 docstring」的那些（0 条脚本缺失），
本文件把这条界线钉住：空描述只许出现在没有 docstring 的地方。
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "bin" / "ssot" / "script-registry.py"


def _tool():
    spec = importlib.util.spec_from_file_location("script_registry_desc_test", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, doc: str) -> Path:
    p = tmp_path / "sample.py"
    p.write_text(f'"""{doc}"""\n', encoding="utf-8")
    return p


def _module_docstring(path: Path) -> str:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return ""
    return (ast.get_docstring(tree) or "").strip()


def test_registered_scripts_with_docstrings_all_have_descriptions() -> None:
    """不变量：description 为空 ⇒ 该脚本没有模块 docstring（或脚本不存在）。"""
    offenders = []
    for entry in sorted((ROOT / "bin" / "_registry" / "scripts").rglob("*.yaml")):
        data = yaml.safe_load(entry.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict) or str(data.get("description") or "").strip():
            continue
        rel = data.get("id")
        script = ROOT / str(rel) if rel else None
        if script is None or not script.is_file():
            continue
        if _module_docstring(script):
            offenders.append(str(rel))
    assert offenders == [], f"这些有 docstring 的脚本仍是空描述: {offenders[:5]}"


def test_derive_description_takes_first_line_and_truncates(tmp_path: Path) -> None:
    tool = _tool()
    one_line = tool.derive_description(_write(tmp_path, "只有一行摘要。"))
    assert one_line == "只有一行摘要。"

    long_first = "首行 " + "x" * 300
    got = tool.derive_description(_write(tmp_path, long_first))
    assert got.startswith("首行 ")
    assert len(got) <= tool.MAX_DESCRIPTION + 1, len(got)


def test_derive_description_folds_continuation_lines(tmp_path: Path) -> None:
    """docstring 首行之后还有内容时只取首行, 不把整段塞进登记面。"""
    tool = _tool()
    doc = "第一行。\n\n第二段不该出现。\n"
    assert tool.derive_description(_write(tmp_path, doc)) == "第一行。"


def test_derive_description_is_empty_without_docstring(tmp_path: Path) -> None:
    tool = _tool()
    bare = tmp_path / "bare.py"
    bare.write_text("x = 1\n", encoding="utf-8")
    assert tool.derive_description(bare) == ""


def test_register_emits_a_derived_description(tmp_path: Path, monkeypatch, capsys) -> None:
    """`register --dry-run` 必须产出非空描述 —— 这就是当初恒为空的那个写入点。"""
    tool = _tool()
    # register() 会做 `REPO_ROOT / path` 与 `relative_to(REPO_ROOT)`，样本必须在它认定的根下。
    monkeypatch.setattr(tool, "REPO_ROOT", tmp_path)
    (tmp_path / "probe_tool.py").write_text(
        '"""Probe tool — 一句由 docstring 派生的摘要。"""\n', encoding="utf-8"
    )
    tool.register("probe_tool.py", dry_run=True)
    out = capsys.readouterr().out
    assert 'description: ""' not in out, "register 仍在写空描述"
    assert "Probe tool" in out


def test_json_quoting_keeps_descriptions_yaml_safe(tmp_path: Path) -> None:
    """带引号/冒号的描述也必须能被 YAML 解析回原文。"""
    tool = _tool()
    weird = '含 "双引号" 与 : 冒号 的一句话'
    got = tool.derive_description(_write(tmp_path, weird))
    parsed = yaml.safe_load(f"description: {json.dumps(got, ensure_ascii=False)}\n")
    assert parsed["description"] == got
