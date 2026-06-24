#!/usr/bin/env bash
# ─── ecos git hooks 安装 ────────────────────────────────
# 将 scripts/git-hooks/ 中的钩子同步到 .githooks/（核心位置）
# .githooks/ 已配置为 core.hooksPath 目标，所有 git 操作从这里执行
# ──────────────────────────────────────────────────────

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

SOURCE="scripts/git-hooks"
TARGET=".githooks"

echo "🔗 同步 git hooks (${SOURCE}/ → ${TARGET}/)"

if [ ! -d "${SOURCE}" ]; then
    echo "❌ ${SOURCE}/ 不存在"
    exit 1
fi

if [ ! -d "${TARGET}" ]; then
    mkdir -p "${TARGET}"
    echo "  📁 ${TARGET}/ 已创建"
fi

INSTALLED=0
for hook in "${SOURCE}"/*; do
    name=$(basename "${hook}")
    [ ! -f "${hook}" ] && continue

    cp "${hook}" "${TARGET}/${name}"
    chmod +x "${TARGET}/${name}"
    echo "  ✅ ${name}"
    INSTALLED=$((INSTALLED + 1))
done

echo ""
echo "✅ 已同步 ${INSTALLED} 个 git hooks → ${TARGET}/"
echo ""
echo "用法:"
echo "  SKIP_GATE=true  git commit    # 跳过 pre-commit 检查"
echo "  QUICK_PUSH=true git push      # pre-push 跳过测试仅 lint"
echo "  SKIP_GATE=true  git push      # 跳过全部 pre-push 检查"
