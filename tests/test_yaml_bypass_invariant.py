"""Tests for yaml-bypass invariant (no .omo/debt/items/*.yaml 越权 status 字段).

任务: 治本 yaml-bypass 3 项 stale debt 闭环 (omo-debt close/reopen CLI 正路).
锁定不变量:
  - 所有 .omo/debt/items/*.yaml 没有 status 字段 (OMO 用 lifecycle_state)
  - 或者 status 字段值与 lifecycle_state 一致 (过渡态: 重开后未再 close)
  - yaml-bypass lint 返回 0 violations

实现: 跑 omo.omo_lint yaml-bypass 拿退出码和输出, 断言 0 issues.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run_lint() -> tuple[int, str]:
    """跑 yaml-bypass lint, 返回 (rc, stdout)."""
    # 走 omo venv 的真实 lint (不用 PATH shim)
    venv_py = ROOT / "projects" / "omo" / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.exists() else sys.executable
    result = subprocess.run(
        [py, "-m", "omo.omo_lint", "yaml-bypass"],
        cwd=ROOT, capture_output=True, text=True, timeout=60, check=False,
    )
    return result.returncode, (result.stdout + result.stderr)


class TestYamlBypassInvariant:
    """R1/R2 violations 闭环. 任一回归立即挂测试."""

    def test_lint_exits_zero(self):
        rc, out = _run_lint()
        assert rc == 0, (
            f"yaml-bypass lint 仍 fail (rc={rc}):\n{out}\n"
            f"→ 走 omo-debt close <id> --actor X 治本 (lifecycle_state 唯一, 剥离 status)"
        )

    def test_lint_output_says_pass(self):
        rc, out = _run_lint()
        assert "pass" in out.lower(), f"lint 报告无 'pass': {out}"

    def test_no_debt_yaml_has_stray_status_field(self):
        """直接扫描所有 .omo/debt/items/*.yaml, 确认无越权 status 字段.

        例外: yaml 文件可携带 status='closed' 当 lifecycle_state 也='closed'
        (即 '已被 omo close 标 closed' 的合法最终态), R1/R2 不会触发.
        但纯无 lifecycle_state 的 status='closed' (R1) 或 status='resolved' (R2) 必须为零.
        """
        items_dir = ROOT / "projects" / "omo" / ".omo" / "debt" / "items"
        if not items_dir.exists():
            pytest.skip(f"debt items dir not found: {items_dir}")
        offenders: list[tuple[str, str, str]] = []
        for path in sorted(items_dir.glob("*.yaml")):
            text = path.read_text(encoding="utf-8")
            # Lightweight check: detect R1 (status without lifecycle_state) and
            # R2 (status='resolved' regardless of lifecycle).
            has_status_line = any(
                ln.strip().startswith("status:") for ln in text.splitlines()
            )
            has_lifecycle = "lifecycle_state:" in text
            if has_status_line and not has_lifecycle:
                # R1: 越权
                offenders.append((path.name, "R1", "status 无 lifecycle_state"))
            for ln in text.splitlines():
                if "status:" in ln and "resolved" in ln:
                    offenders.append((path.name, "R2", ln.strip()))
        assert offenders == [], (
            f"发现 {len(offenders)} 处越权 status 字段:\n"
            + "\n".join(f"  - {p}: {kind} {msg}" for p, kind, msg in offenders)
        )