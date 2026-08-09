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

# ── 一致性保障 (2026-08-08 复盘): 同步到实际执行位置 + 校验 ──
# 根因: core.hooksPath 指向 .git/hooks, 但 install 只装到 .githooks/,
# 两者从不同步 → 本地手改的 hook 会在下次 install 时丢失/被覆盖.
# 修复: (1) 若 core.hooksPath 指向别处, 同步 .githooks/ → 该位置
#       (2) 校验 canonical (.githooks/) 与执行位置一致, 不一致则告警.
ACTUAL_HOOKS="$(git rev-parse --git-path hooks 2>/dev/null)"
if [ -n "${ACTUAL_HOOKS}" ] && [ "${ACTUAL_HOOKS}" != "${TARGET}" ]; then
    mkdir -p "${ACTUAL_HOOKS}"
    SYNCED=0
    for hook in "${TARGET}"/*; do
        name=$(basename "${hook}")
        [ ! -f "${hook}" ] && continue
        cp "${hook}" "${ACTUAL_HOOKS}/${name}"
        chmod +x "${ACTUAL_HOOKS}/${name}"
        SYNCED=$((SYNCED + 1))
    done
    echo "🔗 同步 ${SYNCED} 个 hooks → 执行位置 ${ACTUAL_HOOKS}/"
fi

MISMATCH=0
for hook in "${TARGET}"/*; do
    name=$(basename "${hook}")
    [ ! -f "${hook}" ] && continue
    if [ -f "${ACTUAL_HOOKS}/${name}" ] && ! cmp -s "${hook}" "${ACTUAL_HOOKS}/${name}"; then
        echo "   ⚠️ 不一致: ${name} (canonical ${TARGET}/ vs 执行 ${ACTUAL_HOOKS}/)"
        MISMATCH=$((MISMATCH + 1))
    fi
done
if [ "${MISMATCH}" -gt 0 ]; then
    echo "❌ ${MISMATCH} 个 hook 不一致 — 请检查是否有并行 install 覆盖"
    exit 1
fi
echo "✅ 一致性校验通过 (canonical == 执行位置)"

echo ""
echo "用法:"
echo "  SKIP_GATE=true  git commit    # 跳过 pre-commit 检查"
echo "  QUICK_PUSH=true git push      # pre-push 跳过测试仅 lint"
echo "  SKIP_GATE=true  git push      # 跳过全部 pre-push 检查"
