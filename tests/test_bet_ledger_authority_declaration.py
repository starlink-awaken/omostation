"""BET-LEDGER-CLI-AUTHORITY-SPLIT: 只读出口的读数来源面声明.

背景: `bin/plan/bet-ledger.py` 的 `WS`/`LEDGER` 在 import 时由 `__file__` 反推,
只读出口 (status/list/show/claim-check) 按**当前检出树**计数, 而证据可达性按
`origin/main` 判 —— 同一文件两套权威面, 输出却不声明读数来自哪棵树。
实测后果 (2026-11-09): 在滞后主区读到 `in_progress 2`, 差点为已收口的 BET 重开
closeout PR。

本文件钉住 declare-only 处置的三条性质:
1. 声明包含 root / HEAD / ledger blob / origin/main 比对;
2. 比对真的分「一致 / 不一致」两态 (不是恒绿);
3. 声明走 **stderr**, stdout 的机器可读性逐字节不变。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "bin/plan/bet-ledger.py"

_spec = importlib.util.spec_from_file_location("bet_ledger_auth", MODULE_PATH)
assert _spec and _spec.loader
bl = importlib.util.module_from_spec(_spec)
sys.modules["bet_ledger_auth"] = bl
_spec.loader.exec_module(bl)


def test_declaration_names_root_head_ledger_and_origin_main() -> None:
    """声明必须让读者能判断读数来自哪棵树、是否新鲜."""
    text = "\n".join(bl.authority_declaration_lines())
    assert "root:" in text
    assert "HEAD:" in text
    assert "ledger:" in text
    assert "origin/main:" in text
    assert "与 origin/main:" in text


def test_declaration_detects_divergence(monkeypatch: pytest.MonkeyPatch) -> None:
    """blob 不等时必须报「不一致」—— 否则声明等于恒绿."""
    probes = {
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", f"HEAD:{bl.LEDGER_RELATIVE_PATH}"): "b" * 40,
        ("rev-parse", "origin/main"): "c" * 40,
        ("rev-parse", f"origin/main:{bl.LEDGER_RELATIVE_PATH}"): "d" * 40,
    }

    def fake(cwd: Path, *args: str) -> str | None:
        return probes.get(tuple(args))

    monkeypatch.setattr(bl, "_git_probe", fake)
    text = "\n".join(bl.authority_declaration_lines())
    assert "不一致" in text
    assert "滞后树" in text


def test_declaration_reports_agreement(monkeypatch: pytest.MonkeyPatch) -> None:
    """blob 相等时必须报「一致」—— 正反两态都要能出现."""
    same = "e" * 40
    probes = {
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", f"HEAD:{bl.LEDGER_RELATIVE_PATH}"): same,
        ("rev-parse", "origin/main"): "c" * 40,
        ("rev-parse", f"origin/main:{bl.LEDGER_RELATIVE_PATH}"): same,
    }

    def fake(cwd: Path, *args: str) -> str | None:
        return probes.get(tuple(args))

    monkeypatch.setattr(bl, "_git_probe", fake)
    text = "\n".join(bl.authority_declaration_lines())
    assert "与 origin/main: 一致" in text
    assert "不一致" not in text


def test_declaration_survives_missing_blobs(monkeypatch: pytest.MonkeyPatch) -> None:
    """缺 blob 读数时如实说「无法比较」, 不静默报一致."""
    monkeypatch.setattr(bl, "_git_probe", lambda cwd, *args: None)
    text = "\n".join(bl.authority_declaration_lines())
    assert "无法比较" in text
    assert "一致" not in text


def test_status_emits_declaration_on_stderr_not_stdout() -> None:
    """声明走 stderr: stdout 的机器可读性不能被污染 (下游有正则解析 stdout)."""
    r = subprocess.run(
        [sys.executable, str(MODULE_PATH), "status"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(ROOT),
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "权威面" in r.stderr
    assert "权威面" not in r.stdout
    # stdout 仍是原有的总览格式
    assert "总 bet:" in r.stdout
