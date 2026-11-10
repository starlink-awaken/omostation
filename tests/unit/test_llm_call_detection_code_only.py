"""「有没有 LLM 调用」是代码属性 —— 注释与 docstring 里的 import 不是调用。

缺陷（2026-11-11 自证）：`check-heuristic-default.py` 与 `check-llm-tier-fallback.py`
的 `has_llm` 判据对**文件全文**跑 `import openai` / `from openai import …` 正则，
而两处代码注释都自称「精确检测 LLM API 调用 (排除正则/注释/子模块列表误匹配)」——
声明与实现不符。实测反例：

- 注释里写 `# import openai  (历史依赖, 已移除)` ⇒ 被判成「使用 LLM」
- docstring 里写 from openai import Client 的封装 ⇒ 同上

没有 fallback 词时即误报；有 `fallback` 字样时则漏报。

判据：用 AST 抹掉 docstring / 字符串常量 / 注释后再匹配。真调用是标识符与调用
表达式，不受影响；`has_fallback` 仍需扫全文（argparse 选项 `--no-llm` 是字面量）。

本文件的用例一律端到端跑 `main()`（`REPO_ROOT` 指向临时树），不直接调内部
helper —— 否则「判据有没有被接上」不承重，改坏 `has_llm` 也不会红。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = (
    ROOT / "bin" / "gac" / "check-heuristic-default.py",
    ROOT / "bin" / "gac" / "check-llm-tier-fallback.py",
)


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(f"llm_det_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULES = {p.name: _load(p) for p in SCRIPTS}
NAMES = sorted(MODULES)


def _run_check(module, monkeypatch, tmp_path: Path, files: dict) -> int:
    """在临时树里跑一次检查; REPO_ROOT 指向该树。"""
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(module, "REPO_ROOT", tmp_path)
    return module.main()


@pytest.mark.parametrize("name", NAMES)
def test_comment_and_docstring_imports_are_not_llm_usage(name, monkeypatch, tmp_path) -> None:
    """注释 / docstring / .sh 注释里的 import 不算 LLM 调用。"""
    module = MODULES[name]
    cases = [
        {"bin/x.py": "# import openai  (历史依赖, 已移除)\nprint('hello')\n"},
        {"bin/x.py": '"""from openai import Client 的封装。"""\nprint("hello")\n'},
        {"bin/x.py": "# from anthropic import Client\nprint('hello')\n"},
        {"bin/x.sh": "# import openai\necho hello\n"},
    ]
    for i, files in enumerate(cases):
        case_dir = tmp_path / f"case{i}"
        case_dir.mkdir()
        assert _run_check(module, monkeypatch, case_dir, files) == 0, f"{name}: {files}"


@pytest.mark.parametrize("name", NAMES)
def test_real_call_is_still_detected(name, monkeypatch, tmp_path) -> None:
    """反例保护: 代码里的真实 import + 调用必须仍然命中。"""
    module = MODULES[name]
    files = {"bin/x.py": "import openai\n\ndef f():\n    openai.chat.completions.create()\n"}
    assert _run_check(module, monkeypatch, tmp_path, files) == 1, f"{name}: 真实调用未被识别"


@pytest.mark.parametrize("name", NAMES)
def test_fallback_detection_still_reads_full_text(name, monkeypatch, tmp_path) -> None:
    """has_fallback 必须扫全文: 注释里的 `--no-llm` / aetherforge 也是 fallback 证据。

    这条守的是另一半 —— 修 `has_llm` 时若顺手把 fallback 判据也改成只扫代码，
    argparse 选项 `--no-llm` 会被漏掉。
    """
    module = MODULES[name]
    files = {
        "bin/x.py": (
            "import openai\n\n"
            "def f():\n"
            "    openai.chat.completions.create()\n\n"
            "# 支持 --no-llm 与 aetherforge 网关回退\n"
        )
    }
    assert _run_check(module, monkeypatch, tmp_path, files) == 0, f"{name}: 全文 fallback 判据失效"
