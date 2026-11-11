"""工具盘点里 `__init__.py` 是包标记，不是脚本。

缺陷（2026-11-11 自证）：`bin/tool-registry-audit.py::script_role` 只分
archive / doc / shim / implementation 四类，`bin/*/__init__.py` 三份被算成
`implementation` ⇒ `classify_duplication_conflicts` 把它们报成「高置信重名
`__init__`」，`high_conflict_duplicates` 从 3 虚增到 4。

**危害不是数字**：该清单是给人看的「哪些脚本该合并」信号，`__init__.py` 在列
会诱导一次毫无意义的合并（把包标记并成一份，直接破坏 import）。

判据：`script_role` 对 `__init__.py` 返回 `package`；`classify_duplication_conflicts`
只统计 `implementation` 角色，故包标记自然出列。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "tool-registry-audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("tool_audit_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def test_package_marker_role() -> None:
    """script_role 要求路径在 ROOT 下（_is_archive_path 会 relative_to(ROOT)）。"""
    assert MODULE.script_role(ROOT / "bin" / "gac" / "__init__.py") == "package"
    assert MODULE.script_role(ROOT / "bin" / "ops" / "__init__.py") == "package"


def test_regular_python_script_is_implementation(monkeypatch, tmp_path) -> None:
    """反例保护: 普通脚本仍必须算 implementation。"""
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    f = tmp_path / "tool.py"
    f.write_text("print('x')\n", encoding="utf-8")
    assert MODULE.script_role(f) == "implementation"


def test_package_files_are_not_duplicate_conflicts(monkeypatch, tmp_path) -> None:
    """包标记同名不得进「高置信重名」清单（roles 由 script_role 派生, 不手造）。"""
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    files = []
    for rel in ("bin/gac/__init__.py", "bin/ops/__init__.py"):
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("", encoding="utf-8")
        files.append(str(f))
    roles = {p: MODULE.script_role(Path(p)) for p in files}
    _, _, high = MODULE.classify_duplication_conflicts({"__init__": files}, roles, {})
    assert high == [], f"包标记被当成重名脚本: {high}"


def test_real_duplicate_scripts_are_still_reported() -> None:
    """反例保护: 同名真脚本仍必须进清单。"""
    dup = {"zhixing_host_sync": ["bin/gac/zhixing-host-sync.py", "bin/gac/zhixing_host_sync.py"]}
    roles = {p: "implementation" for p in dup["zhixing_host_sync"]}
    _, _, high = MODULE.classify_duplication_conflicts(dup, roles, {})
    assert len(high) == 1, f"真重名未被报出: {high}"
    assert high[0]["name"] == "zhixing_host_sync"
