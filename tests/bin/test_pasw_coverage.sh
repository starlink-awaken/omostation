#!/usr/bin/env bash
# test_pasw_coverage.sh — verify PASW covers all submodules from .gitmodules
#
# 不变量: `PASW_ISOLATED_SUBS` 与 `.gitmodules` 的 path **一一对应**
#   (计数相等 + 逐项都在列)。计数从 `.gitmodules` 动态取得。
#
# ⚠️ 不可加回硬编码下限(曾为 T1-06 「覆盖 3→18」里程碑写的 `-lt 18`):
# 子模块数 18→16 后该下限恒红, 测试长期"预存红"却无人知(2026-09-29 实测 16 < 18)。
# 模块数属易变事实, 一律动态引用真值源 —— 见 doc-ssot 契约。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source PASW core
source "$ROOT/lib/pasw-core.sh"

# Count submodules from .gitmodules
expected=$(git -C "$ROOT" config --file .gitmodules --get-regexp path 2>/dev/null | awk '{ print $2 }' | wc -w | tr -d ' ')
actual=$(echo "$PASW_ISOLATED_SUBS" | wc -w | tr -d ' ')

echo "Expected submodules: $expected"
echo "PASW_ISOLATED_SUBS count: $actual"

if [ "$expected" -ne "$actual" ]; then
    echo "❌ PASW coverage mismatch: expected $expected, got $actual"
    exit 1
fi

# 逐项 membership: 等式只比计数, 抓不到「少一个 + 多一个」等量替换
for sub in $(git -C "$ROOT" config --file .gitmodules --get-regexp path 2>/dev/null | awk '{ print $2 }'); do
    if ! echo "$PASW_ISOLATED_SUBS" | grep -q "$sub"; then
        echo "❌ Missing submodule: $sub"
        exit 1
    fi
done

echo "✅ PASW covers all $actual submodules"
echo "   Submodules: $PASW_ISOLATED_SUBS"
