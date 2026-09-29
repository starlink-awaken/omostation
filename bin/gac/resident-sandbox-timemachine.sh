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
#
# 2026-09-29: 原硬编码 5s 是 2026-09-07 的实测基线 (彼时仓更小)。如今本机 `git worktree add`
# 实测 6.6~8.0s (post-checkout 钩子会跑 guard-submodules), 5s 让**每一次**合法创建都熔断 ——
# 熔断器退化为恒失败, tests/integration/test-sandbox-timemachine.sh 因此长期红。
# 阈值改为可 env 覆盖, 默认放宽到仍能拦住「无界挂起」的量级: 熔断保护的是「git worktree add 卡死」,
# 不是性能验收门 (「秒级」是能力描述, 见 T10-133 设计文档; 验收条款里的 < 5s 同理是当时基线)。
SANDBOX_TIMEOUT_S="${SANDBOX_TIMEOUT_S:-30}"

usage() {
  sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

sandbox_path() {
  local session="$1"
  echo "$WS_PARENT/ws-sandbox-$session"
}

# 该路径是否仍作为 worktree 注册着 (目录可以已不存在 —— 即 prunable 幽灵注册)。
sandbox_registered() {
  git -C "$WS_ROOT" worktree list --porcelain 2>/dev/null | command grep -qxF "worktree $1"
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

  # 幽灵注册清理: 上次失败可能留下「已注册但目录已删」的 prunable 条目 ——
  # `[ -d "$wt" ]` 看不见它, 但 `git worktree add` 会因同名路径已注册而失败。
  # prune 只清失效注册 (目录已不存在), 幂等, 不动其它 worktree。
  git -C "$WS_ROOT" worktree prune >/dev/null 2>&1 || true

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
    # 超时熔断 = git 进程被 kill 在半途, 它此时持有 worktree 的 **lock**（`git worktree add`
    # 先 register+lock 再填充, 正常完成才 unlock）。locked 会让 `prune` 直接跳过 ⇒ 只做
    # rm+prune 会留下「已锁定 + 半成品」的更顽固残留（2026-09-29 实证: 失败后该路径仍在
    # `git worktree list` 里且标记 locked）。故逐级降级清理: unlock → remove --force → rm → prune。
    git -C "$WS_ROOT" worktree unlock "$wt" >/dev/null 2>&1 || true
    git -C "$WS_ROOT" worktree remove --force "$wt" >/dev/null 2>&1 || true
    rm -rf "$wt" 2>/dev/null || true
    git -C "$WS_ROOT" worktree prune >/dev/null 2>&1 || true
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

  # 判据用「目录 + worktree 注册」双查 —— 只看目录会把「目录已删但注册还在」的 prunable 幽灵
  # 误报成「无残留」(假绿; 且该注册会让后续同名 create 的 `worktree add` 直接失败)。
  if [ ! -d "$wt" ] && ! sandbox_registered "$wt"; then
    echo "✅ 无沙箱残留: $wt"
    return 0
  fi

  local from=""
  [ -f "$wt/.sandbox-from" ] && from="$(cat "$wt/.sandbox-from" 2>/dev/null || true)"

  # 硬性回滚: unlock → worktree remove --force (含未提交改动也删) → 目录级删除 → prune。
  # unlock 不可省: 创建被超时熔断 kill 的半成品沙箱带 lock, 而 `worktree remove` 与 `prune` 都跳过 locked。
  git -C "$WS_ROOT" worktree unlock "$wt" >/dev/null 2>&1 || true
  if git -C "$WS_ROOT" worktree remove --force "$wt" >/dev/null 2>&1; then
    git -C "$WS_ROOT" worktree prune
    echo "✅ 时光机回滚完成 (session=$session, from=$from)"
  else
    # 兜底: 目录级删除 (worktree 注册残留时)
    rm -rf "$wt" 2>/dev/null || true
    git -C "$WS_ROOT" worktree prune
    echo "⚠️ worktree remove 失败，已目录级兜底清理 (worktree 注册可能仍残留): $wt"
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
