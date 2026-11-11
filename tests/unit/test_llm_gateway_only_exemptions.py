"""LLM 网关判据：docstring 里的端点不是违规；豁免只对非运行时默认值生效。

缺陷（2026-11-11 自证，`check-llm-gateway-only.py` 判据自述与实现不符）：

判据注释写「只匹配调用表达式, 不匹配注释/日志/配置默认值」与
「文档说明里提到旧端口/旧路由是正常的」, 但旧实现只跳过**行首 `#`** ——
docstring（模块/类/函数）里的同一句话照样命中。实证
`projects/knowledge/kairon-security/packages/minerva/src/minerva/llm/client.py:13-14`
（模块 docstring 列出支持的提供商 `localhost:11434/v1` / `localhost:1234/v1`）。

判据：AST 取 docstring 行号后豁免。

**边界（既有用例 `test_check_llm_gateway_only.py::
test_env_default_pointing_at_raw_runtime_is_flagged` 钉住，勿"顺手修"）**：
豁免**只对 direct 侧**生效 —— 默认值指向**裸运行时推理端点**
（`localhost:11434/api/generate` 等）时必须仍报，因为那正是"默认绕过网关"。
故 strict 分支必须先于豁免判定，本文件只用例钉住这个边界不被改坏。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-llm-gateway-only.py"


def _load():
    spec = importlib.util.spec_from_file_location("llm_gateway_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _scan(monkeypatch, tmp_path: Path, files: dict) -> list[dict]:
    """在临时树里跑一次 scan(); ROOT 指向该树。"""
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    return MODULE.scan()


def test_docstring_mention_is_not_a_violation(monkeypatch, tmp_path) -> None:
    """docstring 里列出支持的端点只是文档, 不是直连调用。"""
    files = {
        "projects/app/src/mod.py": (
            '"""Client.\n\n'
            "Works with: Ollama (localhost:11434/v1), DeepSeek (api.deepseek.com/v1),\n"
            'LM Studio (localhost:1234/v1), and any OpenAI-compatible provider.\n"""\n'
        )
    }
    assert _scan(monkeypatch, tmp_path, files) == [], "docstring 里的端点被当成违规"


def test_function_docstring_mention_is_not_a_violation(monkeypatch, tmp_path) -> None:
    """函数 docstring 同理（不只是模块 docstring）。"""
    files = {
        "projects/app/src/mod.py": ('def call():\n    """Uses http://localhost:11434/v1 by default."""\n    return 1\n')
    }
    assert _scan(monkeypatch, tmp_path, files) == [], "函数 docstring 被当成违规"


def test_line_comment_is_not_a_violation(monkeypatch, tmp_path) -> None:
    """行首注释里的旧端口是文档说明。"""
    files = {"projects/app/src/mod.py": "# legacy: http://localhost:11434/v1\n"}
    assert _scan(monkeypatch, tmp_path, files) == [], "行注释被当成违规"


def test_env_default_pointing_at_dead_ip_is_exempt(monkeypatch, tmp_path) -> None:
    """豁免的正当面: 非运行时的可配置默认值(死 IP)不算违规。"""
    files = {"projects/app/src/mod.py": 'URL = os.environ.get("X", "http://100.96.126.35:4000")\n'}
    assert _scan(monkeypatch, tmp_path, files) == [], "死 IP 默认值未被豁免"


def test_env_default_pointing_at_raw_runtime_is_still_flagged(monkeypatch, tmp_path) -> None:
    """边界保护: 默认值指向裸运行时端点 = 默认绕过网关, 必须仍报（strict 先于豁免）。"""
    files = {"projects/app/src/mod.py": 'URL = os.environ.get("X", "http://localhost:11434/api/generate")\n'}
    findings = _scan(monkeypatch, tmp_path, files)
    assert len(findings) == 1, f"裸运行时默认值未被标记: {findings}"


def test_real_ollama_run_is_still_flagged(monkeypatch, tmp_path) -> None:
    """反例保护: 真的 `ollama run` 子进程必须命中。"""
    files = {"projects/app/src/mod.py": 'cmd = ["ollama", "run", self.model, full_prompt]\n'}
    findings = _scan(monkeypatch, tmp_path, files)
    assert len(findings) == 1, f"真实 ollama run 未被识别: {findings}"


def test_hardcoded_base_url_is_still_flagged(monkeypatch, tmp_path) -> None:
    """反例保护: 裸的 base_url 默认值（非 env / 非 .get）必须命中。"""
    files = {"projects/app/src/mod.py": 'base_url: str = "http://localhost:11434/v1"\n'}
    findings = _scan(monkeypatch, tmp_path, files)
    assert len(findings) == 1, f"硬编码 base_url 未被识别: {findings}"
