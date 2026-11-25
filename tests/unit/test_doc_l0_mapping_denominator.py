"""`check-doc-l0-mapping` 的文档分母不得为空 (零分母不得判绿)。

规则 1/2 的总体是 `DOC_GLOBS` 扫出的文档; 扫描面落空时 `bad_dim`/`bad_surface`
必然为空 ⇒ `ok = not errors` 会静默判绿 —— 与 `check-test-collection` 那族
「零分母」同形。判据要求: 扫到 0 个文档时**判红**并把分母打进 OK 行。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "ssot" / "check-doc-l0-mapping.py"

# 分母来自 L0 约束源 (projects/ecos); 干净检出上它缺席会让本检查直接报错,
# 与用例要钉的「零分母判红」是两回事 -> 整个模块跳过。
_L0_CONSTRAINTS_SRC = (
    ROOT / "projects" / "ecos" / "src" / "ecos" / "ssot" / "registry" / "L0-constraints.yaml"
)
if not _L0_CONSTRAINTS_SRC.exists():
    pytest.skip(
        f"L0 约束源缺席: {_L0_CONSTRAINTS_SRC} —— "
        "先 `git submodule update --init projects/ecos`（检出形态, 不是回归）",
        allow_module_level=True,
    )


def _load():
    spec = importlib.util.spec_from_file_location("doc_l0_mapping_denominator", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["doc_l0_mapping_denominator"] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _run(module, argv: list[str]) -> tuple[int, str]:
    argv_backup = sys.argv
    sys.argv = ["check-doc-l0-mapping.py", *argv]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = module.main()
    finally:
        sys.argv = argv_backup
    return rc, buf.getvalue()


def test_ok_line_carries_document_denominator() -> None:
    """OK 行必须带文档数 —— 否则读者无法分辨「扫了 4399 个」与「扫了 0 个」。"""
    rc, out = _run(MODULE, [])
    assert "文档=" in out, out
    assert rc == 0, out


def test_empty_scan_surface_is_an_error_not_a_pass(monkeypatch) -> None:
    """变异钉: DOC_GLOBS 指向空 ⇒ 必须判红并点名, 不能静默放行。"""
    monkeypatch.setattr(MODULE, "DOC_GLOBS", ["__nonexistent_glob__/x.md"])
    rc, out = _run(MODULE, ["--json"])
    assert rc == 1, (rc, out)
    assert "扫到 0 个文档" in out, out
