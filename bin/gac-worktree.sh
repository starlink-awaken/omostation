#!/bin/bash
# gac-worktree.sh — GaC worktree per session (ADR-0106, P2, 多 agent 并行终态)
#
# 多 agent 并行的物理隔离: 每 session 独立 worktree + 分支, 各改各的, PR 合并.
# 治本 concurrent-agent-contention (共享工作树撞车 → worktree 隔离).
#
# 用法:
#   gac-worktree.sh claim <session>      # 创建 worktree + 分支 work/<session>
#   gac-worktree.sh submit <session>     # push 分支 + 开 PR (base main)
#   gac-worktree.sh release <session>    # 清理 worktree (合并后)
#   gac-worktree.sh list                 # 列所有 worktree
#
# 模式: 主仓 worktree (子模块共享, 简化). 子模块独立 worktree 后续.
# 对标: git worktree + PR 流程 (Linux kernel / Devin / Codex).

set -e

WS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$WS_ROOT" ]; then
  echo "❌ 不在 git 仓库" >&2
  exit 1
fi
WS_PARENT="$(dirname "$WS_ROOT")"

cmd="${1:-list}"
session="${2:-}"

case "$cmd" in
  claim)
    [ -z "$session" ] && echo "用法: claim <session>" >&2 && exit 1
    wt="$WS_PARENT/ws-$session"
    branch="work/$session"
    if [ -d "$wt" ]; then
      echo "⚠️  worktree 已存在: $wt (cd 过去继续工作)"
    else
      git worktree add "$wt" -b "$branch" 2>&1
      echo "✅ worktree 创建: $wt"
      echo "   分支: $branch (base: $(git rev-parse --abbrev-ref HEAD))"
      echo ""
      echo "   下一步:"
      echo "     cd $wt"
      echo "     # ... 工作 (改文件, commit) ..."
      echo "     gac-worktree.sh submit $session"
    fi
    ;;

  submit)
    [ -z "$session" ] && echo "用法: submit <session>" >&2 && exit 1
    wt="$WS_PARENT/ws-$session"
    branch="work/$session"
    if [ ! -d "$wt" ]; then
      echo "❌ worktree 不存在: $wt (先 claim)" >&2
      exit 1
    fi
    cd "$wt"
    # 提交未提交改动 (如有)
    if ! git diff --quiet || ! git diff --cached --quiet; then
      git add -A
      git commit -m "wip: $session worktree 提交" 2>&1 | tail -2
    fi
    # push 分支
    git push -u origin "$branch" 2>&1 | tail -3
    # 开 PR
    if command -v gh &>/dev/null; then
      gh pr create --base main --head "$branch" \
        --title "[$session] worktree 提交" \
        --body "GaC worktree per session (ADR-0106 P2). 自动生成 PR." 2>&1 | tail -2 \
        || echo "(PR 创建失败, 手动: gh pr create --base main --head $branch)"
    else
      echo "⚠️  gh 未装, 手动开 PR: base main <- $branch"
    fi
    echo "✅ submit: push $branch + PR"
    ;;

  release)
    [ -z "$session" ] && echo "用法: release <session>" >&2 && exit 1
    wt="$WS_PARENT/ws-$session"
    if [ ! -d "$wt" ]; then
      echo "⚠️  worktree 不存在: $wt (已释放?)"
      exit 0
    fi
    # 检查未提交
    cd "$wt"
    if ! git diff --quiet || ! git diff --cached --quiet; then
      echo "⚠️  worktree 有未提交改动, 先 submit 或 stash" >&2
      git status --short | head -5
      exit 1
    fi
    cd "$WS_ROOT"
    git worktree remove "$wt" 2>&1
    echo "✅ worktree 释放: $wt"
    echo "   分支 work/$session 保留 (合并后可删: git branch -D work/$session)"
    ;;

  list)
    echo "=== GaC worktree 列表 ==="
    git worktree list
    ;;

  *)
    echo "GaC worktree per session (ADR-0106 P2)"
    echo ""
    echo "用法: gac-worktree.sh {claim|submit|release|list} [session]"
    echo ""
    echo "  claim <session>      创建 worktree + 分支 work/<session>"
    echo "  submit <session>     push 分支 + 开 PR (base main)"
    echo "  release <session>    清理 worktree (合并后)"
    echo "  list                 列所有 worktree"
    exit 1
    ;;
esac
