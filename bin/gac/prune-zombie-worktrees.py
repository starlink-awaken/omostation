#!/usr/bin/env python3
"""prune-zombie-worktrees.py — 僵尸 worktree 清理 (T10-127, 吸收 gac-worktree-cleanup.sh)

僵尸判定 (三规则并集, 任一命中即僵尸):
  1. worktree 目录无 .git 文件 (checkout 损坏)
  2. 最后活动 (mtime) 超过 TTL (默认 7 天)
  3. 分支已完全合并进 origin/main 且无未推送 commit

安全: 默认 dry-run; --enforce 才真删; 有未提交改动的 worktree 永远跳过;
     删除时联动清理 D2 branch claim (防 occupancy 假占用)。

用法:
  python3 bin/gac/prune-zombie-worktrees.py            # dry-run 报告
  python3 bin/gac/prune-zombie-worktrees.py --enforce  # 实删
  python3 bin/gac/prune-zombie-worktrees.py --enforce --ttl-days 3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

WS_ROOT = Path(__file__).resolve().parents[2]


def _git(*args: str, cwd: Path | None = None) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd or WS_ROOT)
    return r.stdout.strip() if r.returncode == 0 else ""


def _claim_release(session: str) -> None:
    cli = WS_ROOT / "bin/gac/swarm-discipline-cli.py"
    if cli.exists():
        subprocess.run(
            [sys.executable, str(cli), "branch-release", "--session", session],
            capture_output=True,
            timeout=30,
        )


def _cleanup_guard(branch: str) -> str | None:
    """T10-140: 删除前置引用保护 (共享 lib/cleanup-guard; 加载失败宽容放行)."""
    try:
        sys.path.insert(0, str(WS_ROOT / "lib"))
        import cleanup_guard

        return cleanup_guard.protect_reason(branch)
    except Exception as exc:  # noqa: BLE001 — guard 故障不阻断清理主流程
        print(f"    ⚠️  guard 跳过 ({exc})")
        return None


def scan_zombies(ws_parent: Path, ttl_days: int) -> list[dict]:
    now = time.time()
    zombies: list[dict] = []
    for wt in sorted(ws_parent.glob("ws-*")):
        session = wt.name.removeprefix("ws-")
        claim_in_progress = ws_parent / f".ws-{session}.claiming"
        if claim_in_progress.is_file():
            zombies.append(
                {
                    "path": str(wt),
                    "reasons": ["claim-in-progress"],
                    "session": session,
                    "skip": True,
                }
            )
            continue
        gitfile = wt / ".git"
        # 规则 1: checkout 损坏
        if not gitfile.exists():
            zombies.append({"path": str(wt), "reasons": ["no-gitfile"], "session": session})
            continue
        branch = _git("rev-parse", "--abbrev-ref", "HEAD", cwd=wt)
        # 有未提交改动 → 永远跳过
        if _git("status", "--porcelain", cwd=wt):
            zombies.append({"path": str(wt), "reasons": ["dirty-skip"], "skip": True})
            continue
        reasons: list[str] = []
        # 规则 2: TTL 无活动
        files = [f for f in wt.rglob("*") if f.is_file()]
        mtime = max((f.stat().st_mtime for f in files), default=0)
        age_days = (now - mtime) / 86400
        if age_days > ttl_days:
            reasons.append(f"idle-{age_days:.1f}d")
        # 规则 3: 已合并且无未推 commit
        if branch and branch != "HEAD":
            unpushed = _git("log", "--oneline", "--not", "origin/main", branch, cwd=wt)
            merged = [b.strip().lstrip("* ") for b in _git("branch", "--merged", "origin/main", cwd=wt).splitlines()]
            if not unpushed and branch in merged:
                reasons.append("merged-clean")
        if reasons:
            zombies.append({"path": str(wt), "reasons": reasons, "session": session, "branch": branch})
    return zombies


def _registered_worktrees() -> tuple[bool, set[str]]:
    """Return a proved snapshot of root worktree registrations.

    An empty set is not a safe fallback: the root checkout itself must always
    appear in a successful porcelain response.  Preserve command failures so
    callers can fail closed instead of treating "unknown" as "unregistered".
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(WS_ROOT), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False, set()
    if result.returncode != 0:
        return False, set()
    paths = {line.removeprefix("worktree ") for line in result.stdout.splitlines() if line.startswith("worktree ")}
    if not paths or any(not Path(path).is_absolute() for path in paths):
        return False, set()
    return True, paths


def _session_guard_path(ws_parent: Path, session: str) -> Path:
    return ws_parent / f".ws-{session}.lifecycle-lock"


def _acquire_session_guard(ws_parent: Path, session: str) -> Path | None:
    """Atomically exclude a concurrent claimant or pruner for one session."""
    guard = _session_guard_path(ws_parent, session)
    try:
        guard.mkdir(mode=0o700)
    except OSError:
        return None
    return guard


