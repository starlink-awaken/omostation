"""P36-W2 单元测试 — omo observability / cost / alert 三件套路由验证.

覆盖:
  - omo observability metric: KEI audit 计数 (cli 路由 bug 修复)
  - omo observability log stats: 文件统计子命令
  - omo cost estimate: LLM 成本估算
  - omo alert check: KEI 告警阈值
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[2]


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    """在 omo 根目录跑 uv run omo <args>."""
    env = os.environ.copy()
    return subprocess.run(
        ["uv", "run", "omo", *args],
        cwd=str(OMO_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def test_cli_observability_metric_routes_correctly() -> None:
    """Bug fix: 'omo observability metric' 不再报 'invalid choice: observability'.

    此前 cli.py 把 'observability' 作为子命令名转发给 obs_main,
    而 obs_main 内部 subparser 只认 {log, metric}, 触发 invalid choice.
    修复: cli.py 单独路由 observability, 转发 args[1:] 给 obs_main.
    """
    r = _run(["observability", "metric"])
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "KEI Audit Total:" in r.stdout
    assert "Tool Calls:" in r.stdout
    assert "invalid choice" not in r.stderr


def test_cli_observability_log_stats_routes_correctly() -> None:
    """Bug fix: 'omo observability log stats --type kei' 工作."""
    r = _run(["observability", "log", "stats", "--type", "kei"])
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "File:" in r.stdout
    assert "Records:" in r.stdout
    assert "invalid choice" not in r.stderr


def test_cli_observability_log_search_routes_correctly() -> None:
    """Bug fix: 'omo observability log search' 工作."""
    r = _run(["observability", "log", "search", "--type", "kei", "--limit", "3"])
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "Found" in r.stdout
    assert "invalid choice" not in r.stderr


def test_cli_cost_estimate_runs() -> None:
    """omo cost estimate --period 7 跑通且不报缺依赖."""
    r = _run(["cost", "estimate", "--period", "7"])
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "LLM Cost Report" in r.stdout
    assert "Total cost:" in r.stdout


def test_cli_alert_check_runs() -> None:
    """omo alert check 跑通(0 阻断/0 失败时返回 0)."""
    r = _run(["alert", "check"])
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "All KEI metrics normal" in r.stdout


def test_cli_observability_metric_exit_zero_with_real_data() -> None:
    """健壮性: 即便 KEI audit 文件为空也优雅处理."""
    r = _run(["observability", "metric"])
    assert r.returncode == 0
    # 数字部分必出现 (允许为 0)
    assert "KEI Audit Total:" in r.stdout


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
