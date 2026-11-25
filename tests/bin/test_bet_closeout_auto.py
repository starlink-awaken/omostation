#!/usr/bin/env python3
"""Tests for bet-closeout-auto.py.

分两层:
  · helper 单测 (check_retro / find_bet_in_ledger / get_current_status / 时间戳格式)
  · **真实 CLI 契约** (OMO-DEBT-BET-CLOSEOUT-AUTO-PROPOSES-AS-APPLIES): 旧版把「只打印建议」
    写成「已改台账」, 且 Step 4 的 lint 因多传一个台账位置参数而必然 argparse 非零退出,
    却被打成 ⚠️ 后继续 return 0 —— 整步空转。lint 失败用临时树 + 真实子进程触发
    (复制被测脚本, 配一个按指定码退出的 bet-ledger 替身), 缝在进程边界上,
    才钉得住 argparse 那一类接线漂移。

Run: python3 tests/bin/test_bet_closeout_auto.py
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "plan" / "bet-closeout-auto.py"
FIXTURE_BET = "BET-FIXTURE-CO"
# 活仓库里 retro 齐备且台账 status=done 的真实条目 (2026-11-25 实测)
LIVE_BET = "BET-Y2Q4-T10-344"


def _load(tmp_dir: Path | None = None):
    spec = importlib.util.spec_from_file_location("closeout_auto", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    sys.modules["closeout_auto"] = m
    spec.loader.exec_module(m)
    if tmp_dir is not None:
        # 默认 RETRO_DIR 指向仓内**已跟踪**的 .omo/_knowledge/retros/ —— 直接写它会让每次跑测试
        # 都把工作树改脏 (实证: BET-TEST-001.md / BET-BAD-002.md 已被这样的跑法提交进仓)。
        m.RETRO_DIR = tmp_dir / ".omo" / "_knowledge" / "retros"
    return m


def test_check_retro_found(tmp_path):
    m = _load(tmp_path)
    retro = m.RETRO_DIR / "BET-TEST-001.md"
    retro.parent.mkdir(parents=True, exist_ok=True)
    retro.write_text(
        """---
