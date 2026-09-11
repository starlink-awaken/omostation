#!/usr/bin/env bash
# 治本 D: 检测"本地领先远程"的子模块 — 防 CI 悬空 (WP1 Wave B2: verification-only).
#
# 病根: 自动化 agent (OMC/autopilot) 在子模块 commit + bump 主仓指针, 却不 push 子模块
#   → 主仓 gitlink 指向子模块远程没有的 commit → CI `submodules: recursive` 拉不到
#   → "not our ref" → 整条 CI 红. (2026-06-17 实测 14/18 子模块悬空)
#
# WP1 Wave B2: 本脚本只检测并报告未推 commit / 不可达状态，exit nonzero；
#   不再执行远程推送。实际发布由托管 clone-lifecycle integrate 承担。
#
# PASW 适配: 额外检测 .subtrees/ 内的未推 commit 并报告。
#
# 用法:
#   bin/sync-submodules-push.sh --dry-run   # 只看清单 (与默认相同)
#   bin/sync-submodules-push.sh             # 验证；有未推则 exit 1
set -uo pipefail

# 治本 followup C (2026-07-03): pre-push hook 跑时 git 设 GIT_DIR/GIT_WORK_TREE 指向主仓 worktree,
# 泄漏到 `git -C "$sm"` → 读主仓分支(非子模块). unset 后 git -C "$sm" 读子模块自己的 .git.
unset GIT_DIR GIT_WORK_TREE 2>/dev/null || true

cd "$(git rev-parse --show-toplevel)" || { echo "❌ 不在 git 仓"; exit 1; }

dry=0
[ "${1:-}" = "--dry-run" ] && dry=1

pending=0; noupstream=0; missing=0; failed=0

while IFS= read -r sm; do
  [ -z "$sm" ] && continue
  if [ ! -d "$sm/.git" ] && [ ! -f "$sm/.git" ]; then
    # Phase 2a (2026-06-30): worktree 按需 init 子模块是合法的.
    missing=$(( missing + 1 )) || true
    echo "⏭ $sm: 子模块未初始化 (worktree 按需 init 合法), 跳过"
    continue
  fi

  branch=$(git -C "$sm" rev-parse --abbrev-ref HEAD 2>/dev/null) || {
    failed=$(( failed + 1 )) || true
    echo "❌ $sm: 无法读取当前分支"
    continue
  }

  # Phase 2d ISC-3g (2026-07-03): detached HEAD 无 branch tracking → 跳过.
  if [ "$branch" = "HEAD" ]; then
    missing=$(( missing + 1 )) || true
    echo "⏭ $sm: detached HEAD (worktree --init, 无 branch tracking), 跳过 — reachability 由 submodule-reachability-gate 兜底"
    continue
  fi

  # 子模块有上游吗；没有 upstream 时回退到 origin/<当前分支>.
  upstream=$(git -C "$sm" rev-parse --abbrev-ref '@{u}' 2>/dev/null) || {
    if git -C "$sm" show-ref --verify --quiet "refs/remotes/origin/$branch"; then
      upstream="origin/$branch"
      echo "ℹ $sm: 无 upstream, 使用 $upstream 做未推检测"
    else
      : $(( noupstream = noupstream + 1 ))
      : $(( failed = failed + 1 ))
      echo "❌ $sm: 无 upstream, 且 origin/$branch 不存在; 请先配置上游或经托管交付事务发布"
      continue
    fi
  }
  # 本地领先远程多少 (未推 commit)
  cnt=$(git -C "$sm" log --oneline "${upstream}..HEAD" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$cnt" -gt 0 ]; then
    pending=$(( pending + 1 )) || true
    echo "⬆ $sm: $cnt 个未推 → origin/$branch (verification-only; 不 push)"
  fi
done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')

echo "---"
echo "统计: 待push=$pending 失败=$failed 无上游=$noupstream 缺失=$missing (dry-run=$dry, verification-only)"

# ── PASW: 检测 .subtrees/ 隔离 worktree 内的未推 commit ────────────────
PASW_ISOLATED="projects/knowledge/gbrain projects/cockpit projects/agora"
for sub in $PASW_ISOLATED; do
  sub_name=$(basename "$sub")
  sub_wt=".subtrees/$sub_name"
  [ -d "$sub_wt" ] || continue
  [ -e "$sub_wt/.git" ] || continue

  wt_branch=$(git -C "$sub_wt" rev-parse --abbrev-ref HEAD 2>/dev/null) || continue
  [ "$wt_branch" = "HEAD" ] && continue  # detached, skip

  # 检查 remote tracking
  wt_upstream=$(git -C "$sub_wt" rev-parse --abbrev-ref '@{u}' 2>/dev/null) || {
    if git -C "$sub_wt" show-ref --verify --quiet "refs/remotes/origin/$wt_branch"; then
      wt_upstream="origin/$wt_branch"
    else
      continue
    fi
  }

  wt_cnt=$(git -C "$sub_wt" log --oneline "${wt_upstream}..HEAD" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$wt_cnt" -gt 0 ]; then
    pending=$(( pending + 1 )) || true
    echo "⬆ PASW $sub_wt: $wt_cnt 个未推 → origin/$wt_branch (verification-only; 不 push)"
  fi
done

if [ "$failed" -gt 0 ] || [ "$pending" -gt 0 ]; then
  echo "❌ 子模块验证失败: pending=$pending failed=$failed (无自动 push)"
  exit 1
fi
exit 0
