"""根常量深度门禁：`bin/**` 里「根常量少算一级」的站点必须为空。

契约: `bin/gac/path-dependency-scan.py`（判据即该文件的 docstring）
用例来源: 2026-11-13 的 #5322 / #5323 —— 14 个 `bin/<subdir>/` 脚本把
`Path(__file__).resolve().parents[1]` 当 workspace 根（实为 `<root>/bin`），
于是 `REPO / ".omo" / ...` 落到 `<root>/bin/.omo/` 影子状态面。

三层判据，缺一层就会留下「门禁绿着但根仍算错」的缝（沿用 test_writeplane_root_pin 的口径）：
- **自证**：注入违规样本，检测器必须点名 —— 否则「绿」可能只是检测器没命中。
- **反过宽**：`bin/gac/x.py` 里 `parents[1] / "lib"`、`bin/ssot/x.py` 里
  `parents[1] / "ssot"` 是**正确的**（`bin/lib` / `bin/ssot`），不得命中；
  否则把合法写法一起报，判据就会像它的前身那样恒红到无人接线。
- **真实树为空**：主检出上读数必须是 0，且扫描目标就是「装着本用例的这棵检出」
  （根不对就当场红，不空绿）。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BIN_DIR = ROOT / "bin"
SCANNER = BIN_DIR / "gac" / "path-dependency-scan.py"


def _load_scanner():
    spec = importlib.util.spec_from_file_location("path_dependency_scan", SCANNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_scan_target_is_the_checkout_holding_this_test() -> None:
    """根不对就当场红，不空绿。"""
    assert BIN_DIR.is_dir(), f"扫描目标不存在: {BIN_DIR}"
    assert SCANNER.is_file(), f"检测器不存在: {SCANNER}"


def test_real_tree_has_no_root_depth_errors() -> None:
    scanner = _load_scanner()
    hits = scanner.scan(BIN_DIR)
    assert hits == [], (
        f"检出里出现根常量深度错误 {len(hits)} 处:\n"
        + "\n".join(
            f"  {h['file']}:{h['line']} {h['constant']}=parents[{h['found_k']}] "
            f"(应为 parents[{h['required_k']}]) → / {h['joined']}"
            for h in hits[:20]
        )
    )


def test_detector_names_injected_violations(tmp_path: Path) -> None:
    """自证：两种根写法（下标 / 链式 .parent）都要被点名。"""
    scanner = _load_scanner()
    root = tmp_path / "bin"
    _write(
        root,
        "gac/bad_subscript.py",
        "from pathlib import Path\n"
        "REPO = Path(__file__).resolve().parents[1]\n"
        'STATE = REPO / ".omo" / "state" / "x.json"\n',
    )
    _write(
        root,
        "gac/bad_chain.py",
        "from pathlib import Path\n"
        "REPO = Path(__file__).resolve().parent.parent\n"
        'OUT = REPO / "docs" / "x.md"\n',
    )
    hits = scanner.scan(root)
    files = {h["file"] for h in hits}
    assert any("bad_subscript.py" in f for f in files), hits
    assert any("bad_chain.py" in f for f in files), hits
    assert all(h["required_k"] == 2 for h in hits), hits


def test_legitimate_bin_relative_roots_are_not_flagged(tmp_path: Path) -> None:
    """反过宽：`parents[1] / "lib"` / `"ssot"` 是 bin 相对路径，合法。"""
    scanner = _load_scanner()
    root = tmp_path / "bin"
    _write(
        root,
        "gac/good_lib.py",
        "from pathlib import Path\n"
        "BIN = Path(__file__).resolve().parents[1]\n"
        'LIB = BIN / "lib"\n',
    )
    _write(
        root,
        "ssot/good_ssot.py",
        "from pathlib import Path\n"
        "BIN = Path(__file__).resolve().parents[1]\n"
        'SSOT = BIN / "ssot"\n',
    )
    # 模块级同名变量不得让判据误报（循环/函数内的 `p` 等）
    _write(
        root,
        "gac/good_shadow.py",
        "from pathlib import Path\n"
        "REPO = Path(__file__).resolve().parents[2]\n"
        "for p in range(3):\n"
        '    _ = REPO / ".omo"\n'
        '    _ = p / "projects"\n',
    )
    assert scanner.scan(root) == [], scanner.scan(root)


def test_nested_depth_is_required_exactly(tmp_path: Path) -> None:
    """三层深的文件要求 parents[3]，少一级也算错。"""
    scanner = _load_scanner()
    root = tmp_path / "bin"
    _write(
        root,
        "gac/sub/deep.py",
        "from pathlib import Path\n"
        "REPO = Path(__file__).resolve().parents[2]\n"
        'X = REPO / "runtime" / "x"\n',
    )
    hits = scanner.scan(root)
    assert len(hits) == 1, hits
    assert hits[0]["required_k"] == 3 and hits[0]["found_k"] == 2, hits


@pytest.mark.parametrize(
    "src,expected_k",
    [
        ("Path(__file__).resolve().parents[1]", 1),
        ("Path(__file__).resolve().parents[2]", 2),
        ("Path(__file__).resolve().parent", 0),
        ("Path(__file__).resolve().parent.parent", 1),
        ("Path(__file__).resolve().parent.parent.parent", 2),
        ("Path(__file__).parent.parent", 1),
    ],
)
def test_resolve_root_k(src: str, expected_k: int) -> None:
    import ast

    scanner = _load_scanner()
    assert scanner.resolve_root_k(ast.parse(src, mode="eval").body) == expected_k


@pytest.mark.parametrize(
    "src",
    ["Path.cwd()", "SOME_CONST", "Path(__file__).resolve().parents[len(parts)]", "REPO"],
)
def test_resolve_root_k_rejects_non_literal(src: str) -> None:
    import ast

    scanner = _load_scanner()
    assert scanner.resolve_root_k(ast.parse(src, mode="eval").body) is None
