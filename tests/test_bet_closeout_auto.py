"""bet-closeout-auto 的三条硬契约 (OMO-DEBT-BET-CLOSEOUT-AUTO-PROPOSES-AS-APPLIES).

旧版把「建议」写得像「已执行」, 且 Step 4 的 lint 因多传一个台账位置参数而必然
argparse 非零退出, 却被打成 ⚠️ 后继续 return 0 —— 整步空转。用例因此钉三件事:

  1. lint 真的在跑 (活仓库路径: 必须出现 ✅ lint PASS, 而不是 ⚠️)
  2. lint rc != 0 ⇒ 整单失败 (rc != 0), 不放行
  3. Step 3/5 的措辞不再谎报落盘, 且不再教 `git rebase` (AGENTS §6 禁止吸收上游)

lint 失败用**临时树 + 真实 CLI** 触发 (复制被测脚本, 配一个非零退出的 bet-ledger 替身),
不 monkeypatch 函数内部 —— 缝在进程边界上, 才钉得住 argparse 那一类接线漂移。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "plan" / "bet-closeout-auto.py"
FIXTURE_BET = "BET-FIXTURE-CO"
# 活仓库里 retro 齐备且台账 status=done 的真实条目 (2026-11-25 实测)
LIVE_BET = "BET-Y2Q4-T10-344"


def _run(cmd: list[str], *, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def _fixture_tree(tmp_path: Path, *, lint_rc: int) -> Path:
    """一棵最小工作区: 被测脚本 + lint 替身 (按 lint_rc 退出) + in_progress 台账条目."""
    ws = tmp_path / "ws"
    (ws / "bin" / "plan").mkdir(parents=True)
    (ws / "docs" / "plans").mkdir(parents=True)
    (ws / ".omo" / "_knowledge" / "retros").mkdir(parents=True)
    (ws / "bin" / "plan" / "bet-closeout-auto.py").write_text(
        SCRIPT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (ws / "bin" / "plan" / "bet-ledger.py").write_text(
        f"import sys\nprint('stub lint')\nsys.exit({lint_rc})\n", encoding="utf-8"
    )
    (ws / "docs" / "plans" / "3y-bet-ledger.yaml").write_text(
        f"bets:\n- id: {FIXTURE_BET}\n  status: in_progress\n", encoding="utf-8"
    )
    (ws / ".omo" / "_knowledge" / "retros" / f"{FIXTURE_BET}.md").write_text(
        "---\n"
        f"bet_id: {FIXTURE_BET}\n"
        "status: done\n"
        "lifecycle: record\n"
        "owner: governance-agent\n"
        "last-reviewed: 2026-11-25\n"
        "type: retro\n"
        "---\n\n# retro\n",
        encoding="utf-8",
    )
    return ws


def _closeout(ws: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return _run(
        ["python3", "bin/plan/bet-closeout-auto.py", FIXTURE_BET, *extra], cwd=ws
    )


def test_lint_failure_is_a_hard_fail(tmp_path: Path) -> None:
    ws = _fixture_tree(tmp_path, lint_rc=1)
    run = _closeout(ws)
    combined = run.stdout + run.stderr
    assert run.returncode != 0, f"lint rc=1 却放行:\n{combined}"
    assert "lint FAIL" in combined, combined
    assert "lint PASS" not in combined, combined


def test_lint_success_path_advises_without_claiming_a_write(tmp_path: Path) -> None:
    ws = _fixture_tree(tmp_path, lint_rc=0)
    run = _closeout(ws)
    combined = run.stdout + run.stderr
    assert run.returncode == 0, combined
    assert "lint PASS" in combined, combined
    # Step 3: in_progress 条目必须给出带前置校验的落盘命令, 而不是把自己伪装成落盘方
    assert "本脚本不写台账" in combined, combined
    assert f"bet-ledger.py complete {FIXTURE_BET}" in combined, combined
    # 台账真的没被改过 —— 建议不等于执行
    assert "status: in_progress" in (ws / "docs" / "plans" / "3y-bet-ledger.yaml").read_text(
        encoding="utf-8"
    ), "脚本声称不写台账, 却改了台账"


def test_step5_does_not_suggest_forbidden_rebase(tmp_path: Path) -> None:
    ws = _fixture_tree(tmp_path, lint_rc=0)
    combined = _closeout(ws).stdout + _closeout(ws).stderr
    assert "git rebase" not in combined, "AGENTS §6 禁止用 rebase 吸收上游, 提示语不得教它"
    assert "--base main" in combined, "gh pr create 提示缺 --base/--head 显式参数"


def test_live_lint_step_really_runs(tmp_path: Path) -> None:
    """活仓库端到端: lint 子命令的签名与本脚本的调用方式必须仍然对得上.

    这条是空转的直接守卫 —— 旧版多传一个台账路径, argparse 报 unrecognized arguments,
    rc != 0 被旧代码打成 ⚠️ 后照样 return 0, 于是「lint PASS/FAIL」永远不出现。
    """
    run = _run(["python3", "bin/plan/bet-closeout-auto.py", LIVE_BET])
    combined = run.stdout + run.stderr
    assert run.returncode == 0, combined
    assert "lint PASS" in combined, combined
    assert "status 已 done" in combined, combined


def test_dry_run_skips_only_lint() -> None:
    run = _run(["python3", "bin/plan/bet-closeout-auto.py", LIVE_BET, "--dry-run"])
    combined = run.stdout + run.stderr
    assert run.returncode == 0, combined
    assert "跳过 lint" in combined, combined
    assert "lint PASS" not in combined, combined
