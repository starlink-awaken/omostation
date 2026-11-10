"""门禁汇总只能报**实际被跳过**的 broken 检查。

缺陷（2026-11-11 自证）：`gac-local-gate.py` 的汇总行无条件打印
`len(BROKEN_CHECKS)` 条「broken/known-unavailable checks skipped (use --strict
to include)」—— 但 `--strict` 的语义恰恰是**不跳过**它们。实测
`--strict --verbose` 下这 6 项全部执行且 PASS（agent-workflow-lint /
integrations / adapters / bootstrap / observe / gac-compute-onboard-check，
总执行数 69 → 87），提示却在说它们被跳过，还附一句已经无效的
「use --strict to include」。

判据：拿实际执行的 check 名与 BROKEN_CHECKS 做差集，只报差集，并把名字列出来。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "gac-local-gate.py"


def _load():
    spec = importlib.util.spec_from_file_location("gac_local_gate_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def test_only_actually_skipped_are_reported(monkeypatch, capsys) -> None:
    """跑过的不说跳过 —— 只报真正缺席的那些，并点名。"""
    monkeypatch.setattr(MODULE, "BROKEN_CHECKS", {"ran-one", "skipped-two", "skipped-three"})
    MODULE._print_broken_skips([{"name": "ran-one"}])
    out = capsys.readouterr().out
    assert "2 broken/known-unavailable checks skipped" in out, out
    assert "skipped-two" in out and "skipped-three" in out, out
    assert "ran-one" not in out, f"跑过的检查被说成跳过: {out}"


def test_silent_when_nothing_was_skipped(monkeypatch, capsys) -> None:
    """strict 下全部执行 ⇒ 一个字都不该说。"""
    monkeypatch.setattr(MODULE, "BROKEN_CHECKS", {"a", "b"})
    MODULE._print_broken_skips([{"name": "a"}, {"name": "b"}])
    assert capsys.readouterr().out == ""


def test_print_human_does_not_claim_skip_in_strict(monkeypatch, capsys) -> None:
    """端到端: 全部执行时，汇总输出里不得出现 skipped 字样。"""
    monkeypatch.setattr(MODULE, "BROKEN_CHECKS", {"a", "b"})
    report = {
        "ok": True,
        "scope": "staged",
        "run_id": None,
        "change_lane_files": [],
        "finding_topics": [],
        "soft_warns": [],
        "hard_fails": [],
        "checks": [
            {"name": "a", "command": "x", "ok": True},
            {"name": "b", "command": "y", "ok": True},
        ],
    }
    MODULE.print_human(report)
    out = capsys.readouterr().out
    assert "skipped" not in out, f"strict 下谎报跳过: {out}"
