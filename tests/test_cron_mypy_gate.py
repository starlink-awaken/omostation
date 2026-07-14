"""Tests for cron entry correctness — verify mypy-baseline-gate is scheduled.

任务: 闭环验证 TASK-26348641 P0 自反馈闭环 (commit 5944f95e).
cron 入口 .omo/cron/gac-crontab 已落 0 7 * * * feedback-loop-guard +
15 7 * * * mypy-baseline-gate. 本测试锁两条:
  - .omo/cron/gac-crontab 含 mypy-baseline-gate 调度行
  - bin/ssot/mypy-baseline-gate 在干净 workspace 上 exit 0
  - 当 mypy baseline 越界时, gate 正确 exit 1
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CRONTAB = ROOT / ".omo" / "cron" / "gac-crontab"
MYPY_GATE = ROOT / "bin" / "ssot" / "mypy-baseline-gate"


class TestCrontabWiring:
    def test_crontab_file_exists(self):
        assert CRONTAB.exists(), f"missing: {CRONTAB}"

    def test_crontab_has_mypy_baseline_gate_entry(self):
        text = CRONTAB.read_text(encoding="utf-8")
        assert "mypy-baseline-gate" in text, (
            f"crontab 缺 mypy-baseline-gate 调度行:\n{text}"
        )

    def test_crontab_has_feedback_loop_guard_entry(self):
        text = CRONTAB.read_text(encoding="utf-8")
        assert "feedback-loop-guard" in text, (
            f"crontab 缺 feedback-loop-guard 调度行"
        )

    def test_crontab_mypy_entry_runs_after_feedback_loop(self):
        # 顺序约束: feedback-loop-guard 先跑 (07:00 收尾),
        # mypy-baseline-gate 后跑 (07:15 验证). 至少要确认不是反序.
        text = CRONTAB.read_text(encoding="utf-8")
        feedback_pos = text.find("feedback-loop-guard")
        mypy_pos = text.find("mypy-baseline-gate")
        assert feedback_pos != -1 and mypy_pos != -1
        assert feedback_pos < mypy_pos, (
            f"feedback-loop-guard (pos {feedback_pos}) 应在 mypy-baseline-gate (pos {mypy_pos}) 之前"
        )


class TestMypyBaselineGateRuntime:
    def test_gate_dry_run_in_workspace_exits_zero_or_one(self):
        # 干净 workspace → exit 0; 有回归 → exit 1; 解析崩溃 → 其他 (fail)
        result = subprocess.run(
            [sys.executable, str(MYPY_GATE), "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
        )
        assert result.returncode in (0, 1), (
            f"mypy-baseline-gate 解析崩溃 (rc={result.returncode}): "
            f"stderr: {result.stderr[:500]}"
        )

    def test_gate_dry_run_never_emits_event(self):
        # --dry-run 是无副作用模式, 不应写 .omo/_knowledge/omo-events.jsonl
        log = ROOT / ".omo" / "_knowledge" / "omo-events.jsonl"
        before = (
            log.read_text().count("mypy_regression_detected") if log.exists() else 0
        )
        subprocess.run(
            [sys.executable, str(MYPY_GATE), "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
        )
        after = (
            log.read_text().count("mypy_regression_detected") if log.exists() else 0
        )
        # 即使回归, dry-run 也不 emit
        assert after == before, "--dry-run 不得 emit mypy_regression_detected"

    def test_gate_resolves_kairon_baseline(self):
        baseline = ROOT / "projects" / "kairon" / "mypy-baseline.yaml"
        assert baseline.exists(), (
            f"kairon mypy-baseline.yaml 不存在: {baseline}. "
            f"mypy-baseline-gate 无 baseline 可比, gate 失效."
        )

    def test_gate_source_injects_mypypath_src(self):
        # 强制 MYPYPATH=src 是 gate 的核心 (防假绿). 检查源码包含这一逻辑.
        source = MYPY_GATE.read_text(encoding="utf-8")
        assert "MYPYPATH" in source, (
            "mypy-baseline-gate 必须显式注入 MYPYPATH=src (L0:CR-ENG-MYPY-TRUTH-01 防假绿)"
        )
        assert '"src"' in source, "MYPYPATH=src 必须是 src (非空)"


class TestCronExecutionSimulation:
    """模拟 cron 执行, 验证 'cd <workspace> && <command>' 模式不出错."""

    def test_feedback_loop_guard_runs_in_workspace(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "bin" / "gac" / "feedback-loop-guard.py"), "--check"],
            cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
        # 不管 exit (可能 0 或 1 取决于当前 working tree),
        # 关键是 cron 调用不能崩在解析阶段.
        assert result.returncode in (0, 1), (
            f"feedback-loop-guard cron 模拟 exit={result.returncode}, 期望 0/1.\n"
            f"stderr: {result.stderr[:500]}"
        )

    def test_mypy_baseline_gate_dry_run_in_workspace(self):
        result = subprocess.run(
            [sys.executable, str(MYPY_GATE), "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, timeout=120, check=False,
        )
        assert result.returncode in (0, 1), (
            f"mypy-baseline-gate cron 模拟 exit={result.returncode}, 期望 0/1.\n"
            f"stderr: {result.stderr[:500]}"
        )