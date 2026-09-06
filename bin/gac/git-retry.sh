#!/bin/bash
# 机制 20 (2026-09-06, BET-Y1Q4-T10-131): git 操作自动重试 + SSH→HTTPS 故障切换
#
# 使用:
#   bash bin/gac/git-retry.sh push origin main
#   bash bin/gac/git-retry.sh fetch --prune origin
#   bash bin/gac/git-retry.sh pull --rebase origin main
#
# 行为:
#   - 最多重试 3 次，递增延迟 (5s, 10s, 20s)
#   - 仅对网络相关错误重试 (SSL_connect, timeout, connection refused 等)
#   - 非网络错误立即失败
#   - SSH push 失败时自动切换到 HTTPS 重试 (当远端是 SSH URL 时)

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

# SSH 错误关键词 (触发 HTTPS 切换)
SSH_ERRORS=(
  "Permission denied (publickey"
  "ssh: connect to host"
  "Connection refused"
  "Operation timed out"
  "Connection closed by remote"
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

is_ssh_error() {
  local output="$1"
  for err in "${SSH_ERRORS[@]}"; do
    if printf '%s' "$output" | grep -qi "$err"; then
      return 0
    fi
  done
  return 1
}

# 将 SSH URL 转换为 HTTPS URL
ssh_to_https() {
  local url="$1"
  # git@github.com:owner/repo.git → https://github.com/owner/repo.git
  # git@github.com:owner/repo    → https://github.com/owner/repo
  if printf '%s' "$url" | grep -q '^git@'; then
    local host path
    host=$(printf '%s' "$url" | sed 's/^git@\([^:]*\):.*/\1/')
    path=$(printf '%s' "$url" | sed 's/^git@[^:]*:\(.*\)$/\1/')
    printf 'https://%s/%s' "$host" "$path"
    return 0
  fi
  # SSH over port: ssh://git@github.com/owner/repo
  if printf '%s' "$url" | grep -q '^ssh://'; then
    printf '%s' "$url" | sed 's|^ssh://git@|https://|'
    return 0
  fi
  return 1
}

show_help() {
  cat << 'EOF'
用法: bash bin/gac/git-retry.sh <git-cmd> [args...]

示例:
  bash bin/gac/git-retry.sh push origin main
  bash bin/gac/git-retry.sh fetch --prune origin
  bash bin/gac/git-retry.sh pull --rebase origin main

行为:
  - 网络错误自动重试 (最多 3 次, 递增延迟)
  - SSH push 失败时自动切换 HTTPS (仅当远端是 SSH URL)
  - 非网络错误立即失败，不重试

环境变量:
  GIT_RETRY_MAX    最大重试次数 (默认 3)
  GIT_RETRY_DELAY  初始延迟秒数 (默认 5)
  GIT_NO_HTTPS_FALLBACK  设为 1 禁用 HTTPS 故障切换
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

  # SSH 错误 + push 命令 + 未禁用 HTTPS 切换 → 尝试 HTTPS
  if is_ssh_error "$output" && [ "$1" = "push" ] && [ "${GIT_NO_HTTPS_FALLBACK:-0}" != "1" ]; then
    remote="${2:-origin}"
    remote_url=$(git remote get-url "$remote" 2>/dev/null || echo '')
    if [ -n "$remote_url" ]; then
      https_url=$(ssh_to_https "$remote_url") || true
      if [ -n "$https_url" ] && [ "$https_url" != "$remote_url" ]; then
        echo "[git-retry] SSH 失败，切换到 HTTPS: $https_url" >&2
        # 临时修改远端 URL
        git remote set-url "$remote" "$https_url"
        # 用 HTTPS 重试一次
        https_output=$(git "$@" 2>&1) && {
          printf '%s\n' "$https_output"
          echo "[git-retry] HTTPS 切换成功" >&2
          exit 0
        }
        https_rc=$?
        # 恢复 SSH URL
        git remote set-url "$remote" "$remote_url"
        # HTTPS 也失败了，继续正常重试循环
        last_output="$https_output"
      fi
    fi
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
