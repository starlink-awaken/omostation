"""硬编码密钥扫描器的判据精度 —— 变量名词边界、替换值、文档面。

缺陷（2026-11-11 自证）：`hardcode-scan.py` 的三条正则
`api_key|password|token\s*=\s*['"][^'"]+['"]` 在改动前对仓内产出 **6 条命中、
0 条真密钥**（精度 0%）：

- `split_token = "## 🧬 Onboarding Consensus"` —— `token` 命中 `split_token` 子串
- `PASSWORD="$_PRESET_PASS"` / `token="$(python3 -c "` —— 值是 shell 替换，不是字面密钥
- `.omo/_knowledge/**.md` 里 3 处 `api_key="ollama"` —— 文档引用示例配置

判据：变量名加 `\b` 词边界；值以 `$` 或反引号开头视为替换；不扫 `.md`。
本文件的用例端到端跑 `main()`（`REPO_ROOT` 指向临时树）。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "hardcode-scan.py"


def _load():
    spec = importlib.util.spec_from_file_location("hardcode_scan_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _run(monkeypatch, tmp_path: Path, files: dict) -> int:
    """在临时树里跑一次扫描; REPO_ROOT 指向该树。返回退出码。"""
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(MODULE, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["hardcode-scan.py"])
    with pytest.raises(SystemExit) as exc:
        MODULE.main()
    return exc.value.code


def test_real_hardcoded_secret_is_still_detected(monkeypatch, tmp_path) -> None:
    """反例保护: 真正的字面密钥必须仍然命中。"""
    files = {"bin/x.py": 'api_key = "sk-live-abc123def456"\n'}
    assert _run(monkeypatch, tmp_path, files) == 1, "真实硬编码密钥未被识别"


def test_substring_variable_name_is_not_a_secret(monkeypatch, tmp_path) -> None:
    """`split_token` 里的 token 是子串, 不是密钥变量名。"""
    files = {"bin/gac/y.py": 'split_token = "## 🧬 Onboarding Consensus"\n'}
    assert _run(monkeypatch, tmp_path, files) == 0, "split_token 被误判为 token 密钥"


def test_shell_substitution_is_not_a_hardcoded_secret(monkeypatch, tmp_path) -> None:
    """`$_PRESET_PASS` 是变量引用, 不是硬编码密钥。"""
    files = {"bin/z.sh": 'PASSWORD="$_PRESET_PASS"\n'}
    assert _run(monkeypatch, tmp_path, files) == 0, "shell 变量替换被误判为硬编码密码"


def test_command_substitution_is_not_a_hardcoded_secret(monkeypatch, tmp_path) -> None:
    """`$(...)` 是命令替换, 不是硬编码密钥。"""
    files = {"bin/w.sh": "token=\"$(python3 -c 'print(1)')\"\n"}
    assert _run(monkeypatch, tmp_path, files) == 0, "命令替换被误判为硬编码 token"


def test_markdown_docs_are_not_scanned(monkeypatch, tmp_path) -> None:
    """文档按定义引用示例配置, 不构成硬编码密钥证据。"""
    files = {".omo/_knowledge/notes.md": '示例：把模型名写成 api_key="ollama"\n'}
    assert _run(monkeypatch, tmp_path, files) == 0, "markdown 示例被误判为硬编码密钥"
