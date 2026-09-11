#!/bin/bash
# 机制 20 (2026-09-06, BET-Y1Q4-T10-131): git 操作自动重试
# WP1 Wave B2: push 动词在执行 Git 前硬拒绝 (PUBLICATION_OWNER_REQUIRED)
#
# 使用:
#   bash bin/gac/git-retry.sh fetch --prune origin
#   bash bin/gac/git-retry.sh ls-remote origin HEAD
#   bash bin/gac/git-retry.sh pull --rebase origin main
#
# 行为:
#   - push 立即拒绝并打印 PUBLICATION_OWNER_REQUIRED (不执行 git)
#   - 最多重试 3 次，递增延迟 (5s, 10s, 20s)
#   - 仅对网络相关错误重试 (SSL_connect, timeout, connection refused 等)
#   - 非网络错误立即失败

set -euo pipefail

MAX_RETRIES=3
RETRY_DELAYS=(5 10 20)

# 网络错误关键词
NETWORK_ERRORS=(
  "SSL_connect"
  "SSL_ERROR_SYSCALL"
  "HTTP/2"
  "connection refused"
  "Connection reset"
  "timeout"
  "Temporary failure"
  "Could not resolve"
  "early EOF"
  "unexpected disconnect"
  "Operation not permitted"
  "Connection timed out"
)

is_network_error() {
  local output="$1"
  for err in "${NETWORK_ERRORS[@]}"; do
    if printf '%s' "$output" | grep -qi "$err"; then
      return 0
    fi
  done
  return 1
}

show_help() {
  cat << 'EOF'
用法: bash bin/gac/git-retry.sh <git-cmd> [args...]

示例:
  bash bin/gac/git-retry.sh fetch --prune origin
  bash bin/gac/git-retry.sh ls-remote origin HEAD
  bash bin/gac/git-retry.sh pull --rebase origin main

行为:
  - push 动词拒绝: PUBLICATION_OWNER_REQUIRED (不执行 Git)
  - 网络错误自动重试 (最多 3 次, 递增延迟)
  - 非网络错误立即失败，不重试

环境变量:
  GIT_RETRY_MAX    最大重试次数 (默认 3)
  GIT_RETRY_DELAY  初始延迟秒数 (默认 5)
EOF
}

if [ $# -eq 0 ]; then
  show_help
  exit 1
fi

# --help 支持
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
  show_help
  exit 0
fi

# WP1 Wave B2: push 在任何 Git 执行前拒绝
if [ "$1" = "push" ]; then
  echo "PUBLICATION_OWNER_REQUIRED" >&2
  echo "[git-retry] push 已禁用: 仅 clone-lifecycle integrate 可执行远程 ref 写入" >&2
  exit 2
fi

# 覆盖默认值
if [ -n "${GIT_RETRY_MAX:-}" ]; then
  MAX_RETRIES="$GIT_RETRY_MAX"
fi

last_output=""
for attempt in $(seq 1 "$MAX_RETRIES"); do
  # 捕获输出 (stdout + stderr)
  output=$(git "$@" 2>&1) && {
    printf '%s\n' "$output"
    exit 0
  }
  rc=$?
  last_output="$output"

  # 非网络错误 → 立即失败
  if ! is_network_error "$output"; then
    printf '%s\n' "$output" >&2
    echo "[git-retry] 非网络错误，不再重试 (exit code: $rc)" >&2
    exit $rc
  fi

  if [ "$attempt" -lt "$MAX_RETRIES" ]; then
    delay=${RETRY_DELAYS[$((attempt - 1))]:-10}
    echo "[git-retry] 网络错误，${delay}s 后重试 ($attempt/$MAX_RETRIES)" >&2
    sleep "$delay"
  fi
done

printf '%s\n' "$last_output" >&2
echo "[git-retry] 重试 $MAX_RETRIES 次后仍失败" >&2
exit 1
