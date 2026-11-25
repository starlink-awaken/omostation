"""`doc-link-check` 在断链目标全属「输入没备齐」时必须自报未判定。

形状与 `bin/gac/gac-healthcheck.py::input_absent` 一致：未检出的子模块 /
gitignore 覆盖的生成态 / 已归档旧路径。旧实现把这些一律计成 FAIL ——
干净检出上实测 15 条断链全部指向未检出子模块，而读数与「文档真有 15 处错」同形。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "bin" / "ssot" / "doc-link-check.py"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("doc_link_check_nm", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _scan(mod, tmp_path: Path, body: str) -> dict:
    # resolve(): macOS 上 /var/folders 是符号链接, 不 resolve 会让 relative_to 判错
    mod.WORKSPACE = tmp_path.resolve()
    (tmp_path / "README.md").write_text(body, encoding="utf-8")
    return mod.run()


def test_all_targets_absent_is_not_measured(mod, tmp_path):
    result = _scan(mod, tmp_path, "[x](projects/ecos/src/ecos/ssot/m3.yaml)\n")
    assert result["ok"] is False
    assert result["measured"] is False
    assert result["reason"] == "targets_absent"
    assert result["broken_links"] == 1


def test_no_broken_links_is_measured(mod, tmp_path):
    """没有断链 ⇒ 真的扫过且没问题，必须算测过。"""
    result = _scan(mod, tmp_path, "# 没有问题\n")
    assert result["ok"] is True
    assert result["measured"] is True
    assert result["reason"] is None


def test_one_real_target_is_measured(mod, tmp_path):
    """反证：只要混进一个不属于输入缺席的目标，就必须仍算可测（不得整体折成未判定）。"""
    result = _scan(
        mod,
        tmp_path,
        "[a](projects/ecos/src/ecos/ssot/m3.yaml)\n[b](definitely-missing-xyz.md)\n",
    )
    assert result["broken_links"] == 2
    assert result["measured"] is True
    assert result["reason"] is None
