#!/usr/bin/env python3
"""
worktree-janitor.py — PR-C worktree 三条件安全清理

三条件全部满足才可清理（缺一不可）:
1. 无活跃 claim：claim 文件不存在或对应 run 已 close
2. 无未推送变更：git status clean + 本地分支已 push 或远程已删
3. 分支已 merge 或已删：origin/main 包含该分支，或远程已删且 HEAD 可达

补充规则：worktree mtime 超过 24h 未活动

用法:
    python bin/gac/worktree-janitor.py          # dry-run 模式（默认）
    python bin/gac/worktree-janitor.py --apply  # 真清理
"""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple


@dataclass
class WorktreeInfo:
    """worktree 信息"""
    path: Path
    session: str
    branch: str
    mtime: float

    def age_hours(self) -> float:
        """age in hours"""
        now = datetime.now(timezone.utc).timestamp()
        return (now - self.mtime) / 3600


def run_git(cwd: Path, *args: str) -> str:
    """执行 git 命令，返回 stdout"""
    result = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def get_file_mtime(path: Path) -> float:
    """获取文件/目录 mtime（跨平台兼容）"""
    try:
        stat = path.stat()
        # macOS: st_mtime, Linux: st_mtime
        return stat.st_mtime
    except OSError:
        return 0.0


def list_worktrees(root_repo: Path) -> list[WorktreeInfo]:
    """列出所有 /Users/xiamingxing/ws-* worktree（跳过主仓）"""
    worktrees = []
    parent = root_repo.parent

    # git worktree list 获取全部
    output = run_git(root_repo, "worktree", "list", "--porcelain")
    if not output:
        return worktrees

    lines = output.split("\n")
    current_path = None
    for line in lines:
        if not line:
            continue
        if line.startswith("worktree "):
            wt_path = Path(line[len("worktree "):].strip())
            # 只处理 ws-* 开头的 worktree，且在 parent 目录下
            if wt_path.parent == parent and wt_path.name.startswith("ws-"):
                current_path = wt_path
        elif current_path and line.startswith("branch "):
            branch = line[len("branch "):].strip()
            # refs/heads/work/xxx -> work/xxx
            if branch.startswith("refs/heads/"):
                branch = branch[len("refs/heads/"):]
            session = current_path.name[len("ws-"):]
            mtime = get_file_mtime(current_path)
            worktrees.append(
                WorktreeInfo(path=current_path, session=session, branch=branch, mtime=mtime)
            )
            current_path = None

    return worktrees


def check_claim_inactive(root_repo: Path, session: str) -> Tuple[bool, str]:
    """
    条件1：无活跃 claim
    - claim 文件不存在
    - 或 run status 非 active（closed/failed等）
    """
    claim_dir = root_repo / ".omo" / "_delivery" / "branch-claims"
    claim_file = claim_dir / f"{session}.json"

    if not claim_file.exists():
        return True, "no claim file"

    try:
        data = json.loads(claim_file.read_text())
        # 检查 coordination_token 或 status 字段
        if "coordination_token" in data:
            token = data["coordination_token"]
            if token and token != 0:
                return False, f"active claim (token={token})"
        if "status" in data:
            status = data["status"]
            if status == "active":
                return False, f"active run (status={status})"
        return True, "inactive claim"
    except (json.JSONDecodeError, IOError):
        # 读取失败，保守保留
        return False, "claim file unreadable"


def check_no_unpushed_changes(wt_info: WorktreeInfo) -> Tuple[bool, str]:
    """
    条件2：无未推送变更
    - git status --porcelain 为空
    - 本地分支已在远程（git branch -r --contains HEAD 非空）
    - 或远程已删（branch 不在 git ls-remote）
    """
    # 2.1 检查 status
    status_output = run_git(wt_info.path, "status", "--porcelain")
    if status_output:
        return False, f"dirty ({len(status_output.splitlines())} files)"

    # 2.2 检查远程是否存在该分支
    branch_ref = f"refs/heads/{wt_info.branch}"
    ls_remote = run_git(wt_info.path, "ls-remote", "--heads", "origin", wt_info.branch)
    if ls_remote:
        # 远程存在，检查本地是否已 push
        # git branch -r --contains HEAD 检查远程是否包含当前 commit
        contains = run_git(wt_info.path, "branch", "-r", "--contains", "HEAD")
        if contains:
            return True, "pushed"
        return False, "not pushed"
    else:
        # 远程已删，条件满足
        return True, "remote deleted"


