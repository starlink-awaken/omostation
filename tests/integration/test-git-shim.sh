#!/usr/bin/env bash
# test-git-shim.sh — git-shim T1-04 fail-closed 测试
#
# 测试 shim 在 swarm-git 缺失时的兜底拦截行为.
# 通过临时创建无 swarm-git 的 worktree 来测试 fail-closed 路径.
# 用法: bash tests/integration/test-git-shim.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SHIM="$ROOT/bin/gac/git-shim"
PASS=0
FAIL=0
TMPDIR_SHIM=""

_cleanup() {
  [ -n "$TMPDIR_SHIM" ] && rm -rf "$TMPDIR_SHIM"
}
trap _cleanup EXIT

# 创建隔离测试环境: 复制 shim + git 仓但无 swarm-git
_setup() {
  TMPDIR_SHIM="$(mktemp -d)"
  local test_root="$TMPDIR_SHIM/repo"
  mkdir -p "$test_root/.git" "$test_root/bin/gac"
  git init -q "$test_root"
  cp "$SHIM" "$test_root/bin/gac/git-shim"
  chmod +x "$test_root/bin/gac/git-shim"
  SHIM="$test_root/bin/gac/git-shim"
  cd "$test_root"
  git config user.email "test@test.com"
  git config user.name "Test"
  git commit --allow-empty -q -m "init"
}

_assert_blocked() {
  local desc="$1"
  shift
  if AGENT_ID="test-agent" bash "$SHIM" "$@" 2>/dev/null; then
    echo "FAIL: $desc (should have been blocked)"
    FAIL=$((FAIL + 1))
  else
    echo "PASS: $desc"
    PASS=$((PASS + 1))
  fi
}

_assert_passthrough() {
  local desc="$1"
  shift
  if AGENT_ID="test-agent" bash "$SHIM" "$@" >/dev/null 2>&1; then
    echo "PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $desc (should have passed through)"
    FAIL=$((FAIL + 1))
  fi
}

_assert_human_passthrough() {
  local desc="$1"
  shift
  if (unset AGENT_ID; bash "$SHIM" "$@" >/dev/null 2>&1); then
    echo "PASS: $desc"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $desc (human should always pass through)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== git-shim T1-04 fail-closed tests ==="
echo ""

_setup

# 1. --no-verify blocked for agent
_assert_blocked "agent --no-verify commit blocked" commit --no-verify -m "test"
_assert_blocked "agent push --no-verify blocked" push --no-verify

# 2. clean -fd blocked for agent
_assert_blocked "agent clean -fd blocked" clean -fd

# 3. reset --hard blocked for agent
_assert_blocked "agent reset --hard blocked" reset --hard HEAD

# 4. stash -u blocked for agent
_assert_blocked "agent stash -u blocked" stash -u

# 5. Safe ops pass through for agent
_assert_passthrough "agent status passes through" status
_assert_passthrough "agent log passes through" log --oneline -1
_assert_passthrough "agent diff passes through" diff --stat

# 6. Human always passes through (even --no-verify)
_assert_human_passthrough "human status passes through" status

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] || exit 1
