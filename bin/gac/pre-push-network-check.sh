#!/bin/bash
# BET-Y1Q4-T10-131: pre-push 网络连通性预检
# 在 git push 前检测 SSH 连通性，失败时提示切换 HTTPS。
# 仅做建议，不阻断 push。
#
# 用法: bash bin/gac/pre-push-network-check.sh [remote-name]

set -euo pipefail

REMOTE="${1:-origin}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"

if [ -z "$ROOT" ]; then
  echo "[pre-push-netcheck] ⚠️ 不在 git 仓库中" >&2
  exit 0
fi

# 获取远端 URL
REMOTE_URL=$(git remote get-url "$REMOTE" 2>/dev/null || echo '')
if [ -z "$REMOTE_URL" ]; then
  echo "[pre-push-netcheck] ⚠️ 远端 $REMOTE 不存在" >&2
  exit 0
fi

# 只检查 SSH URL
if ! printf '%s' "$REMOTE_URL" | grep -qE '^(git@|ssh://)'; then
  exit 0
fi

# 提取 SSH host
HOST=$(printf '%s' "$REMOTE_URL" | sed -E 's#^(git@|ssh://git@)?([^/:]+).*#\2#')
if [ -z "$HOST" ]; then
  exit 0
fi

# 快速 SSH 连通性检查 (2s 超时)
if timeout 2 ssh -o ConnectTimeout=1 -o BatchMode=yes -o StrictHostKeyChecking=no "$HOST" exit 2>/dev/null; then
  exit 0
fi

# SSH 不可达 → 输出建议
cat << EOF
[pre-push-netcheck] ⚠️ SSH 连接到 $HOST 超时/不可达
  git-retry.sh 将在 push 失败时自动切换到 HTTPS。
  如需手动切换: git remote set-url $REMOTE https://${HOST}/\$(git remote get-url $REMOTE | sed 's#.*:/##')
EOF

exit 0
