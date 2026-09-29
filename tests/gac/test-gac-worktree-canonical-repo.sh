#!/bin/bash
# Contract tests for canonical repository binding in gac-worktree.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_SCRIPT="$SCRIPT_DIR/../../bin/gac/gac-worktree.sh"
RESOLVE_SCRIPT="$SCRIPT_DIR/../../bin/gac/resolve-root-remote.sh"

assert_in() {  # $1=label $2=file $3=pattern
  local label="$1" file="$2" pattern="$3"
  if rg -q --fixed-strings "$pattern" "$file"; then
    printf '  ✅ %s\n' "$label"
  else
    printf '  ❌ %s (missing in %s: %s)\n' "$label" "$(basename "$file")" "$pattern"
    exit 1
  fi
}

assert_contains() {  # 针对 canonical 解析脚本的断言
  assert_in "$1" "$WORKTREE_SCRIPT" "$2"
}

# 2026-09-29: 原第一条断言 `gh pr create --repo "$CANONICAL_ROOT_REPO"` 已过期 ——
# 自 WP1 Wave B2 起 submit 是 proposal-only (`gac-worktree.sh` 内不再有 `gh pr create`),
# PR 由人/agent 手动 `gh pr create`。该断言因此恒红 (实测主工作区同样失败)。
# 保留同等意图的替代断言: canonical repo 常量必须定义 (在 resolve-root-remote.sh),
# 且 gh 的写操作必须显式绑它。
assert_in "canonical repo constant is defined" "$RESOLVE_SCRIPT" 'CANONICAL_ROOT_REPO="starlink-awaken/omostation"'
assert_contains "PR merge binds canonical repo" 'gh pr merge "$pr_number" --repo "$CANONICAL_ROOT_REPO"'
assert_contains "post-merge pull uses resolved remote" 'git pull --ff-only "$ROOT_REMOTE" main'
assert_contains "fetch failure is not swallowed" 'set -euo pipefail'

printf 'canonical repository contract: PASS\n'
