#!/usr/bin/env bash
# 治本 D: 同步"本地领先远程"的子模块 — 防 CI 悬空.
#
# 病根: 自动化 agent (OMC/autopilot) 在子模块 commit + bump 主仓指针, 却不 push 子模块
#   → 主仓 gitlink 指向子模块远程没有的 commit → CI `submodules: recursive` 拉不到
#   → "not our ref" → 整条 CI 红. (2026-06-17 实测 14/18 子模块悬空)
#
# 治本: 检测每个子模块"未推 commit"(@{u}..HEAD 非空), push 到各自 origin, 让 gitlink 可达.
# 注入点: 主仓 .git/hooks/pre-push 调用本脚本 → 主仓 push(触发 CI)前先补齐子模块.
#
# PASW 适配: 高冲突子模块 (gbrain/cockpit/agora) 的 commit 在 .subtrees/ 隔离 worktree 内,
# 共享 projects/<sub>/ 保持在原 gitlink commit (detached HEAD). 本脚本额外检测 .subtrees/ 内的
# 未推 commit 并 push, 确保 bump-pointer 后的 SHA 在子模块 remote 上可达.
#
# 用法:
#   bin/sync-submodules-push.sh --dry-run   # 只看清单, 不 push
#   bin/sync-submodules-push.sh             # 真同步
#   bin/sync-submodules-push.sh --pull      # pull stale + push unpushed (治本 E)
set -uo pipefail

# 治本 followup C (2026-07-03): pre-push hook 跑时 git 设 GIT_DIR/GIT_WORK_TREE 指向主仓 worktree,
# 泄漏到 `git -C "$sm"` → 读主仓分支(非子模块, 实测报 branch=work/<session>) → 子模块全判"无上游"拦 push.
# unset 后 git -C "$sm" 读子模块自己的 .git (正确). cd 用 cwd 的 worktree .git (hook cwd=发起push的worktree).
unset GIT_DIR GIT_WORK_TREE 2>/dev/null || true

cd "$(git rev-parse --show-toplevel)" || { echo "❌ 不在 git 仓"; exit 1; }

dry=0
pull=0
[ "${1:-}" = "--dry-run" ] && dry=1
[ "${1:-}" = "--pull" ] && pull=1
[ "${2:-}" = "--pull" ] && pull=1

pushed=0; pulled=0; pending=0; noupstream=0; missing=0; failed=0

# PASW 高冲突子模块 (ADR-0371): 由 bump-pointer 管理，不自动 pull
PASW_SUBS="projects/gbrain projects/cockpit projects/agora"
is_pasw() {
  for p in $PASW_SUBS; do
    [ "$1" = "$p" ] && return 0
  done
  return 1
}

while IFS= read -r sm; do
  [ -z "$sm" ] && continue
  if [ ! -d "$sm/.git" ] && [ ! -f "$sm/.git" ]; then
    # Phase 2a (2026-06-30): worktree 按需 init 子模块是合法的 (主仓文件改动不涉子模块).
    # 未 init 无"领先"可言, 跳过 (不计 failed). gitlink 可达性由 submodule-reachability-gate 单独管.
    missing=$(( missing + 1 )) || true
    echo "⏭ $sm: 子模块未初始化 (worktree 按需 init 合法), 跳过"
    continue
  fi

  branch=$(git -C "$sm" rev-parse --abbrev-ref HEAD 2>/dev/null) || {
    failed=$(( failed + 1 )) || true
    echo "❌ $sm: 无法读取当前分支"
    continue
  }

  # Phase 2d ISC-3g (2026-07-03): detached HEAD (worktree --init 产生) 无 branch tracking.
  # worktree 子模块 checkout 到主仓 gitlink commit (可达), 不在 branch 上开发 = 无本地领先 commit.
  # 跳过 sync (不计 failed); gitlink 可达性由 submodule-reachability-gate 兜底 (pre-push 独立跑).
  # 区分真未推 (agent 在子模块 branch 上 commit 未 push): 那种 branch != HEAD, 走下面正常逻辑.
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
      # 用 : $(( ... )) 避免 $((0+1))=1 触发 set -e (bash $((expr)) expr=0 返回 1 经典陷阱)
      : $(( noupstream = noupstream + 1 ))
      : $(( failed = failed + 1 ))
      echo "❌ $sm: 无 upstream, 且 origin/$branch 不存在; 请先配置上游或手动 push"
      continue
    fi
  }
  # 本地领先远程多少 (未推 commit)
  cnt=$(git -C "$sm" log --oneline "${upstream}..HEAD" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$cnt" -gt 0 ]; then
    pending=$(( pending + 1 )) || true
    echo "⬆ $sm: $cnt 个未推 → origin/$branch"
    if [ "$dry" = "0" ]; then
      # 跳过子模块 pre-push hook：子模块 gate 已在 commit 时跑过，
      # 本地 pre-push 再跑 e2e/integration 容易挂死，导致根仓库 push 阻塞。
      if git -C "$sm" push --no-verify origin "$branch" >/dev/null 2>&1; then
        pushed=$(( pushed + 1 )) || true; echo "  ✅ pushed"
      else
        failed=$(( failed + 1 )) || true; echo "  ❌ push 失败 (认证/冲突?)"
      fi
    fi
  fi

  # 治本 E (2026-08-08): --pull 模式下检测 stale 子模块并自动 pull
  if [ "$pull" = "1" ]; then
    if is_pasw "$sm"; then
      echo "⏭ $sm: PASW 子模块, 跳过 auto-pull (由 bump-pointer 管理)"
    else
      behind_cnt=$(git -C "$sm" log --oneline "HEAD..${upstream}" 2>/dev/null | wc -l | tr -d ' ')
      if [ "$behind_cnt" -gt 0 ]; then
        echo "⬇ $sm: $behind_cnt 个过期 ← $upstream"
        if [ "$dry" = "0" ]; then
          if git -C "$sm" checkout main >/dev/null 2>&1 && git -C "$sm" pull --quiet origin main >/dev/null 2>&1; then
            pulled=$(( pulled + 1 )) || true; echo "  ✅ pulled"
          else
            failed=$(( failed + 1 )) || true; echo "  ❌ pull 失败 (冲突?)"
          fi
        fi
      fi
    fi
  fi
done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')

echo "---"
echo "统计: 待push=$pending 已push=$pushed 已pull=$pulled 失败=$failed 无上游=$noupstream 缺失=$missing (dry-run=$dry)"

# ── PASW: 检测 .subtrees/ 隔离 worktree 内的未推 commit ────────────────
# PASW 隔离子模块的实际 commit 在 .subtrees/<sub>/ 内, 共享 projects/<sub>/ 保持原状.
# 本段检测 .subtrees/ 内的未推 commit 并 push, 确保 bump-pointer 后的 SHA 可达.
PASW_ISOLATED="projects/gbrain projects/cockpit projects/agora"
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
    echo "⬆ PASW $sub_wt: $wt_cnt 个未推 → origin/$wt_branch"
    if [ "$dry" = "0" ]; then
      if git -C "$sub_wt" push --no-verify origin "$wt_branch" >/dev/null 2>&1; then
        pushed=$(( pushed + 1 )) || true
        echo "  ✅ pushed"
      else
        failed=$(( failed + 1 )) || true
        echo "  ❌ push 失败"
      fi
    fi
  fi
done

[ "$failed" -gt 0 ] && exit 1
exit 0
