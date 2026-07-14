#!/usr/bin/env bash
# Single entry point for submodule pointer closure.
#
# Flow:
#   1. acquire a root-level transaction lock
#   2. push submodule commits so gitlinks are reachable
#   3. verify root gitlinks are reachable from submodule origins
#   4. stage submodule pointers and optionally commit the root bump
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

commit_msg=""
dry=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --message|-m)
      commit_msg="${2:-}"
      shift 2
      ;;
    --dry-run)
      dry=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

lock="$ROOT/.git/submodule-pointer-transaction.lock"
if ! mkdir "$lock" 2>/dev/null; then
  echo "❌ another submodule pointer transaction is active: $lock" >&2
  exit 1
fi
trap 'rmdir "$lock"' EXIT

echo "== submodule pointer transaction =="
if [ "$dry" = "1" ]; then
  bash "$ROOT/bin/sync-submodules-push.sh" --dry-run
  python3 "$ROOT/bin/submodule-reachability-gate.py" --source worktree
  exit 0
fi

bash "$ROOT/bin/sync-submodules-push.sh"
python3 "$ROOT/bin/submodule-reachability-gate.py" --source worktree --fetch

git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}' | xargs git add --
python3 "$ROOT/bin/change-lane-check.py" --staged
python3 "$ROOT/bin/ssot-guardian.py"

if git diff --cached --quiet; then
  echo "no root submodule pointer changes to commit"
  exit 0
fi

if [ -n "$commit_msg" ]; then
  git commit -m "$commit_msg"
else
  echo "staged submodule pointers; pass --message to commit automatically"
fi
