#!/bin/bash
# test-resolve-root-remote.sh — Tests for canonical root remote resolution
#
# Tests 3 remote topologies:
# 1. origin=wrong (omostation-runtime), omostation-root=correct → resolves to omostation-root
# 2. Only origin=correct → resolves to origin
# 3. No correct remote → fail closed (exit 1)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOLVER="$SCRIPT_DIR/../../bin/gac/resolve-root-remote.sh"

PASS=0
FAIL=0

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  ✅ $label: '$actual'"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $label: expected '$expected', got '$actual'"
    FAIL=$((FAIL + 1))
  fi
}

assert_fail() {
  local label="$1"
  local output="$2"
  local rc="$3"
  if [ "$rc" -ne 0 ]; then
    echo "  ✅ $label: failed as expected (rc=$rc)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $label: expected failure but got rc=0, output='$output'"
    FAIL=$((FAIL + 1))
  fi
}

# Create a temporary git repo for testing
setup_test_repo() {
  local tmpdir
  tmpdir=$(mktemp -d)
  cd "$tmpdir"
  git init -q
  git commit --allow-empty -q -m "init"
  echo "$tmpdir"
}

cleanup_test_repo() {
  local tmpdir="$1"
  rm -rf "$tmpdir" 2>/dev/null || true
}

echo "=== Test 1: origin=wrong, omostation-root=correct ==="
{
  tmpdir=$(setup_test_repo)
  cd "$tmpdir"
  git remote add origin https://github.com/starlink-awaken/omostation-runtime.git
  git remote add omostation-root https://github.com/starlink-awaken/omostation.git
  result=$(source "$RESOLVER" && resolve_root_remote 2>/dev/null)
  assert_eq "resolves to omostation-root" "omostation-root" "$result"
  cleanup_test_repo "$tmpdir"
}

echo ""
echo "=== Test 2: Only origin=correct ==="
{
  tmpdir=$(setup_test_repo)
  cd "$tmpdir"
  git remote add origin https://github.com/starlink-awaken/omostation.git
  result=$(source "$RESOLVER" && resolve_root_remote 2>/dev/null)
  assert_eq "resolves to origin" "origin" "$result"
  cleanup_test_repo "$tmpdir"
}

echo ""
echo "=== Test 3: No correct remote → fail closed ==="
{
  tmpdir=$(setup_test_repo)
  cd "$tmpdir"
  git remote add origin https://github.com/starlink-awaken/omostation-runtime.git
  git remote add omostation-ssh git@github.com:starlink-awaken/other-repo.git
  output=$(source "$RESOLVER" && resolve_root_remote 2>&1) && rc=0 || rc=$?
  assert_fail "fails with exit 1" "$output" "$rc"
  cleanup_test_repo "$tmpdir"
}

echo ""
echo "=== Test 4: OMOSTATION_ROOT_REMOTE env override ==="
{
  tmpdir=$(setup_test_repo)
  cd "$tmpdir"
  git remote add origin https://github.com/starlink-awaken/omostation-runtime.git
  git remote add my-fork https://github.com/starlink-awaken/omostation.git
  OMOSTATION_ROOT_REMOTE=my-fork result=$(source "$RESOLVER" && resolve_root_remote 2>/dev/null)
  assert_eq "resolves via env override" "my-fork" "$result"
  cleanup_test_repo "$tmpdir"
}

echo ""
echo "=== Test 5: OMOSTATION_ROOT_REMOTE with wrong URL → fail ==="
{
  tmpdir=$(setup_test_repo)
  cd "$tmpdir"
  git remote add origin https://github.com/starlink-awaken/omostation-runtime.git
  git remote add my-fork https://github.com/starlink-awaken/omostation-runtime.git
  output=$(OMOSTATION_ROOT_REMOTE=my-fork source "$RESOLVER" && resolve_root_remote 2>&1) && rc=0 || rc=$?
  assert_fail "env override with wrong URL fails" "$output" "$rc"
  cleanup_test_repo "$tmpdir"
}

echo ""
echo "=== Test 6: SSH URL variant ==="
{
  tmpdir=$(setup_test_repo)
  cd "$tmpdir"
  git remote add origin git@github.com:starlink-awaken/omostation-runtime.git
  git remote add omostation-root git@github.com:starlink-awaken/omostation.git
  result=$(bash -c "source '$RESOLVER' && resolve_root_remote" 2>/dev/null) && rc=0 || rc=$?
  assert_eq "resolves SSH URL" "omostation-root" "$result"
  cleanup_test_repo "$tmpdir"
}

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
