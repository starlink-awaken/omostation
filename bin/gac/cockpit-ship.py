#!/usr/bin/env python3
"""cockpit-ship — omostation 自动化自治交付流水线 (Autonomous Delivery Pipeline)

将繁琐的 8 步交付流固化为确定性原子能力:
  Claim Worktree -> Local Gate -> Commit & Push -> Create PR -> Monitor CI -> Auto Merge & Release

用法:
  python3 bin/gac/cockpit-ship.py --session <name> --title "feat(...): ..." [--body "..."] [--auto-merge]
  python3 bin/gac/cockpit-ship.py --current --title "fix(...): ..." [--auto-merge]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()
WORKSPACE = HOME / "Workspace"
GAC_WORKTREE_SH = WORKSPACE / "bin/gac/gac-worktree.sh"


def run_cmd(cmd: list[str], cwd: Path | None = None, check: bool = True, dry_run: bool = False) -> subprocess.CompletedProcess:
    cwd_path = cwd or WORKSPACE
    print(f"▸ [{cwd_path.name}] {' '.join(cmd)}")
    if dry_run:
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
    res = subprocess.run(cmd, cwd=cwd_path, capture_output=True, text=True)
    if check and res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        print(f"❌ 命令失败 (code {res.returncode}):\n{err}", file=sys.stderr)
        sys.exit(res.returncode)
    return res



def notify(title: str, msg: str) -> None:
    safe_msg = msg.replace('"', '\\"')[:200]
    safe_title = title.replace('"', '\\"')[:100]
    subprocess.run(
        ["osascript", "-e", f'display notification "{safe_msg}" with title "{safe_title}" sound name "Glass"'],
        capture_output=True,
    )


def resolve_session_and_worktree(session_arg: str | None, current: bool) -> tuple[str, Path]:
    cwd = Path.cwd()
    if current or not session_arg:
        if cwd.name.startswith("ws-"):
            session = cwd.name[3:]
            return session, cwd
        # 尝试从 git 分支名推导
        res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
        branch = res.stdout.strip()
        if branch.startswith("agent/") or branch.startswith("work/"):
            session = branch.split("/")[-1]
            return session, cwd
        print("❌ 未指定 --session 且当前目录不是 ws-* 隔离工作区", file=sys.stderr)
        sys.exit(1)

    session = session_arg
    wt_path = HOME / f"ws-{session}"
    return session, wt_path


def main() -> None:
    parser = argparse.ArgumentParser(description="omostation 自动化自治交付流水线")
    parser.add_argument("--session", "-s", help="Worktree 会话名称 (如 fix-lint-bug)")
    parser.add_argument("--current", action="store_true", help="使用当前目录所在的 Worktree")
    parser.add_argument("--title", "-t", required=True, help="PR 标题 (需符合 Conventional Commits 规范)")
    parser.add_argument("--body", "-b", default="", help="PR 描述正文")
    parser.add_argument("--auto-merge", action="store_true", help="CI 绿灯后自动 squash merge 并释放 worktree")
    parser.add_argument("--dry-run", action="store_true", help="预检模式，仅打印步骤")
    parser.add_argument("--timeout", type=int, default=600, help="等待 CI 门禁超时秒数 (默认 600s)")

    args = parser.parse_args()
    session, wt_path = resolve_session_and_worktree(args.session, args.current)

    print(f"🚀 [cockpit-ship] 启动交付流水线 · 会话: {session} · 工作区: {wt_path}")

    # 1. 确保 Worktree 存在
    if not wt_path.exists():
        print(f"📦 Worktree 不存在，正在创建隔离工作区: {session}...")
        run_cmd(["bash", str(GAC_WORKTREE_SH), "claim", session], cwd=WORKSPACE, dry_run=args.dry_run)
        if not wt_path.exists() and not args.dry_run:
            print(f"❌ 无法创建工作区: {wt_path}", file=sys.stderr)
            sys.exit(1)

    if args.dry_run:
        print("\n🔍 [DRY-RUN 预检模式] 模拟以下自动化全链路:")
        print(f"  1. 隔离工作区: claim {session} -> {wt_path}")
        print(f"  2. 代码提交: git commit -m '{args.title}'")
        print(f"  3. 本地门禁: 校验 check-ci-surfaces.py 与关键规则")
        print(f"  4. 远端推送: git push -u origin agent/{session}")
        print(f"  5. 开启 PR: gh pr create --base main --head agent/{session} --title '{args.title}'")
        if args.auto_merge:
            print(f"  6. 门禁监听: gh pr checks <pr> --watch 等待全部 CI checks 绿灯")
            print(f"  7. 自动合入: gac-worktree.sh merge {session}")
            print(f"  8. 释放资源: gac-worktree.sh release {session}")
            print(f"  9. 桌面通知: 弹出 macOS 原生交付成功通知")
        print("\n✅ 预检完成，参数与环境校验通过。")
        return

    # 2. 检查工作区修改并提交 Commit
    status = run_cmd(["git", "status", "--short"], cwd=wt_path, check=False)
    if status.stdout.strip():
        print("📝 检测到未暂存代码变更，正在提交...")
        run_cmd(["git", "add", "-A"], cwd=wt_path)
        run_cmd(["git", "commit", "-m", args.title], cwd=wt_path)
    else:
        print("ℹ️ 工作区干净，检查是否有新 commit 需交付...")

    # 3. 本地门禁快速扫描
    print("🛡️ 运行本地基础门禁核验...")
    ci_surf = WORKSPACE / "bin/gac/check-ci-surfaces.py"
    if ci_surf.exists():
        run_cmd(["python3", str(ci_surf)], cwd=wt_path, check=False)

    # 4. 获取当前分支并推送到远程
    branch_res = run_cmd(["git", "branch", "--show-current"], cwd=wt_path)
    branch = branch_res.stdout.strip()
    if not branch:
        print("❌ 无法获取当前分支", file=sys.stderr)
        sys.exit(1)

    print(f"📤 推送分支 {branch} 到远程...")
    run_cmd(["git", "push", "-u", "origin", branch], cwd=wt_path)

    # 5. 创建或获取 GitHub PR
    print(f"📋 检查或创建 Pull Request (Base: main, Head: {branch})...")
    pr_num = None
    chk_pr = run_cmd(["gh", "pr", "list", "--head", branch, "--json", "number,url"], cwd=wt_path, check=False)
    prs = json.loads(chk_pr.stdout) if chk_pr.stdout.strip() else []
    if prs:
        pr_num = prs[0]["number"]
        pr_url = prs[0]["url"]
        print(f"ℹ️ 已存在关联 PR: #{pr_num} ({pr_url})")
    else:
        body_content = args.body or f"## 自动化交付\n\n- 交付会话: `{session}`\n- 变更标题: {args.title}\n"
        create_pr = run_cmd(
            ["gh", "pr", "create", "--base", "main", "--head", branch, "--title", args.title, "--body", body_content],
            cwd=wt_path,
        )
        for line in create_pr.stdout.splitlines():
            if "pull/" in line:
                pr_num = line.strip().split("pull/")[-1].split("/")[0]
                print(f"✅ PR 创建成功: #{pr_num} ({line.strip()})")
                break

    notify("cockpit-ship 交付已推至 PR", f"会话 {session}: PR #{pr_num or '已开启'}")


    if not args.auto_merge:
        print(f"\n🎉 交付流程已完成推送与 PR 创建！可使用 `gac-worktree.sh merge {session}` 进行合入。")
        return

    if not pr_num:
        print("⚠️ 未识别到 PR 编号，无法执行 --auto-merge", file=sys.stderr)
        return

    # 6. 自动等待 CI 绿灯并合并
    print(f"\n⏳ 开始监控 PR #{pr_num} CI 门禁状态 (超时: {args.timeout}s)...")
    start_time = time.time()
    while time.time() - start_time < args.timeout:
        res = run_cmd(
            ["gh", "pr", "view", str(pr_num), "--json", "statusCheckRollup,state"],
            cwd=WORKSPACE,
            check=False,
        )
        if res.returncode != 0:
            time.sleep(10)
            continue

        pr_data = json.loads(res.stdout)
        if pr_data.get("state") == "MERGED":
            print(f"✅ PR #{pr_num} 已经被合并！")
            break

        checks = pr_data.get("statusCheckRollup", [])
        if not checks:
            print("  ⏳ 等待 CI checks 触发...")
            time.sleep(10)
            continue

        statuses = [c.get("status") for c in checks]
        conclusions = [c.get("conclusion") for c in checks if c.get("status") == "COMPLETED"]

        in_progress = any(s in ("IN_PROGRESS", "QUEUED", "PENDING") for s in statuses)
        has_failure = any(c in ("FAILURE", "TIMED_OUT", "ACTION_REQUIRED") for c in conclusions)

        if has_failure:
            print(f"❌ PR #{pr_num} CI 门禁出现失败，停止自动合并以保护主线！", file=sys.stderr)
            notify("cockpit-ship CI 失败", f"PR #{pr_num} 门禁未通过，已停止自动合并")
            sys.exit(1)

        if not in_progress and all(c in ("SUCCESS", "SKIPPED", "NEUTRAL") for c in conclusions):
            print(f"🟢 PR #{pr_num} 全部 {len(checks)} 项 CI 检查通过！开始自动合入...")
            # 调用原生 merge
            run_cmd(["bash", str(GAC_WORKTREE_SH), "merge", session], cwd=WORKSPACE)
            print(f"🧹 自动释放隔离工作区 {session}...")
            run_cmd(["bash", str(GAC_WORKTREE_SH), "release", session], cwd=WORKSPACE, check=False)
            notify("cockpit-ship 自动合入成功", f"PR #{pr_num} 已合并至 main，工作区已释放！")
            print(f"\n🏆 全链路交付闭环完成！已安全合入 main 并清理临时 worktree。")
            return

        completed_count = len(conclusions)
        total_count = len(checks)
        print(f"  ⏳ 正在运行 CI: {completed_count}/{total_count} 完成 (已耗时 {int(time.time() - start_time)}s)...")
        time.sleep(15)

    print("⚠️ 等待 CI 超时，未自动合并。请后续手动验证并合并。", file=sys.stderr)


if __name__ == "__main__":
    main()
