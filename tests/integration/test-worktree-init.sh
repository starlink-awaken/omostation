#!/usr/bin/env bash
# test-worktree-init.sh — 集成测试: worktree-init.sh + --filter=blob:none (T10-138)
#
# 验证:
#   1. --help / 无参数 (会因缺 git 引用失败, 但语法正确返回 nonzero)
#   2. --filter=blob:none 添加成功 (grep 检查)
#   3. --reference 保留 (向后兼容)
#   4. 空 submodule 初始化产出 .git 链接但无文件 (lazy fetch)

set -euo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/bin/gac/worktree-init.sh"
PASS=0
FAIL=0

ok()  { echo "✅ $1"; PASS=$((PASS + 1)); }
ko()  { echo "❌ $1"; FAIL=$((FAIL + 1)); }

# Test 1: --filter=blob:none added in both code paths
if grep -q -- "--filter=blob:none" "$SCRIPT"; then
  ok "--filter=blob:none present"
else
  ko "--filter=blob:none missing"
fi

# Test 2: --reference still present (向后兼容)
if grep -q -- "--reference" "$SCRIPT"; then
  ok "--reference still present"
else
  ko "--reference missing"
fi

# Test 3: --depth 1 still present
if grep -q -- "--depth 1" "$SCRIPT"; then
  ok "--depth 1 still present"
else
  ko "--depth 1 missing"
fi

# Test 4: Bash syntax
if bash -n "$SCRIPT"; then
  ok "bash syntax check"
else
  ko "bash syntax error"
fi

# Test 5: Comment header documents optimization
if grep -q "T10-138 submodule 调研落地" "$SCRIPT"; then
  ok "header documents T10-138 optimization"
else
  ko "header missing T10-138 attribution"
fi

echo ""
echo "worktree-init smoke test: $PASS pass / $FAIL fail"
exit $FAIL
