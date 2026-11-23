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


def test_unwired_entries_are_named_not_just_counted() -> None:
    """未接线的登记项必须**点名**, 不能只给 `wired=N/M`。

    缺陷形状 (2026-11-23): 总结行报 `wired=144/158` 而 `error_count=0`
    ⇒ 「哪 14 条没接」要人自己去差集, 而「CI 平面干净」这句会盖住它。
    点名时每条带上**它自己声明的 workflow** —— 多数正是「声明了 workflow
    但该 workflow 不跑 ci-check-runner」这种声明与执行面不符。
    """
    report = MODULE.check_ci_surfaces()
    unwired = report["unwired_tools"]
    assert report["unwired_count"] == len(unwired), (report["unwired_count"], len(unwired))
    assert all(row["tool"] for row in unwired), unwired
    # 点名的必须**确实**不在接线集里 —— 否则点名本身就是假绿
    wiring = MODULE._discover_wiring()
    for row in unwired:
        assert row["tool"] not in wiring, row
    # 总结行要带上计数, 否则等于没点名
    assert "unwired=" in _summary_line()


def _summary_line() -> str:
    """总结行由 `main()` 打印 (check_ci_surfaces() 只返回 dict), 故按 CLI 路径取。"""
    import contextlib
    import io
    import sys

    argv = sys.argv
    sys.argv = ["check-ci-surfaces.py"]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            MODULE.main()
    finally:
        sys.argv = argv
    for line in buf.getvalue().splitlines():
        if line.startswith("SSOT:"):
            return line
    return ""
