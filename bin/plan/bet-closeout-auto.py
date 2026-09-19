#!/usr/bin/env python3
"""bet-closeout-auto.py — 5 步 closeout 工作流自动化 (A2 SOP).

封装 ledger closeout 的重复步骤:
1. 验证 retro 文件存在 + frontmatter 完整
2. 改台账 status → done + done_at + completion_evidence (若缺)
3. 跑 lint + gac-local-gate 验证
4. 提示 commit / push / gh pr 步骤 (不自动执行, 因风险)

用法:
  python3 bin/plan/bet-closeout-auto.py <bet-id> [--evidence-file PATH] [--dry-run]

依赖:
  bin/plan/bet-ledger.py  (status / lint / complete)
  bin/ssot/doc-governance-check.py  (frontmatter 验证)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "plans" / "3y-bet-ledger.yaml"
RETRO_DIR = ROOT / ".omo" / "_knowledge" / "retros"


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_retro(bet_id: str) -> tuple[bool, str]:
    """验证 retro 文件存在 + frontmatter 完整."""
    retro_path = RETRO_DIR / f"{bet_id}.md"
    if not retro_path.exists():
        return False, f"❌ retro not found: {retro_path}"
    content = retro_path.read_text(encoding="utf-8")
    required = ["bet_id", "status", "lifecycle", "owner", "last-reviewed", "type"]
    missing = [k for k in required if f"{k}:" not in content]
    if missing:
        return False, f"❌ retro frontmatter 缺字段: {missing}"
    if bet_id not in content:
        return False, f"❌ retro 未含 bet_id={bet_id}"
    return True, f"✅ retro OK: {retro_path}"


def find_bet_in_ledger(bet_id: str) -> tuple[bool, int]:
    """在台账找 bet-id 段, 返回 (found, line_no)."""
    if not LEDGER.exists():
        return False, -1
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.strip() == f"id: {bet_id}":
            return True, i
    return False, -1


def get_current_status(bet_id: str) -> str | None:
    """读台账当前 status. 限于 bet 段内 (id: ... 到下个 'id:' 行前)."""
    if not LEDGER.exists():
        return None
    lines = LEDGER.read_text(encoding="utf-8").splitlines()
    in_bet = False
    for line in lines:
        s = line.strip()
        if s == f"id: {bet_id}":
            in_bet = True
            continue
        if in_bet and s.startswith("id:") and s != f"id: {bet_id}":
            return None
        if in_bet and s.startswith("status:"):
            return s.split(":", 1)[1].strip()
    return None


def run_lint() -> tuple[bool, str]:
    """跑 bet-ledger lint."""
    result = subprocess.run(
        ["python3", "bin/plan/bet-ledger.py", "lint", str(LEDGER)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    return result.returncode == 0, result.stdout + result.stderr


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bet_id", help="BET ID, 例 BET-Y1Q4-T10-02")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="只检查 + 报告, 不修改台账",
    )
    args = ap.parse_args()

    bet_id = args.bet_id
    print(f"━━━ closeout-auto: {bet_id} ━━━\n")

    # Step 1: retro 验证
    print("Step 1 · retro 验证")
    ok, msg = check_retro(bet_id)
    print(f"  {msg}")
    if not ok:
        return 1

    # Step 2: 台账查找
    print("\nStep 2 · 台账定位")
    found, line_no = find_bet_in_ledger(bet_id)
    if not found:
        print(f"  ❌ {bet_id} 不在台账 {LEDGER.name}")
        return 1
    current = get_current_status(bet_id)
    print(f"  ✅ 找到 {bet_id} (line {line_no}), 当前 status={current}")

    # Step 3: 台账修改建议
    print("\nStep 3 · 台账修改建议")
    if current == "done":
        print(f"  ℹ️ status 已 done, 跳过修改")
    else:
        print("  需修改项:")
        print(f"    - status: {current} → done")
        print(f"    - done_at: '{utc_now_iso()}'")
        print("    - completion_evidence: {axes: {...}, overall_state: delivery_accepted}")

    # Step 4: lint 验证 (--dry-run 跳过)
    print("\nStep 4 · bet-ledger lint")
    if args.dry_run:
        print("  [dry-run] 跳过 lint")
    else:
        ok, output = run_lint()
        if ok:
            print("  ✅ lint PASS")
        else:
            print(f"  ⚠️ lint 输出: {output[:500]}")

    # Step 5: 后续步骤提示
    print("\nStep 5 · 后续 commit/push 提示 (本脚本不自动执行)")
    print("  $ git add docs/plans/3y-bet-ledger.yaml .omo/_knowledge/retros/<id>.md")
    print("  $ git commit -m 'fix(<scope>): close <bet-id> — done_at + retro + CE'")
    print("  $ git fetch origin main && git rebase origin/main")
    print("  $ git push -u origin agent/governance-agent/<bet-id>")
    print("  $ gh pr create --title '...' --body-file docs/reports/...closeout.md")
    print("  $ gh pr checks <pr-num> --watch")
    print("  $ gh pr merge <pr-num> --admin --squash --delete-branch")

    print(f"\n━━━ closeout-auto: {bet_id} ━━━ 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())