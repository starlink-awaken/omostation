"""cron 作业「worktree + 自动 PR」发布模式共享库 (BET-Y2Q4-T10-357 提炼).

背景: 直提家族 cron job (主仓工作区 git commit, push 失败必分叉) 的断根模式。
T356 (BET-Y2Q4-T10-356) 在 gen-capability-registry.py 落地 --publish; 本库将其
提炼为参数化实现, 供同族 job 零成本接入 (第二个接入者: check-mcptool-impl-drift)。

流程 (与 T356 一字不差):
  fetch → 临时 worktree (origin/main 基 + 子模块 init) → 跑生成命令 →
  无漂移即弃 → commit/push → gh pr create + merge --squash --auto → 清理
全程不碰主仓工作区; 任一步失败只清理退出, 绝不回退直提主仓。
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path


def publish_via_pr(
    *,
    workspace: Path,
    run_cmd: list[str],
    add_paths: list[str],
    branch_prefix: str,
    title: str,
    body: str,
    cmd_nonzero_ok: bool = False,
) -> int:
    """在临时 worktree 中跑 run_cmd 并经 PR 发布产物.

    Args:
        workspace: 主仓根 (fetch/worktree 操作锚点; run_cmd 在临时 worktree 内跑).
        run_cmd: worktree 内要执行的命令 (元素列表; 相对 worktree 根).
        add_paths: git add 路径 (相对 worktree 根).
        branch_prefix: 分支前缀, 实际分支 = f"{branch_prefix}-YYYYMMDD".
        title: PR 标题 (建议含日期).
        body: PR 正文.
        cmd_nonzero_ok: True 时 run_cmd 非零退出不视为失败 (业务信号语义,
            如 drift 检测 rc=1 表示有 drift, 产物已写出)。

    Returns: 0 = 成功 (含无漂移跳过), 1 = 失败 (细节已打 stderr)。
    """
    today = date.today()
    date_str = today.isoformat()
    branch = f"{branch_prefix}-{today:%Y%m%d}"
    tmp = Path(tempfile.mkdtemp(prefix="cronpub-"))
    # cron 的 PATH 精简 (/usr/bin:/bin), gh/git/uv 需显式补位 (uv 在 ~/.local/bin,
    # 探针类脚本 subprocess 裸调 uv —— T357 实测)
    env = dict(os.environ)
    env["PATH"] = (
        "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:"
        + os.path.expanduser("~/.local/bin") + ":"
        + env.get("PATH", "")
    )

    def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
        cmd = ["git"]
        if cwd is not None:
            cmd += ["-C", str(cwd)]
        cmd += args
        return subprocess.run(cmd, capture_output=True, text=True, env=env)

    def fail(step: str, r: subprocess.CompletedProcess) -> int:
        print(f"❌ publish 失败 @ {step}: rc={r.returncode}", file=sys.stderr)
        if r.stdout.strip():
            print(r.stdout.strip(), file=sys.stderr)
        if r.stderr.strip():
            print(r.stderr.strip(), file=sys.stderr)
        return 1

    pr_url = ""
    try:
        # 1. 拿最新主干 (fetch 不动主仓工作区)
        r = git("fetch", "origin", "main", cwd=workspace)
        if r.returncode:
            return fail("fetch origin main", r)

        # 2. 临时 worktree 基于 origin/main (与主仓工作区完全隔离)
        r = git("worktree", "add", "-b", branch, str(tmp), "origin/main", cwd=workspace)
        if r.returncode:
            return fail("worktree add", r)

        # 2b. 子模块 checkout (实测 ~83s, 本地对象库复用): 扫 projects/* 子模块
        #     源的脚本无此步必崩 (NativeInspectionError source_unprovable, T356 实测)
        r = git("-c", "protocol.file.allow=always",
                "submodule", "update", "--init", "--depth", "1", cwd=tmp)
        if r.returncode:
            return fail("submodule update", r)

        # 3. worktree 内跑生成命令
        r = subprocess.run(run_cmd, capture_output=True, text=True, env=env, cwd=tmp)
        if r.returncode and not cmd_nonzero_ok:
            return fail("worktree 内执行命令", r)

        # 4. add + 无漂移即弃
        git("add", "--", *add_paths, cwd=tmp)
        r = git("diff", "--cached", "--quiet", cwd=tmp)
        if r.returncode == 0:
            print(f"✅ 产物无漂移, 跳过发布 ({date_str})")
            return 0

        # 5. commit + push (不带 [skip ci]: required checks 需真跑才能 auto-merge)
        r = git("commit", "-m", title, cwd=tmp)
        if r.returncode:
            return fail("commit", r)
        r = git("push", "-u", "origin", branch, cwd=tmp)
        if r.returncode:
            return fail("push", r)

        # 6. PR + 自动 squash (repo 未启用 auto-merge 时挂起等人, 可接受降级)
        r = subprocess.run(
            ["gh", "pr", "create", "--base", "main", "--head", branch,
             "--title", title, "--body", body],
            capture_output=True, text=True, env=env, cwd=tmp,
        )
        if r.returncode:
            return fail("gh pr create", r)
        pr_url = r.stdout.strip().splitlines()[-1]
        print(f"✅ PR 已创建: {pr_url}")
        r = subprocess.run(
            ["gh", "pr", "merge", pr_url, "--squash", "--auto", "--delete-branch"],
            capture_output=True, text=True, env=env, cwd=tmp,
        )
        # auto-merge 未启用时 rc!=0: 分支已推远端不丢失, 降级挂起等人工, 不算失败
        if r.returncode == 0:
            print(f"✅ 已使能 auto-merge (squash): {pr_url}")
        else:
            print(f"⚠️  auto-merge 未生效 (repo 设置?), PR 挂起等人工: {pr_url}")
        return 0
    finally:
        # 7. 清理: worktree 强删 + 本地分支删 (远端分支归 gh --delete-branch 管)
        git("worktree", "remove", "--force", str(tmp), cwd=workspace)
        git("branch", "-D", branch, cwd=workspace)
        if pr_url:
            print(f"📌 本次发布记录: {pr_url}")
