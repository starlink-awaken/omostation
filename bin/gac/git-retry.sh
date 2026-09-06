#!/bin/bash
# 机制 20 (2026-09-05): git 操作自动重试 — 应对网络不稳定 (LibreSSL 超时).
#
# 使用:
#   bash bin/gac/git-retry.sh push origin main
#   bash bin/gac/git-retry.sh fetch --prune origin
#   bash bin/gac/git-retry.sh pull --rebase origin main
#
# 行为:
#   - 最多重试 3 次
#   - 每次重试间隔递增 (5s, 10s, 20s)
#   - 仅对网络相关错误重试 (SSL_connect, HTTP/2, timeout, connection refused)
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

if [ $# -eq 0 ]; then
    echo "Usage: bash bin/gac/git-retry.sh <git-command> [args...]"
    echo "Example: bash bin/gac/git-retry.sh push origin main"
    exit 1
fi

last_output=""
for attempt in $(seq 1 $MAX_RETRIES); do
    # 捕获输出
    output=$(git "$@" 2>&1) && {
        # 成功
        printf '%s\n' "$output"
        exit 0
    }
    rc=$?
    last_output="$output"

    if ! is_network_error "$output"; then
        # 非网络错误，立即失败
        printf '%s\n' "$output" >&2
        echo "[git-retry] 非网络错误，不再重试 (exit code: $rc)" >&2
        exit $rc
    fi

    if [ $attempt -lt $MAX_RETRIES ]; then
        delay=${RETRY_DELAYS[$((attempt - 1))]:-10}
        echo "[git-retry] 网络错误，${delay}s 后重试 ($attempt/$MAX_RETRIES): $output" >&2
        sleep $delay
    fi
done

printf '%s\n' "$last_output" >&2
echo "[git-retry] 重试 $MAX_RETRIES 次后仍失败" >&2
exit 1
