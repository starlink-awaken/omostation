"""债务标记必须按词边界匹配 —— `whack-a-mole` 里的 hack 不是债务。

缺陷（2026-11-11 自证）：`check-diff-debt.py` 的 `DEBT_PATTERN` 无词边界，
`FIXME|HACK|TODO|XXX` 会命中任何子串。实测本仓 `.omo/_truth/registry/document-governance.yaml:35`
的 `whack-a-mole` 被报成新增 HACK 债务；全仓口径下无词边界会产出 **3626** 条
垃圾命中（含 `.omo/_archive/**.tar.gz` 二进制内容），加词边界后只剩 **382** 条真标记。

判据：`\b(FIXME|HACK|TODO|XXX)\b`。标识符后缀（`_xxx`）、二进制字节、
普通英文单词（whack / hacking）都不再命中；`# TODO:` / `TODO(name):` 等
常规写法仍有词边界，照常命中。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-diff-debt.py"


def _pattern():
    spec = importlib.util.spec_from_file_location("diff_debt_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DEBT_PATTERN


def test_substrings_are_not_markers() -> None:
    """子串命中是假阳：whack-a-mole / 标识符后缀 / 普通单词。"""
    pattern = _pattern()
    for line in (
        "# 把它声明成枚举会变成 whack-a-mole: 要么只列一部分",
        "func_name: run_governance_audit_xxx",
        "# HACKING 是一种文化, 不是债务标记",
        "prefixTODOsuffix",
    ):
        assert pattern.search(line) is None, f"子串被误判为债务标记: {line}"


def test_standard_markers_still_match() -> None:
    """反例保护: 常规债务标记写法必须仍然命中。"""
    pattern = _pattern()
    for line in (
        "# FIXME: 这里需要重做",
        "# TODO(xiamingxing): 补测试",
        "// HACK 临时绕过",
        "# XXX 不安全",
        "TODO:",
    ):
        assert pattern.search(line) is not None, f"真标记未命中: {line}"
