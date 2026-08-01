#!/bin/bash
# Contract tests for canonical repository binding in gac-worktree.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_SCRIPT="$SCRIPT_DIR/../../bin/gac/gac-worktree.sh"

assert_contains() {
  local label="$1" pattern="$2"
  if rg -q --fixed-strings "$pattern" "$WORKTREE_SCRIPT"; then
    printf '  ✅ %s\n' "$label"
  else
    printf '  ❌ %s (missing: %s)\n' "$label" "$pattern"
    exit 1
  fi
}

assert_contains "PR create binds canonical repo" 'gh pr create --repo "$CANONICAL_ROOT_REPO"'
assert_contains "PR merge binds canonical repo" 'gh pr merge "$pr_number" --repo "$CANONICAL_ROOT_REPO"'
assert_contains "post-merge pull uses resolved remote" 'git pull --ff-only "$ROOT_REMOTE" main'
assert_contains "fetch failure is not swallowed" 'set -euo pipefail'

printf 'canonical repository contract: PASS\n'
