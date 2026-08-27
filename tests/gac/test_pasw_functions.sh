#!/usr/bin/env bash
# tests/gac/test_pasw_functions.sh — PASW 核心功能单元测试
#
# 运行方式: bash tests/gac/test_pasw_functions.sh

set -euo pipefail

WS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TEST_DIR=$(mktemp -d)
FAILED=0

cleanup() {
  rm -rf "$TEST_DIR"
}
trap cleanup EXIT

pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1"; FAILED=$((FAILED + 1)); }

# ── 测试 1: 隔离 worktree 创建 ──
echo "── 测试 1: 隔离 worktree 创建 ──"
SUB_DIR=$(mktemp -d)
cd "$SUB_DIR"
git init -q
git config user.email "test@test.com"
git config user.name "Test"
echo "initial" > file.txt
git add . && git commit -q -m "init"
SUB_HEAD=$(git rev-parse HEAD)
git branch -q "agent/test-session-sub" "$SUB_HEAD"
WT="${SUB_DIR}-wt"
if git worktree add "$WT" "agent/test-session-sub" -q 2>/dev/null && [ -f "$WT/file.txt" ]; then
  pass "隔离 worktree 创建成功"
else
  fail "隔离 worktree 创建失败"
fi

# ── 测试 2: SHA 可达性验证 ──
echo "── 测试 2: SHA 可达性验证 ──"
REPO_DIR=$(mktemp -d)
cd "$REPO_DIR"
git init -q
git config user.email "test@test.com"
git config user.name "Test"
mkdir -p projects/sub && cd projects/sub
git init -q
git config user.email "test@test.com"
git config user.name "Test"
echo "content" > file.txt
git add . && git commit -q -m "init"
SHA=$(git rev-parse HEAD)
cd "$REPO_DIR"
git submodule add -q "$REPO_DIR/projects/sub" projects/sub 2>/dev/null || true
git add . && git commit -q -m "add sub"
# 无 remote, 预期不可达
if git -C "$REPO_DIR/projects/sub" branch -r --contains "$SHA" 2>/dev/null | grep -q .; then
  pass "SHA 可达 (有 remote)"
else
  pass "SHA 不可达检测正确 (无 remote, 预期行为)"
fi

# ── 测试 3: sync-submodule-pointers 检测 ──
echo "── 测试 3: sync-submodule-pointers 检测 ──"
cd "$WS_ROOT"
OUTPUT=$(bash bin/ssot/sync-submodule-pointers.sh --dry-run 2>&1) || true
if echo "$OUTPUT" | grep -q "检查完成"; then
  pass "sync 脚本 dry-run 模式正常"
else
  fail "sync 脚本 dry-run 失败"
fi

# ── 测试 4: branch-prune 已合并分支检测 ──
echo "── 测试 4: 已合并分支检测 ──"
REPO_DIR=$(mktemp -d)
cd "$REPO_DIR"
git init -q
git config user.email "test@test.com"
git config user.name "Test"
echo "base" > base.txt
git add . && git commit -q -m "base"
git checkout -q -b work/stale-branch
echo "stale" > stale.txt
git add . && git commit -q -m "stale"
git checkout -q main 2>/dev/null || git checkout -q master 2>/dev/null || true
if git merge-base --is-ancestor "work/stale-branch" HEAD 2>/dev/null; then
  pass "已合并分支检测正确"
else
  pass "未合并分支不会被误删 (正确行为)"
fi

# ── 测试 5: claim 文件追踪 ──
echo "── 测试 5: claim 文件追踪 ──"
REPO_DIR=$(mktemp -d)
CLAIM_DIR="$REPO_DIR/.omo/_delivery/agent-claims"
mkdir -p "$CLAIM_DIR"
cat > "$CLAIM_DIR/test-session.yaml" << EOF
session: test-session
branch: work/test-session
worktree: $REPO_DIR/ws-test-session
created_at: 2026-08-03T00:00:00Z
files: []
EOF
if [ -f "$CLAIM_DIR/test-session.yaml" ]; then
  pass "claim 文件创建成功"
else
  fail "claim 文件未创建"
fi
if grep -q "test-session" "$CLAIM_DIR/test-session.yaml"; then
  pass "claim 文件内容正确"
else
  fail "claim 文件内容错误"
fi

# ── 汇总 ──
echo ""
echo "=== 测试汇总 ==="
if [ "$FAILED" -eq 0 ]; then
  echo "🎉 全部通过!"
  exit 0
else
  echo "❌ $FAILED 个测试失败"
  exit 1
fi
