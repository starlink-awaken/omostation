#!/usr/bin/env bash
# fix-remotes.sh — 自动修复 root + 全部 submodule 的 origin 指向
#
# T10-134 hook-manifest.yaml: remote-hygiene check 的 fix 字段指引此脚本
# 当 hook 报错 "origin 指向异常" 时, 可直接复制该 fix 命令执行:
#   python3 bin/ssot/fix-remotes.sh 2>/dev/null || git submodule update --init ...
#
# 行为:
#   1. 修复 root remote.origin.url → canonical omostation URL
#   2. 递归修复 16 个 submodule 的 origin 指向
#   3. 对每个 submodule 用 .gitmodules 中的 url 作为 source of truth
#   4. 仅在当前 URL 与期望 URL 不匹配时修复 (idempotent)
#
# 退出码:
#   0 — 全部修复或已正确
#   1 — 修复失败

set -euo pipefail

CANONICAL_ROOT="https://github.com/starlink-awaken/omostation.git"
WS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

if [ ! -d "$WS_ROOT/.git" ]; then
  echo "❌ $WS_ROOT 不是 git 仓库" >&2
  exit 1
fi

cd "$WS_ROOT"

echo "[fix-remotes] root: 检查 origin 指向"
FETCH_URL=$(git remote get-url origin 2>/dev/null || echo "")
PUSH_URL=$(git remote get-url --push origin 2>/dev/null || echo "")

if [ -n "$FETCH_URL" ] && [ "$FETCH_URL" != "$CANONICAL_ROOT" ] && [ "$FETCH_URL" != "${CANONICAL_ROOT/git@github.com:/https://github.com/}" ]; then
  echo "[fix-remotes] root: 修复 origin fetch $FETCH_URL → $CANONICAL_ROOT"
  git remote set-url origin "$CANONICAL_ROOT"
fi

if [ -n "$PUSH_URL" ] && [ "$PUSH_URL" != "$CANONICAL_ROOT" ]; then
  echo "[fix-remotes] root: 修复 origin push $PUSH_URL → $CANONICAL_ROOT"
  git remote set-url --push origin "$CANONICAL_ROOT"
fi

echo "[fix-remotes] submodule: 递归修复 origin 指向"

git config --file .gitmodules --get-regexp '^submodule\..*\.(path|url)$' 2>/dev/null | \
  awk '{print $1, $2}' | \
  awk -F'[. ]' '{
    if ($1 == "submodule") {
      section = $2
      field = $NF
      if (field == "path") path[section] = $2
      if (field == "url") url[section] = $2
    }
  } END {
    for (s in path) print path[s], url[s]
  }' | while read -r SUB_PATH SUB_URL; do
    if [ ! -d "$SUB_PATH" ]; then
      continue
    fi
    cd "$WS_ROOT/$SUB_PATH"
    CURRENT_SUB=$(git remote get-url origin 2>/dev/null || echo "")
    EXPECTED_HTTPS="$SUB_URL"
    EXPECTED_SSH="${SUB_URL/https:\/\//git@}"
    EXPECTED_SSH="${EXPECTED_SSH/\//:}"

    if [ -n "$CURRENT_SUB" ] && [ "$CURRENT_SUB" != "$EXPECTED_HTTPS" ] && [ "$CURRENT_SUB" != "$EXPECTED_SSH" ]; then
      echo "[fix-remotes] submodule $SUB_PATH: 修复 $CURRENT_SUB → $EXPECTED_HTTPS"
      git remote set-url origin "$EXPECTED_HTTPS"
    fi
    cd "$WS_ROOT"
  done

echo "[fix-remotes] 完成"
exit 0
