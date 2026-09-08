#!/usr/bin/env python3
"""cleanup-guard — 清理器引用保护 (BET-Y1Q4-T10-140).

并行 agent 无差别 reset/prune 吃掉未推 commit 与活跃工作面 (T10-139 交付期间
7 次观测)。本模块是三个清理器 (prune-zombie-worktrees / branch-ttl-gate /
gac-branch-prune) 的共享删除前置检查:

  protect_reason(branch) -> str | None
    1. unpushed   — 分支有未推送到远端的 commit (git log @{u}.. / origin/<b>..)
    2. open-pr    — 分支有关联 open PR (gh, 查询失败宽容放行)
    3. bet-claimed — 分支名含活跃 BET 认领的 bet_id (T10-139 广播联动)

返回 None = 可删; 返回原因字符串 = 跳过并警告。
CLI: python3 lib/cleanup-guard.py check <branch>  # exit 0=可删 1=保护 2=错误
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
CLAIMS_DIR = WS / ".omo" / "_delivery" / "bet-claims"

_active_claims_cache: list[str] | None = None


def _git(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd or WS)
    return r.stdout.strip() if r.returncode == 0 else ""


def has_unpushed_commits(branch: str, cwd: Path | None = None) -> bool:
    """分支有未推 commit: 有 upstream 比 @{u}..b; 无 upstream 比 origin/<b>..b;
    远端也无同名分支 → 整条分支都是未推 (True)."""
    upstream = _git("rev-parse", "--abbrev-ref", f"{branch}@{{u}}", cwd=cwd)
    base = upstream if upstream and "origin" in upstream else f"origin/{branch}"
    probe = _git("rev-parse", "--verify", base, cwd=cwd)
    if not probe:
        return True  # 远端不存在该分支 → 全部 commit 都是本地未推
    return bool(_git("log", "--oneline", f"{base}..{branch}", cwd=cwd))


def pr_open(branch: str) -> bool:
    """分支有 open PR; gh 不可用/超时 → False (宽容, 不因查询失败阻断清理)."""
    try:
        r = subprocess.run(
            ["gh", "pr", "list", "--head", branch, "--state", "open", "--json", "number"],
            capture_output=True, text=True, timeout=30, cwd=WS,
        )
        return bool(json.loads(r.stdout or "[]"))
    except Exception:  # noqa: BLE001 — 查询故障不阻断清理主流程
        return False


def active_claim_bets() -> list[str]:
    """活跃 BET 认领的 bet_id 列表 (T10-139 广播; 进程内缓存一次)."""
    global _active_claims_cache
    if _active_claims_cache is None:
        bets: list[str] = []
        if CLAIMS_DIR.is_dir():
            for f in CLAIMS_DIR.glob("*.json"):
                try:
                    claim = json.loads(f.read_text(encoding="utf-8"))
                    bet_id = claim.get("bet_id")
                    if bet_id:
                        bets.append(str(bet_id))
                except (OSError, json.JSONDecodeError):
                    continue
        _active_claims_cache = bets
    return _active_claims_cache


def protect_reason(branch: str, cwd: Path | None = None) -> str | None:
    """删除前置检查: 返回 None=可删, str=保护原因.

    bet-claimed 匹配双形态: 全 id (BET-Y1Q4-T10-139) 或尾段短 id (T10-139,
    真实分支命名惯例 work/t10-139-xxx) — 短 id 带边界匹配防 T10-13 误吃 T10-139.
    """
    if has_unpushed_commits(branch, cwd=cwd):
        return "unpushed"
    if pr_open(branch):
        return "open-pr"
    b_lower = branch.lower()
    for bet in active_claim_bets():
        if not bet:
            continue
        if bet in branch:
            return f"bet-claimed ({bet})"
        short = bet.rsplit("-", 1)[-1].lower()  # BET-Y1Q4-T10-139 → t10-139
        if short and (f"-{short}-" in b_lower or b_lower.endswith(f"-{short}")):
            return f"bet-claimed ({bet})"
    return None


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="清理器引用保护 (T10-140)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    chk = sub.add_parser("check", help="检查分支是否可删")
    chk.add_argument("branch")
    chk.add_argument("--cwd", default=None, help="仓库目录 (默认主仓)")
    args = ap.parse_args(argv)

    if args.cmd == "check":
        reason = protect_reason(args.branch, Path(args.cwd) if args.cwd else None)
        if reason is None:
            print("DELETABLE")
            return 0
        print(f"PROTECTED: {reason}")
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
