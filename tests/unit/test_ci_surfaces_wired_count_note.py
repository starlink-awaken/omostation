"""`wired_tools` 计数偏低时必须说明原因（缺生可见）。

缺陷（2026-11-11 自证）：`wired_tools` 来自 `_discover_wiring()` 扫出的
workflow 文本 + sgf-policy。子模块未 init 的检出里 sgf-policy 缺席 ⇒ 计数
**静默偏低**：同一份 `ci-surfaces.yaml`（154 面）在两种检出上读出
`wired=147`（有 sgf-policy）与 `wired=95`（无）。旧实现只打印数字，读者会把
「计数低」读成「这 59 个工具没接线」，而它们其实经 `gac-local-gate.py` 执行。

判据：`--check`/默认输出在 sgf-policy 缺席时显式说明计数偏低。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-ci-surfaces.py"


def _load():
    spec = importlib.util.spec_from_file_location("ci_surfaces_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _run(monkeypatch, capsys, policy_present: bool) -> str:
    monkeypatch.setattr(MODULE, "_sgf_policy_present", lambda: policy_present)
    monkeypatch.setattr(sys, "argv", ["check-ci-surfaces.py"])
    MODULE.main()
    return capsys.readouterr().out


def test_note_printed_when_policy_absent(monkeypatch, capsys) -> None:
    """sgf-policy 缺席时必须说明 wired_tools 偏低，否则计数被误读成「未接线」。"""
    out = _run(monkeypatch, capsys, policy_present=False)
    assert "sgf-policy.yaml 缺席" in out, f"缺席时未提示: {out}"
    assert "计数偏低" in out, out


def test_no_note_when_policy_present(monkeypatch, capsys) -> None:
    """反过来：policy 在位时不得误导性地提示计数偏低。"""
    out = _run(monkeypatch, capsys, policy_present=True)
    assert "sgf-policy.yaml 缺席" not in out, f"policy 在位却提示缺席: {out}"
