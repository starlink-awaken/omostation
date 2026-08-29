#!/usr/bin/env bash
# deploy-scripts.sh — 脚本部署管线（v1.0 · 2026-07-21）
# 用途: 确保 ~/.hermes/scripts/ 下所有脚本可执行、符号链接有效、权限正确
# 集成: 在 cron-service 启动时或 git hook 中调用
#
# usage:
#   bash deploy-scripts.sh              # 检查 + 修复
#   bash deploy-scripts.sh --check      # 仅检查，不修复（exit 1 表示有问题）
#   bash deploy-scripts.sh --verbose    # 详细输出

set -euo pipefail

SCRIPTS_DIR="${HOME}/.hermes/scripts"
CHECK_ONLY=false
VERBOSE=false

for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=true ;;
        --verbose) VERBOSE=true ;;
    esac
done

if [ ! -d "$SCRIPTS_DIR" ]; then
    echo "[FAIL] SCRIPTS_DIR 不存在: $SCRIPTS_DIR"
    exit 1
fi

cd "$SCRIPTS_DIR"
total=0
fixed=0
broken_symlinks=0
missing_shebangs=0

echo "═══ 脚本部署检查: $SCRIPTS_DIR ═══"

# 1. 遍历所有 .sh 文件
while IFS= read -r -d '' f; do
    total=$((total + 1))
    base="$(basename "$f")"
    issues=""

    # 检查 execute bit
    if [ ! -x "$f" ]; then
        issues="$issues NOEXEC"
        if [ "$CHECK_ONLY" = false ]; then
            chmod +x "$f"
            fixed=$((fixed + 1))
        fi
    fi

    # 检查 shebang
    read -r firstline < "$f" || true
    case "$firstline" in
        '#!/bin/bash'|'#!/usr/bin/env bash'|'#!/bin/sh'|'#!/usr/bin/env python3'|'#!/bin/zsh') ;;
        *) issues="$issues NOSHEBANG(${firstline:0:30})"; missing_shebangs=$((missing_shebangs + 1)) ;;
    esac

    if [ "$issues" != "" ] || [ "$VERBOSE" = true ]; then
        echo "  $(printf '%3d' $total) [$( [ -x "$f" ] && echo 'OK' || echo 'FIX' )] $base${issues:+  ← $issues}"
    fi
done < <(find . -name '*.sh' -print0)

# 2. 检查符号链接断链
while IFS= read -r -d '' link; do
    if [ ! -e "$link" ]; then
        broken_symlinks=$((broken_symlinks + 1))
        echo "  [BROKEN] $link → (missing target)"
    fi
done < <(find . -type l -print0)

# 3. 汇总
echo ""
echo "═══ 结果 ═══"
echo "  脚本文件:    $total"
echo "  权限修复:    $fixed"
echo "  缺 shebang:  $missing_shebangs"
echo "  断链:        $broken_symlinks"
echo ""

if [ "$CHECK_ONLY" = true ] && [ "$broken_symlinks" -gt 0 ]; then
    echo "[FAIL] 存在断链符号链接"
    exit 1
fi

if [ "$CHECK_ONLY" = true ] && [ "$fixed" -gt 0 ]; then
    echo "[FAIL] 存在权限问题（--check 模式不修复）"
    exit 1
fi

echo "[PASS] SCRIPTS_DIR 健康"
exit 0