def check_branch_merged_or_deleted(wt_info: WorktreeInfo, root_repo: Path) -> Tuple[bool, str]:
    """
    条件3：分支已 merge 或已删
    - git branch --merged origin/main 包含该分支
    - 或 origin 上已无此分支且 git merge-base --is-ancestor HEAD origin/main
    """
    # 3.1 检查远程是否存在
    ls_remote = run_git(root_repo, "ls-remote", "--heads", "origin", wt_info.branch)
    if not ls_remote:
        # 远程已删，检查 HEAD 是否可达
        is_ancestor = run_git(
            wt_info.path, "merge-base", "--is-ancestor", "HEAD", "origin/main"
        )
        if is_ancestor:
            return True, "deleted and ancestor"
        return False, "deleted but not ancestor"

    # 3.2 检查是否已 merge 到 origin/main
    merged_output = run_git(root_repo, "branch", "--merged", "origin/main")
    if wt_info.branch in merged_output.splitlines():
        return True, "merged"

    return False, "not merged"


def judge_worktree(wt_info: WorktreeInfo, root_repo: Path, min_age_hours: float = 24.0) -> Tuple[bool, str]:
    """
    判定 worktree 是否可清理

    Returns:
        (can_clean, reason) - can_clean=True 可清理，reason 为判定原因
    """
    # 补充规则：mtime 检查
    age = wt_info.age_hours()
    if age < min_age_hours:
        return False, f"too fresh ({age:.1f}h < {min_age_hours}h)"

    # 条件1：claim inactive
    claim_ok, claim_reason = check_claim_inactive(root_repo, wt_info.session)
    if not claim_ok:
        return False, f"claim active: {claim_reason}"

    # 条件2：无未推送变更
    unpushed_ok, unpushed_reason = check_no_unpushed_changes(wt_info)
    if not unpushed_ok:
        return False, f"unpushed: {unpushed_reason}"

    # 条件3：分支已 merge 或已删
    merged_ok, merged_reason = check_branch_merged_or_deleted(wt_info, root_repo)
    if not merged_ok:
        return False, f"branch: {merged_reason}"

    return True, f"clean (age={age:.1f}h, claim={claim_reason}, unpushed={unpushed_reason}, merged={merged_reason})"


def remove_worktree(wt_info: WorktreeInfo, root_repo: Path) -> bool:
    """清理 worktree + 分支"""
    try:
        # git worktree remove --force
        result = subprocess.run(
            ["git", "-C", str(root_repo), "worktree", "remove", "--force", str(wt_info.path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"  ❌ worktree remove 失败: {result.stderr}", file=sys.stderr)
            return False

        # git branch -D
        result = subprocess.run(
            ["git", "-C", str(root_repo), "branch", "-D", wt_info.branch],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"  ❌ branch delete 失败: {result.stderr}", file=sys.stderr)
            return False

        return True
    except Exception as e:
        print(f"  ❌ 清理异常: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="PR-C worktree 三条件安全清理")
    parser.add_argument("--apply", action="store_true", help="真清理（默认 dry-run）")
    parser.add_argument("--min-age", type=float, default=24.0, help="最小 age（小时）")
    args = parser.parse_args()

    # 解析主仓路径
    root_repo = Path.cwd()
    while root_repo != root_repo.parent:
        if (root_repo / ".git").exists():
            break
        root_repo = root_repo.parent
    else:
        print("❌ 不在 git 仓库内", file=sys.stderr)
        sys.exit(1)

    worktrees = list_worktrees(root_repo)

    if not worktrees:
        print("✅ 无需清理的 worktree")
        return

    # 判定并分类
    to_clean = []
    to_keep = []

    for wt in worktrees:
        can_clean, reason = judge_worktree(wt, root_repo, args.min_age)
        if can_clean:
            to_clean.append((wt, reason))
        else:
            to_keep.append((wt, reason))

    # 打印表格
    print(f"{'SESSION':<20} {'BRANCH':<20} {'AGE':<8} {'STATUS':<30}")
    print("-" * 80)

    for wt, reason in to_keep:
        print(f"{wt.session:<20} {wt.branch:<20} {wt.age_hours():>6.1f}h  KEEP: {reason}")

    for wt, reason in to_clean:
        print(f"{wt.session:<20} {wt.branch:<20} {wt.age_hours():>6.1f}h  CLEAN: {reason}")

    print("-" * 80)
    print(f"总计: {len(worktrees)} worktree, 可清理 {len(to_clean)}, 保留 {len(to_keep)}")

    if args.apply:
        if not to_clean:
            return

        print("\n⚡ 执行清理...")
        failed = 0
        for wt, reason in to_clean:
            print(f"  清理 {wt.session}...")
            if remove_worktree(wt, root_repo):
                print(f"    ✅ {wt.path}")
            else:
                failed += 1
                print(f"    ❌ 清理失败")

        if failed > 0:
            sys.exit(1)
        print(f"\n✅ 清理完成 ({len(to_clean) - failed}/{len(to_clean)})")
    else:
        print("\n💡 dry-run 模式。添加 --apply 执行真清理")


if __name__ == "__main__":
    main()
