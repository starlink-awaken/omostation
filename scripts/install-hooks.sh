#!/usr/bin/env bash
set -euo pipefail
# 安装 git hooks 从 canonical source 到执行位置
# 修复: SOURCE=.githooks (canonical tracked), TARGET=.git/hooks (runtime)

SOURCE=".githooks"
TARGET=".git/hooks"

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

# 一致性校验: canonical vs 实际执行位置
ACTUAL_HOOKS="$(git rev-parse --git-path hooks 2>/dev/null)"
MISMATCH=0
for hook in "${TARGET}"/*; do
    name=$(basename "${hook}")
    [ ! -f "${hook}" ] && continue
    if [ -f "${ACTUAL_HOOKS}/${name}" ] && ! cmp -s "${hook}" "${ACTUAL_HOOKS}/${name}"; then
        echo "   ⚠️ 不一致: ${name}"
        MISMATCH=$((MISMATCH + 1))
    fi
done
if [ "${MISMATCH}" -gt 0 ]; then
    echo "❌ ${MISMATCH} 个 hook 不一致 — 请运行 install-hooks 同步"
    exit 1
fi
echo "✅ 一致性校验通过"
