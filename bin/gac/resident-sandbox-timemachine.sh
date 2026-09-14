#!/usr/bin/env bash
# resident-sandbox-timemachine.sh — Git Worktree 物理沙箱 + 时光机回滚 (BET-Y1Q4-T10-133)
#
# 为持久化 Agent 的高危/未知探索任务提供秒级建立的隔离 worktree 物理沙箱。
# 沙箱内试错失败 → 硬性时光机回滚自毁 (worktree remove --force + 删分支)，
# 绝对防止主工作区受污染。
#
# 用法:
#   bash bin/gac/resident-sandbox-timemachine.sh --help
#   bash bin/gac/resident-sandbox-timemachine.sh create <session> [--from <commit>]
#   bash bin/gac/resident-sandbox-timemachine.sh run <session> -- <cmd...>
#   bash bin/gac/resident-sandbox-timemachine.sh rollback <session>
#
# 硬约束: 沙箱内禁止 git push / merge 到 main — 命令串校验，命中即拦截 (FAIL)。

set -euo pipefail

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WS_PARENT="$(dirname "$WS_ROOT")"

# circuit_breaker: 沙箱创建超时 (秒)
SANDBOX_TIMEOUT_S=5

usage() {
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

sandbox_path() {
  local session="$1"
  echo "$WS_PARENT/ws-sandbox-$session"
}

# create <session> [--from <commit>] — 秒级创建隔离沙箱 worktree
cmd_create() {
  local session="$1" from="${2:-HEAD}"
  local wt
  wt="$(sandbox_path "$session")"

  if [ -d "$wt" ]; then
    echo "❌ 沙箱已存在: $wt" >&2
    return 1
  fi

  local branch="sandbox/$session"
  local start_ms end_ms elapsed_ms
  start_ms=$(python3 -c 'import time; print(int(time.time()*1000))')

  # 秒级创建: 基于 --from commit（默认当前 HEAD），--detach 避免分支名冲突
  # macOS 无 GNU timeout — 用 python3 子进程 + 超时 (circuit_breaker)
  if ! WS_ROOT="$WS_ROOT" python3 - "$wt" "$from" "$SANDBOX_TIMEOUT_S" <<'PYEOF' >/dev/null 2>&1
import os, subprocess, sys
wt, from_ref, timeout_s = sys.argv[1], sys.argv[2], int(sys.argv[3])
root = os.environ["WS_ROOT"]
try:
    res = subprocess.run(
        ["git", "-C", root, "worktree", "add", "--detach", wt, from_ref],
        capture_output=True, text=True, timeout=timeout_s,
    )
    sys.exit(res.returncode)
except subprocess.TimeoutExpired:
    sys.exit(124)  # 超时码 (对应 GNU timeout)
PYEOF
  then
    echo "❌ 沙箱创建超时或失败 (> ${SANDBOX_TIMEOUT_S}s, circuit_breaker): $wt" >&2
    rm -rf "$wt" 2>/dev/null || true
    return 1
  fi

  end_ms=$(python3 -c 'import time; print(int(time.time()*1000))')
  elapsed_ms=$((end_ms - start_ms))

  # 记录来源 commit（rollback 后报告用）
  echo "$from" > "$wt/.sandbox-from" 2>/dev/null || true

  echo "✅ 沙箱创建: $wt (${elapsed_ms}ms, from=$from, detach)"
}

# run <session> -- <cmd...> — 在沙箱 worktree 内执行命令
cmd_run() {
  local session="$1"
  shift
  [ "$1" = "--" ] && shift
  local wt
  wt="$(sandbox_path "$session")"

  if [ ! -d "$wt" ]; then
    echo "❌ 沙箱不存在: $wt (先 create)" >&2
    return 1
  fi

  # 硬约束: 禁止 push/merge 到 main
  local joined
  joined="$*"
  if [[ "$joined" == *"git push"* || "$joined" == *"git merge"* || "$joined" == *"git rebase"* ]]; then
    echo "❌ 沙箱硬约束: 禁止 push/merge/rebase (命令串拦截)" >&2
    return 2
  fi

  echo "▶ 沙箱执行 (cwd=$wt): $*"
  (cd "$wt" && eval "$*")
  return $?
}

# rollback <session> — 时光机回滚自毁 (worktree remove --force + 清理)
cmd_rollback() {
  local session="$1"
  local wt
  wt="$(sandbox_path "$session")"

  if [ ! -d "$wt" ]; then
    echo "✅ 无沙箱残留: $wt"
    return 0
  fi

  local from=""
  [ -f "$wt/.sandbox-from" ] && from="$(cat "$wt/.sandbox-from" 2>/dev/null || true)"

  # 硬性回滚: worktree remove --force (含未提交改动也删) + prune
  if git -C "$WS_ROOT" worktree remove --force "$wt" >/dev/null 2>&1; then
    git -C "$WS_ROOT" worktree prune
    echo "✅ 时光机回滚完成 (session=$session, from=$from)"
  else
    # 兜底: 目录级删除 (worktree 注册残留时)
    rm -rf "$wt" 2>/dev/null || true
    git -C "$WS_ROOT" worktree prune
    echo "⚠️ worktree remove 失败，已目录级兜底清理: $wt"
  fi
}

main() {
  local cmd="${1:-help}"
  shift || true

  case "$cmd" in
    create)
      [ $# -ge 1 ] || { usage; return 1; }
      cmd_create "$1" "${2:-HEAD}"
      ;;
    run)
      [ $# -ge 2 ] || { usage; return 1; }
      cmd_run "$@"
      ;;
    rollback)
      [ $# -ge 1 ] || { usage; return 1; }
      cmd_rollback "$1"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      usage
      return 1
      ;;
  esac
}

main "$@"