bet_id: BET-TEST-001
status: closed
lifecycle: history
owner: test
last-reviewed: 2026-09-19
type: ephemeral
---
content"""
    )
    ok, msg = m.check_retro("BET-TEST-001")
    assert ok, msg


def test_check_retro_missing():
    m = _load()
    ok, msg = m.check_retro("BET-NONEXISTENT-999")
    assert not ok
    assert "not found" in msg


def test_check_retro_missing_frontmatter(tmp_path):
    m = _load(tmp_path)
    retro = m.RETRO_DIR / "BET-BAD-002.md"
    retro.parent.mkdir(parents=True, exist_ok=True)
    retro.write_text("---\nbet_id: BET-BAD-002\n---\nno status field")
    ok, msg = m.check_retro("BET-BAD-002")
    assert not ok
    assert "frontmatter" in msg.lower()


def test_find_bet_in_ledger():
    m = _load()
    # Real test: BET-Y1Q4-T10-125 exists in main ledger
    ok, line = m.find_bet_in_ledger("BET-Y1Q4-T10-125")
    assert ok
    assert line > 0


def test_find_bet_not_in_ledger():
    m = _load()
    ok, line = m.find_bet_in_ledger("BET-NEVER-EXISTED-999")
    assert not ok
    assert line == -1


def test_get_current_status_done():
    m = _load()
    # Real test: BET-Y1Q4-T10-125 is done
    status = m.get_current_status("BET-Y1Q4-T10-125")
    assert status == "done"


def test_get_current_status_in_progress():
    m = _load()
    # Find any in_progress bet for testing
    import yaml
    ledger_path = m.LEDGER
    if not ledger_path.exists():
        return
    data = yaml.safe_load(ledger_path.read_text())
    # The ledger schema isn't simple flat list; just verify None for invalid id
    assert m.get_current_status("BET-INVALID-999") is None


def test_utc_today_format():
    m = _load()
    today = m.utc_today()
    # YYYY-MM-DD = 10 chars
    assert len(today) == 10
    assert today[4] == "-"
    assert today[7] == "-"


def test_utc_now_iso_format():
    m = _load()
    iso = m.utc_now_iso()
    # YYYY-MM-DDTHH:MM:SSZ = 20 chars
    assert len(iso) == 20
    assert iso[10] == "T"
    assert iso.endswith("Z")


def _cli(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
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
        "status: closed\n"
        "lifecycle: history\n"
        "owner: governance-agent\n"
        "last-reviewed: 2026-11-25\n"
        "type: ephemeral\n"
        "---\n\n# retro\n",
        encoding="utf-8",
    )
    return ws


def _closeout(ws: Path, *extra: str):
    return _cli(["python3", "bin/plan/bet-closeout-auto.py", FIXTURE_BET, *extra], cwd=ws)


def test_lint_failure_is_a_hard_fail(tmp_path):
    ws = _fixture_tree(tmp_path, lint_rc=1)
    run = _closeout(ws)
    combined = run.stdout + run.stderr
    assert run.returncode != 0, f"lint rc=1 却放行:\n{combined}"
    assert "lint FAIL" in combined, combined
    assert "lint PASS" not in combined, combined


def test_lint_success_path_advises_without_claiming_a_write(tmp_path):
    ws = _fixture_tree(tmp_path, lint_rc=0)
    run = _closeout(ws)
    combined = run.stdout + run.stderr
    assert run.returncode == 0, combined
    assert "lint PASS" in combined, combined
    # Step 3: in_progress 条目必须给出带前置校验的落盘命令, 而不是把自己伪装成落盘方
    assert "本脚本不写台账" in combined, combined
    assert f"bet-ledger.py complete {FIXTURE_BET}" in combined, combined
    # 台账真的没被改过 —— 建议不等于执行
    ledger_text = (ws / "docs" / "plans" / "3y-bet-ledger.yaml").read_text(encoding="utf-8")
    assert "status: in_progress" in ledger_text, "脚本声称不写台账, 却改了台账"


def test_step5_does_not_suggest_forbidden_rebase(tmp_path):
    ws = _fixture_tree(tmp_path, lint_rc=0)
    run = _closeout(ws)
    combined = run.stdout + run.stderr
    assert "git rebase" not in combined, "AGENTS §6 禁止用 rebase 吸收上游, 提示语不得教它"
    assert "--base main" in combined, "gh pr create 提示缺 --base/--head 显式参数"


def test_live_lint_step_really_runs():
    """活仓库端到端: 本脚本调用 lint 的形式必须仍与 `bet-ledger.py lint` 的签名对得上.

    这条是空转的直接守卫 —— 旧版多传一个台账路径, argparse 报 unrecognized arguments,
    rc != 0 被旧代码打成 ⚠️ 后照样 return 0, 于是「lint PASS/FAIL」永远不出现。
    """
    run = _cli(["python3", "bin/plan/bet-closeout-auto.py", LIVE_BET], cwd=ROOT)
    combined = run.stdout + run.stderr
    assert run.returncode == 0, combined
    assert "lint PASS" in combined, combined
    assert "status 已 done" in combined, combined


def test_dry_run_skips_only_lint():
    run = _cli(["python3", "bin/plan/bet-closeout-auto.py", LIVE_BET, "--dry-run"], cwd=ROOT)
    combined = run.stdout + run.stderr
    assert run.returncode == 0, combined
    assert "跳过 lint" in combined, combined
    assert "lint PASS" not in combined, combined


if __name__ == "__main__":
    import inspect
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    failures = []
    for name, fn in tests:
        try:
            sig = inspect.signature(fn)
            kwargs = {}
            if "tmp_path" in sig.parameters:
                from tempfile import mkdtemp
                kwargs["tmp_path"] = Path(mkdtemp())
            if "monkeypatch" in sig.parameters:
                import _pytest.monkeypatch as mp_mod
                kwargs["monkeypatch"] = mp_mod.MonkeyPatch()
            fn(**kwargs)
            print(f"  PASS {name}")
        except Exception as e:
            print(f"  FAIL {name}: {e}")
            failures.append((name, e))
    if failures:
        sys.exit(1)
    print(f"\n{len(tests)} tests passed")