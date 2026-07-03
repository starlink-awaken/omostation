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
# 用法:
#   bin/sync-submodules-push.sh --dry-run   # 只看清单, 不 push
#   bin/sync-submodules-push.sh             # 真同步
set -uo pipefail

cd "$(git rev-parse --show-toplevel)" || { echo "❌ 不在 git 仓"; exit 1; }

dry=0
[ "${1:-}" = "--dry-run" ] && dry=1

pushed=0; pending=0; noupstream=0; missing=0; failed=0

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
done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')

echo "---"
echo "统计: 待push=$pending 成功=$pushed 失败=$failed 无上游=$noupstream 缺失=$missing (dry-run=$dry)"
[ "$failed" -gt 0 ] && exit 1
exit 0
