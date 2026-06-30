#!/bin/bash
# gac-worktree.sh — GaC worktree per session (ADR-0106, P2, 多 agent 并行终态)
#
# 多 agent 并行的物理隔离: 每 session 独立 worktree + 分支, 各改各的, PR 合并.
# 治本 concurrent-agent-contention (共享工作树撞车 → worktree 隔离).
#
# 用法:
#   gac-worktree.sh claim <session>      # 创建 worktree + 分支 work/<session>
#   gac-worktree.sh submit <session>     # push 分支 + 开 PR (base main)
#   gac-worktree.sh merge <session>      # squash 合并 PR + release worktree + 删分支
#   gac-worktree.sh release <session>    # 清理 worktree (手动, 合并后)
#   gac-worktree.sh list                 # 列所有 worktree
#
# session 命名: 只允许 [a-z0-9-] (防 git 分支非法字符), 如 "fix-route-bug".
# 模式: 主仓 worktree (子模块共享). 子模块撞车则需独立 worktree (Phase 1 验证后定).
# 对标: git worktree + PR 流程 (Linux kernel / Devin / Codex).
# 落地计划: docs/AGENT-ISOLATION-ROLLOUT.md (Phase 1).

set -e

WS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$WS_ROOT" ]; then
  echo "❌ 不在 git 仓库" >&2
  exit 1
fi
WS_PARENT="$(dirname "$WS_ROOT")"

cmd="${1:-list}"
session="${2:-}"

# session 名只允许小写字母/数字/连字符 (防 work/<session> 含 git 分支非法字符)
validate_session() {
  local s="$1"
  if ! printf '%s' "$s" | grep -qE '^[a-z0-9][a-z0-9-]*$'; then
    echo "❌ session 名非法: '$s' (只允许 [a-z0-9-], 首字符须字母/数字)" >&2
    exit 1
  fi
}

case "$cmd" in
  claim)
    [ -z "$session" ] && echo "用法: claim <session>" >&2 && exit 1
    validate_session "$session"
    wt="$WS_PARENT/ws-$session"
    branch="work/$session"
    # 分支已存在但 worktree 缺失 → 残留/重名, 提示清理 (防 claim 撞残留分支)
    if git show-ref --verify --quiet "refs/heads/$branch" 2>/dev/null && [ ! -d "$wt" ]; then
      echo "⚠️  分支 $branch 已存在但 worktree 缺失 (残留? 清理: git branch -D $branch)" >&2
      exit 1
    fi
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
      echo "     # 改子模块先 init: git submodule update --init <submodule>"
      echo "     gac-worktree.sh submit $session"
    fi
    ;;

  submit)
    [ -z "$session" ] && echo "用法: submit <session>" >&2 && exit 1
    validate_session "$session"
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
    validate_session "$session"
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

  merge)
    # Phase 2a-3: PR 合并 + release + 删分支 (补全 PR 闭环: claim→submit→merge)
    # L0 萃取在 worktree commit 时已触发 (post-commit commit 级, worktree 共享 .git/hooks),
    # 派生文件进 PR. squash merge 到 main 后无需重跑 (ISC-3c).
    [ -z "$session" ] && echo "用法: merge <session>" >&2 && exit 1
    validate_session "$session"
    wt="$WS_PARENT/ws-$session"
    branch="work/$session"
    if [ ! -d "$wt" ]; then
      echo "❌ worktree 不存在: $wt (先 claim + submit)" >&2
      exit 1
    fi
    # worktree 必须已 submit (push + 开 PR). 有未提交 → 提示先 submit.
    cd "$wt"
    if ! git diff --quiet || ! git diff --cached --quiet; then
      echo "⚠️  worktree 有未提交改动, 先 submit" >&2
      git status --short | head -5
      exit 1
    fi
    cd "$WS_ROOT"
    # gh 必备
    if ! command -v gh &>/dev/null; then
      echo "❌ gh 未装, 手动: gh pr merge --squash --head $branch --delete-branch" >&2
      exit 1
    fi
    # 查 PR (head work/<session>, base main, open)
    pr_number=$(gh pr list --head "$branch" --base main --state open --json number 2>/dev/null \
      | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['number'] if d else '')" 2>/dev/null)
    if [ -z "$pr_number" ]; then
      echo "❌ 未找到 open PR (head=$branch base=main). 先 submit 开 PR." >&2
      exit 1
    fi
    echo "🔗 合并 PR #$pr_number ($branch → main, squash)..."
    # squash merge + 删远程分支. 失败即停 (冲突/constraint 失败等).
    if ! gh pr merge "$pr_number" --squash --delete-branch 2>&1; then
      echo "❌ PR #$pr_number 合并失败 (可能冲突或 CI 未过)" >&2
      exit 1
    fi
    echo "✅ PR #$pr_number 已 squash 合并"
    # 主仓切 main + 拉最新 (含刚合并的)
    git checkout main 2>&1 | tail -1
    git pull --ff-only origin main 2>&1 | tail -2
    # 释放 worktree (clean, 因 submit 已 push 全部)
    git worktree remove "$wt" 2>&1
    echo "✅ worktree 释放: $wt"
    # 删本地分支 (远程已 --delete-branch)
    git branch -D "$branch" 2>&1 | tail -1
    echo ""
    echo "🎉 merge 完成: PR #$pr_number → main, worktree + 分支已清理"
    ;;

  list)
    echo "=== GaC worktree 列表 ==="
    git worktree list
    ;;

  *)
    echo "GaC worktree per session (ADR-0106 P2)"
    echo ""
    echo "用法: gac-worktree.sh {claim|submit|merge|release|list} [session]"
    echo ""
    echo "  claim <session>      创建 worktree + 分支 work/<session>"
    echo "  submit <session>     push 分支 + 开 PR (base main)"
    echo "  merge <session>      squash 合并 PR + release worktree + 删分支"
    echo "  release <session>    清理 worktree (手动, 合并后)"
    echo "  list                 列所有 worktree"
    echo ""
    echo "session 命名: 只允许 [a-z0-9-] (如 fix-route-bug)"
    exit 1
    ;;
esac
