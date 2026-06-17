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

pushed=0; pending=0; noupstream=0; failed=0

while IFS= read -r sm; do
  [ -z "$sm" ] && continue
  # 子模块有上游吗
  upstream=$(git -C "$sm" rev-parse --abbrev-ref '@{u}' 2>/dev/null) || { noupstream=$((noupstream+1)); continue; }
  # 本地领先远程多少 (未推 commit)
  cnt=$(git -C "$sm" log --oneline "${upstream}..HEAD" 2>/dev/null | wc -l | tr -d ' ')
  if [ "$cnt" -gt 0 ]; then
    pending=$((pending+1))
    branch=$(git -C "$sm" rev-parse --abbrev-ref HEAD)
    echo "⬆ $sm: $cnt 个未推 → origin/$branch"
    if [ "$dry" = "0" ]; then
      if git -C "$sm" push origin "$branch" >/dev/null 2>&1; then
        pushed=$((pushed+1)); echo "  ✅ pushed"
      else
        failed=$((failed+1)); echo "  ❌ push 失败 (认证/冲突?)"
      fi
    fi
  fi
done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')

echo "---"
echo "统计: 待push=$pending 成功=$pushed 失败=$failed 无上游跳过=$noupstream (dry-run=$dry)"
[ "$failed" -gt 0 ] && exit 1
exit 0
