#!/usr/bin/env bash
# 机制 22c (2026-09-05): Hook 智能安装 + 完整性校验.
#
# 使用:
#   bash bin/gac/hook-installer.sh              # 安装 (hash 校验, 仅变化时重装)
#   bash bin/gac/hook-installer.sh --force      # 强制重装
#   bash bin/gac/hook-installer.sh --check      # 仅检查, 不安装

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
if [ -z "$ROOT" ]; then
  echo "❌ 不在 git 仓库" >&2
  exit 1
fi

CANONICAL="$ROOT/.githooks"
# 本仓用 core.hooksPath=.githooks (hooks 直接从 canonical 生效), installer 负责
# 在真实 git-dir/hooks 写入 .version/.content-hash 供 health-check/版本自检.
# 不用 git-path hooks (会被 core.hooksPath 重定向到 .githooks 导致 cp 自拷贝).
# 用 --git-common-dir: worktree 下返回共享主仓 .git (元数据单点), 而非 .git/worktrees/<name>.
GIT_DIR_REAL="$(git rev-parse --git-common-dir 2>/dev/null || echo "$ROOT/.git")"
TARGET="$GIT_DIR_REAL/hooks"
FORCE=0
CHECK_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --check) CHECK_ONLY=1 ;;
  esac
done

mkdir -p "$TARGET"

# ── 计算 canonical 内容哈希 ────────────────────────────────
# 所有 hook 文件 (排除 .md) 的 shasum 排序后拼接再 hash
CANONICAL_HASH=$(find "$CANONICAL" -type f -not -name '*.md' -not -name '.*' | sort | xargs shasum -a 256 2>/dev/null | shasum -a 256 | awk '{print $1}')
INSTALLED_FILE="$TARGET/.content-hash"
INSTALLED_HASH=$(cat "$INSTALLED_FILE" 2>/dev/null || echo "")

# ── 版本校验 ──────────────────────────────────────────────
CANONICAL_VERSION="$(cat "$CANONICAL/VERSION" 2>/dev/null || echo '0.0.0')"
INSTALLED_VERSION="$(cat "$TARGET/.version" 2>/dev/null || echo '0.0.0')"

if [ "$FORCE" -eq 0 ] && [ "$CANONICAL_HASH" = "$INSTALLED_HASH" ] && [ "$CANONICAL_VERSION" = "$INSTALLED_VERSION" ]; then
  echo "✅ hooks 已是最新 (v$CANONICAL_VERSION, ${CANONICAL_HASH:0:12})"
  exit 0
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo "⚠️ hooks 需要更新:" >&2
  echo "   version: $INSTALLED_VERSION → $CANONICAL_VERSION" >&2
  echo "   hash:    ${INSTALLED_HASH:0:12} → ${CANONICAL_HASH:0:12}" >&2
  exit 1
fi

# ── 安装 ──────────────────────────────────────────────────
echo "📦 安装 hooks (v$CANONICAL_VERSION)..."

for hook in "$CANONICAL"/*; do
  name=$(basename "$hook")
  # 跳过非 hook 文件
  [[ "$name" == *.md ]] && continue
  [[ "$name" == VERSION ]] && continue
  [[ "$name" == .* ]] && continue
  [[ -f "$hook" ]] || continue

  cp "$hook" "$TARGET/$name"
  chmod +x "$TARGET/$name"
  echo "   ✓ $name"
done

# ── 写入版本 + hash ───────────────────────────────────────
echo "$CANONICAL_HASH" > "$INSTALLED_FILE"
cp "$CANONICAL/VERSION" "$TARGET/.version" 2>/dev/null || true

echo "✅ hooks 已同步 (v$CANONICAL_VERSION, ${CANONICAL_HASH:0:12})"
