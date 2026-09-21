"""`governance-semantic-gate` 不得整体降级为 SOFT。

背景：该聚合器曾被列入 `gac-local-gate.SOFT_CHECKS`（理由写作
"evolution/release_ready 是软信号"）。但脚本自身已按 blocking 标志分类：

    blocking=True          : gac-mof-validate / adr-coverage / service-config-drift
    blocking=release-only  : agent-workflow-status / governance-evolution-packages
                             (非 --release 时 blocking=False, 本就非阻断)

整体降级使上述 blocking 子检查的失败**无法翻转 gate**，与 sgf-policy.yaml
对其 "阻断性" 的声明自相矛盾。实证后果：ADR 一致性缺陷（重复编号 / INDEX
失配）零成本进入 main，靠人工发现后才由 #4113 修复。

契约：`governance-semantic-gate` 的退出码必须参与 hard_fails 判定。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
GATE = WORKSPACE / "bin" / "gac" / "gac-local-gate.py"
SEMANTIC = WORKSPACE / "bin" / "gac" / "governance-semantic-gate.py"

NAME = "governance-semantic-gate"


def _load_gate():
    spec = importlib.util.spec_from_file_location("gac_local_gate_probe", GATE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {GATE}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_semantic_gate_is_not_soft() -> None:
    assert NAME not in _load_gate().SOFT_CHECKS, (
        f"{NAME} 必须参与 hard_fails 判定；整体降级会使其内部 blocking 子检查永不翻转 gate"
    )


def test_semantic_gate_failure_lands_in_hard_fails() -> None:
    """分类逻辑：该检查 ok=False 时应计入 hard_fails（而非 soft_warns）。"""
    gate = _load_gate()
    results = [{"name": NAME, "ok": False}]
    hard = [r for r in results if not r["ok"] and r["name"] not in gate.SOFT_CHECKS]
    soft = [r for r in results if not r["ok"] and r["name"] in gate.SOFT_CHECKS]
    assert len(hard) == 1, "失败须计入 hard_fails"
    assert soft == [], "不得落在 soft_warns"
    assert (len(hard) == 0) is False, "gate ok 应因此为 False"


def test_semantic_gate_exposes_blocking_checks_and_uses_exit_code() -> None:
    """契约有意义的前提：内部确有 blocking 检查，且退出码反映 blocking_failures。"""
    proc = subprocess.run(
        [sys.executable, str(SEMANTIC), "--json"],
        capture_output=True,
        text=True,
        check=False,
        cwd=WORKSPACE,
    )
    report = json.loads(proc.stdout)
    blocking = [c for c in report["checks"] if c.get("blocking")]
    assert blocking, "聚合器应至少暴露一个 blocking 检查"
    expected_exit = 0 if not report.get("blocking_failures") else 1
    assert proc.returncode == expected_exit, (
        f"退出码须反映 blocking_failures；got {proc.returncode}, expected {expected_exit}"
    )
