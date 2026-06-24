"""omo-debt close/reopen 单元测试 (Round 43 P0).

修复 omo_debt.py:933/947 update_item 漏传 _load_yaml 后, 验证:
  - close --id <id> --actor <actor> 改 yaml 真改 (lifecycle_state=closed + history append close + actor)
  - reopen --id <id> --actor <actor> 改 yaml 真改 (lifecycle_state=identified + history append reopen + actor)
  - close 对不存在的 id 抛 FileNotFoundError (走 update_item 的 file not found 路径)
  - omo lint yaml-bypass 在 omo-debt close 写的 yaml 上报 0 issue (集成一致性)

实现: in-process 调 omo.omo_debt.main(), 注入 sys.argv. 不用 subprocess, 避免
跨 venv 问题 (pytest 可能跑在 kairon venv 里, omo 不在 kairon venv site-packages).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def tmp_omo_dir(tmp_path: Path) -> Path:
    """建临时 .omo/ 目录 + seed 1 个 test debt (Round 43 P0 单元测试)."""
    debt_items = tmp_path / "debt" / "items"
    debt_items.mkdir(parents=True)
    debt_yaml = debt_items / "DEBT-TEST-CLOSE-REOPEN.yaml"
    debt_yaml.write_text(
        "id: DEBT-TEST-CLOSE-REOPEN\n"
        "title: Test Debt for close/reopen\n"
        "description: round 43 P0 unit test\n"
        "severity: low\n"
        "source: omo\n"
        "registered_at: '2026-06-15T00:00:00Z'\n"
        "lifecycle_state: identified\n"
        "history: []\n",
        encoding="utf-8",
    )
    return tmp_path


def _run_omo_debt(omo_dir: Path, command: str, debt_id: str, actor: str) -> int:
    """In-process 调 omo.omo_debt.main(), 注入 sys.argv. 返回 exit code."""
    from omo import omo_debt  # noqa: WPS433 (in-process is intentional)

    old_argv = sys.argv
    try:
        sys.argv = [
            "omo-debt",
            command,
            "--omo-dir",
            str(omo_dir),
            "--id",
            debt_id,
            "--actor",
            actor,
        ]
        return omo_debt.main()
    except (FileNotFoundError, SystemExit) as exc:
        # close 不存在的 id 抛 FileNotFoundError, 我们捕了再 return 非 0
        if isinstance(exc, SystemExit):
            return int(exc.code) if exc.code is not None else 0
        return 1
    finally:
        sys.argv = old_argv


def test_close_writes_lifecycle_state_and_history(tmp_omo_dir: Path) -> None:
    """omo-debt close 走正路, yaml 真改 lifecycle_state=closed + history append."""
    rc = _run_omo_debt(
        tmp_omo_dir, "close", "DEBT-TEST-CLOSE-REOPEN", "test-actor-close"
    )
    assert rc == 0, f"close 失败 rc={rc}"

    yaml_path = tmp_omo_dir / "debt" / "items" / "DEBT-TEST-CLOSE-REOPEN.yaml"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert data["lifecycle_state"] == "closed"
    assert data["gate_level"] == "none"

    history = data.get("history", [])
    assert len(history) == 1
    assert history[0]["action"] == "close"
    assert history[0]["actor"] == "test-actor-close"
    assert history[0]["note"] == "Closed debt item."
    assert history[0]["at"]  # 时间戳非空


def test_reopen_writes_lifecycle_state_and_history(tmp_omo_dir: Path) -> None:
    """omo-debt reopen 走正路, yaml 真改 lifecycle_state=identified + history append."""
    # 先 close 一次
    rc_close = _run_omo_debt(
        tmp_omo_dir, "close", "DEBT-TEST-CLOSE-REOPEN", "test-actor-step1"
    )
    assert rc_close == 0

    # 再 reopen
    rc_reopen = _run_omo_debt(
        tmp_omo_dir, "reopen", "DEBT-TEST-CLOSE-REOPEN", "test-actor-step2"
    )
    assert rc_reopen == 0

    yaml_path = tmp_omo_dir / "debt" / "items" / "DEBT-TEST-CLOSE-REOPEN.yaml"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert data["lifecycle_state"] == "identified"

    history = data.get("history", [])
    actions = [h["action"] for h in history]
    assert "close" in actions
    assert "reopen" in actions
    actors = {h["actor"] for h in history}
    assert "test-actor-step1" in actors
    assert "test-actor-step2" in actors


def test_close_unknown_id_returns_nonzero(tmp_omo_dir: Path) -> None:
    """omo-debt close 对不存在的 id 走 update_item 抛 FileNotFoundError 路径."""
    rc = _run_omo_debt(tmp_omo_dir, "close", "DEBT-DOES-NOT-EXIST", "test-actor")
    # 我们的 _run_omo_debt 捕了 FileNotFoundError 返 1
    assert rc != 0, f"close 不存在 id 应返非 0, got {rc}"


def test_yaml_bypass_lint_accepts_cli_written_yaml(tmp_omo_dir: Path) -> None:
    """omo lint yaml-bypass: omo-debt close CLI 写的 yaml 应 0 issue.

    集成一致性: omo-debt close 走正路 → yaml 合规 → lint 工具 0 issue.
    反向场景 (手工注入 status 字段越权) 在 audit 报告里有真实证据, 不在单测内复现.
    """
    # 1. 用 omo-debt close 走正路改 yaml
    rc_close = _run_omo_debt(
        tmp_omo_dir, "close", "DEBT-TEST-CLOSE-REOPEN", "lint-integration-test"
    )
    assert rc_close == 0

    # 2. 调 omo lint yaml-bypass (通过 _check_yaml_bypass 函数, 显式传 omo_dir)
    from omo.omo_lint import _check_yaml_bypass

    issues = _check_yaml_bypass(tmp_omo_dir)
    assert issues == [], (
        f"omo-debt close 写的 yaml 应 0 issue (合规), got: {issues}. "
        f"这意味着 lint 工具自身有 bug, 请报修."
    )


def test_yaml_bypass_lint_detects_status_field_bypass(tmp_omo_dir: Path) -> None:
    """omo lint yaml-bypass: 手工注入 status 字段越权 (R2) 应被检测.

    这是反向测试: 模拟 fix_debts.py 越权行为 (改 status 字段但 OMO 字段 lifecycle_state 不动).
    期望 lint 工具报 R2 issue.
    """
    # 1. 干净 baseline: 0 issue
    from omo.omo_lint import _check_yaml_bypass

    issues = _check_yaml_bypass(tmp_omo_dir)
    assert issues == [], f"干净 baseline 不应报 issue, got: {issues}"

    # 2. 模拟 fix_debts.py 越权: yaml 加 status=closed 但 lifecycle_state=identified (不一致)
    yaml_path = tmp_omo_dir / "debt" / "items" / "DEBT-TEST-CLOSE-REOPEN.yaml"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    data["status"] = "closed"  # 越权: OMO 不读 status
    yaml_path.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    # 3. lint 应报 R2 (status=closed 但 lifecycle_state=identified 不一致)
    issues = _check_yaml_bypass(tmp_omo_dir)
    r2_issues = [msg for _, msg in issues if "R2" in msg]
    assert r2_issues, f"应报 R2 (status 越权), got: {issues}"
