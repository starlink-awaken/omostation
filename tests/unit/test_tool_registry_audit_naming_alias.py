"""连字符↔下划线命名别名不得被算成「重名实现」。

缺陷（2026-11-11 自证）：`tool-registry-audit.py` 的 `_is_shim` 只认
"Compatibility wrapper" / "CLI alias" 两种自述措辞，漏掉仓内实际在用的
"CLI wrapper"（bin/ops/bionic-memory-consolidation.py）、
"CLI entry for"（bin/panorama/sunset-redirector.py）、
"下划线命名版别名"（bin/gac/zhixing_host_sync.py）。

后果：3 对**刻意**的命名别名（BET spec 要求连字符名 / CLI 入口 / 调用方按模块名加载）
全被算成 `implementation`，`classify_duplication_conflicts` 报出 3 条「高置信重名」
—— 那是纯噪音，且会诱导把别名与实现合并（合并即丢一个被 spec 或调用方点名的文件名）。

判据：**结构**而非措辞 —— 文件正文里出现加载自己异名兄弟的动作
（`from <swapped> import` / `with_name("<swapped>.py")`）。实现文件不会加载自己的异名。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "tool-registry-audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("tool_audit_alias_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _write(monkeypatch, tmp_path: Path, rel: str, body: str) -> Path:
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    target = tmp_path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return target


def test_hyphenated_wrapper_loading_underscore_sibling_is_shim(monkeypatch, tmp_path) -> None:
    f = _write(
        monkeypatch,
        tmp_path,
        "bin/ops/alpha-tool.py",
        '"""CLI wrapper."""\nfrom bin.ops.alpha_tool import main\n\nsys.exit(main())\n',
    )
    assert MODULE.script_role(f) == "shim"


def test_underscore_implementation_is_not_shim(monkeypatch, tmp_path) -> None:
    """反例保护: 实现文件（不加载自己的异名）仍算 implementation。"""
    f = _write(monkeypatch, tmp_path, "bin/ops/alpha_tool.py", '"""实现。"""\n\ndef main():\n    return 0\n')
    assert MODULE.script_role(f) == "implementation"


def test_with_name_sibling_load_is_shim(monkeypatch, tmp_path) -> None:
    f = _write(
        monkeypatch,
        tmp_path,
        "bin/gac/beta_host_sync.py",
        '"""下划线命名版别名。"""\n'
        '_PATH = Path(__file__).with_name("beta-host-sync.py")\n'
        '_spec = importlib.util.spec_from_file_location("_x", _PATH)\n',
    )
    assert MODULE.script_role(f) == "shim"


def test_plain_script_without_variant_is_implementation(monkeypatch, tmp_path) -> None:
    """反例保护: 没有异名形态的脚本不受影响。"""
    f = _write(monkeypatch, tmp_path, "bin/gac/gamma.py", "print('x')\n")
    assert MODULE.script_role(f) == "implementation"


def test_naming_alias_pair_is_not_a_duplicate_conflict(monkeypatch, tmp_path) -> None:
    """别名 + 实现不得进「高置信重名」清单（roles 由 script_role 派生）。"""
    wrapper = _write(monkeypatch, tmp_path, "bin/ops/alpha-tool.py", "from bin.ops.alpha_tool import main\n")
    impl = _write(monkeypatch, tmp_path, "bin/ops/alpha_tool.py", "def main():\n    return 0\n")
    files = [str(wrapper), str(impl)]
    roles = {p: MODULE.script_role(Path(p)) for p in files}
    _, _, high = MODULE.classify_duplication_conflicts({"alpha_tool": files}, roles, {})
    assert high == [], f"命名别名被当成重名实现: {high}"