def _release_session_guard(guard: Path) -> None:
    try:
        guard.rmdir()
    except OSError as exc:
        print(f"    ⚠️  lifecycle guard release failed: {guard} ({exc})")


def _revalidate_candidate(candidate: dict, ws_parent: Path) -> tuple[bool, str]:
    """Fail closed when a deletion candidate changes after the initial scan."""
    path = Path(str(candidate.get("path") or ""))
    session = str(candidate.get("session") or "")
    if not session or path.name != f"ws-{session}" or path.parent.resolve() != ws_parent.resolve():
        return False, "candidate-identity-drift"
    if (ws_parent / f".ws-{session}.claiming").is_file():
        return False, "claim-in-progress"
    if not path.is_dir():
        return False, "target-missing"
    registered_ok, registered = _registered_worktrees()
    if not registered_ok:
        return False, "registered-state-unprovable"
    if str(path) in registered:
        return False, "registered-worktree"

    gitfile = path / ".git"
    expected_branch = str(candidate.get("branch") or "")
    if not gitfile.exists():
        if expected_branch or "no-gitfile" not in candidate.get("reasons", []):
            return False, "git-identity-drift"
        return True, "stable-no-gitfile"

    status = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if status.returncode != 0:
        return False, "git-status-unreadable"
    if status.stdout.strip():
        return False, "dirty-worktree"

    branch = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if branch.returncode != 0:
        return False, "branch-unreadable"
    if expected_branch and branch.stdout.strip() != expected_branch:
        return False, "branch-identity-drift"
    return True, "stable"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--enforce", action="store_true", help="真删 (默认 dry-run)")
    ap.add_argument("--ttl-days", type=int, default=7)
    args = ap.parse_args(argv)

    ws_parent = WS_ROOT.parent
    zombies = scan_zombies(ws_parent, args.ttl_days)
    # T10-140 迭代: 注册中的 worktree (git worktree list 认) = 活现场,
    # 不论 merged-clean/idle 一律跳过 — 僵尸语义修正 (git 不认的孤儿目录才是僵尸).
    # 背景: merged-clean 判定曾把并行方的活 worktree 标为可删 (dry-run 实测).
    registered_ok, registered = _registered_worktrees()
    if not registered_ok:
        print("⛔ registered-state-unprovable")
        return 2
    mode = "ENFORCE" if args.enforce else "DRY-RUN"
    print(f"=== Zombie Worktree 扫描 ({mode}, ttl={args.ttl_days}d) ===")
    removed = 0
    for z in zombies:
        if z.get("skip"):
            if "claim-in-progress" in z["reasons"]:
                print(f"  ⏭  跳过 (claim 初始化进行中): {z['path']}")
            else:
                print(f"  ⏭  跳过 (有未提交改动): {z['path']} — 请人工处理")
            continue
        if z["path"] in registered:
            print(f"  ⏭  跳过 (注册中 worktree, 活现场): {z['path']} [{', '.join(z['reasons'])}]")
            continue
        print(f"  僵尸: {z['path']} [{', '.join(z['reasons'])}]")
        if args.enforce and z.get("session"):
            lifecycle_guard = _acquire_session_guard(ws_parent, z["session"])
            if lifecycle_guard is None:
                print(f"    ⏭  lifecycle-guard-held: {z['session']}")
                continue
            try:
                stable, stable_reason = _revalidate_candidate(z, ws_parent)
                if not stable:
                    print(f"    ⏭  删除前二次确认拒绝: {stable_reason}")
                    continue
                # T10-140 引用保护: 分支有未推 commit / open PR / 活跃认领 → 只删 worktree 留分支
                guard_skip = False
                if z.get("branch") and z["branch"] != "HEAD":
                    guard = _cleanup_guard(z["branch"])
                    if guard is not None:
                        print(f"    ⛔ 分支保留 (引用保护 {guard}): {z['branch']}")
                        guard_skip = True
                stable, stable_reason = _revalidate_candidate(z, ws_parent)
                if not stable:
                    print(f"    ⏭  删除前最终确认拒绝: {stable_reason}")
                    continue
                removal = subprocess.run(
                    ["git", "worktree", "remove", "--force", z["path"]],
                    capture_output=True,
                    text=True,
                )
                if removal.returncode != 0 or Path(z["path"]).exists():
                    detail = (removal.stderr or removal.stdout or "target still exists").strip()
                    print(f"    ⛔ 删除失败, 保留 claim: {z['path']} — {detail}")
                    continue
                if z.get("branch") and z["branch"] != "HEAD" and not guard_skip:
                    subprocess.run(["git", "branch", "-D", z["branch"]], capture_output=True)
                _claim_release(z["session"])
                removed += 1
            finally:
                _release_session_guard(lifecycle_guard)
    print(f"=== 结果: 发现 {len(zombies)} (跳过 {sum(1 for z in zombies if z.get('skip'))}), 实删 {removed} ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
