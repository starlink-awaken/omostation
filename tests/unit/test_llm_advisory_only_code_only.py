"""auto-apply 判据只认「非注释、非 docstring」的文本 —— 注释里的命令不是执行。

缺陷（2026-11-11 自证）：`check-llm-advisory-only.py` 对 .py 文件全文跑
`git commit --no-verify` / `git push --force` 等正则，注释与 docstring 里
提到这些命令即被计成 auto-apply。实测探针（docstring + 两行注释）报 3 处违规，
其中 2 处是纯文字。

判据：匹配前抹掉注释与 docstring，但**保留字符串字面量** —— 本规则的判据本身
要匹配字符串里的命令文本（`subprocess.run(["git","commit"])` / `os.system(...)`），
抹掉字符串会把真违规一并抹没（与 `check-llm-tier-fallback` 的 `_code_only` 刻意不同）。

本文件的用例端到端跑 `main()`（`REPO_ROOT` 指向临时树），不直接调内部 helper。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-llm-advisory-only.py"


def _load():
    spec = importlib.util.spec_from_file_location("llm_advisory_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _run(monkeypatch, tmp_path: Path, files: dict) -> int:
    """在临时树里跑一次检查; REPO_ROOT 指向该树。"""
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(MODULE, "REPO_ROOT", tmp_path)
    return MODULE.main()


def test_comments_and_docstrings_are_not_auto_apply(monkeypatch, tmp_path) -> None:
    """注释 / docstring 里提到危险命令只是文字, 不算 auto-apply。"""
    cases = [
        {"bin/x.py": '"""git commit --no-verify 是禁止的。"""\nprint("hi")\n'},
        {"bin/x.py": "# git commit --no-verify\n# git push --force\nprint('hi')\n"},
        {"bin/x.py": 'def f():\n    """git push --force 不要用。"""\n    return 1\n'},
    ]
    for i, files in enumerate(cases):
        case_dir = tmp_path / f"case{i}"
        case_dir.mkdir()
        assert _run(monkeypatch, case_dir, files) == 0, f"注释/docstring 误报: {files}"


def test_real_auto_apply_call_is_detected(monkeypatch, tmp_path) -> None:
    """反例保护: subprocess 里真实的 git commit --no-verify 必须命中。"""
    files = {"bin/x.py": 'import subprocess\n\nsubprocess.run(["git", "commit", "--no-verify"])\n'}
    assert _run(monkeypatch, tmp_path, files) == 1, "真实 auto-apply 调用未被识别"


def test_os_system_command_string_is_detected(monkeypatch, tmp_path) -> None:
    """反例保护: os.system 的命令字符串必须命中（字符串字面量不得被抹掉）。"""
    files = {"bin/x.py": 'import os\n\nos.system("git push --force")\n'}
    assert _run(monkeypatch, tmp_path, files) == 1, "os.system 命令字符串未被识别"
