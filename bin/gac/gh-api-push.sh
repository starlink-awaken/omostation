#!/bin/bash
# gh-api-push.sh — Wave B3 fail-closed publication bypass closure
#
# WP1 Spec 1.4.0 / Plan Task 10: this helper must not reach Git Data API
# write endpoints. After non-effectful argv validation it emits
# PUBLICATION_OWNER_REQUIRED and exits nonzero. Canonical publication is
# managed `clone-lifecycle integrate` only. Proposal creation ≠ publication;
# unknown outcomes are query-only.
#
# Historical note (BASE-TREE-SNAPSHOT golden rule, 2026-08-24): GitHub Git
# Data API trees are full snapshots, not patches. That write path is retired
# here; do not reintroduce blob/tree/commit/ref POST/PATCH or force=true.

set -euo pipefail

if [ "$#" -lt 6 ]; then
  echo "用法: gh-api-push.sh <owner> <repo> <branch> <base-ref> <commit-msg> <file...>" >&2
  echo "PUBLICATION_OWNER_REQUIRED" >&2
  echo "[gh-api-push] 已禁用: 仅 clone-lifecycle integrate 可执行远程 ref 写入" >&2
  exit 2
fi

shift 5
if [ "$#" -lt 1 ]; then
  echo "❌ 至少需要一个文件" >&2
  echo "PUBLICATION_OWNER_REQUIRED" >&2
  echo "[gh-api-push] 已禁用: 仅 clone-lifecycle integrate 可执行远程 ref 写入" >&2
  exit 2
fi

# Non-effectful argv validation complete — reject before any gh api call.
echo "PUBLICATION_OWNER_REQUIRED" >&2
echo "[gh-api-push] 已禁用: 仅 clone-lifecycle integrate 可执行远程 ref 写入" >&2
exit 2
