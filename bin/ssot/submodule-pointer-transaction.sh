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
changed_from="${SUBMODULE_POINTER_BASE_REF:-}"
incremental=1

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
    --changed-from)
      changed_from="${2:-}"
      [ -n "$changed_from" ] || { echo "--changed-from requires a ref" >&2; exit 2; }
      shift 2
      ;;
    --all)
      changed_from=""
      incremental=0
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$incremental" = "1" ] && [ -z "$changed_from" ]; then
  if git rev-parse --verify --quiet "upstream/main^{commit}" >/dev/null; then
    changed_from="upstream/main"
  else
    changed_from="origin/main"
  fi
fi

if [ "$dry" = "0" ] && ! git diff --cached --quiet; then
  echo "index must be clean before a submodule pointer transaction" >&2
  echo "commit or unstage existing changes; the transaction will stage only its own gitlinks" >&2
  exit 2
fi

stage_paths=()
if [ -n "$changed_from" ]; then
  if ! git rev-parse --verify --quiet "${changed_from}^{commit}" >/dev/null; then
    echo "incremental base is not resolvable: $changed_from (use --all for a full transaction)" >&2
    exit 2
  fi
  if ! git diff --quiet "$changed_from" -- .gitmodules; then
    echo ".gitmodules changed; incremental staging is unsafe (rerun with --all)" >&2
    exit 2
  fi
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    if ! git diff --quiet "$changed_from" -- "$path"; then
      stage_paths+=("$path")
    fi
  done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')
else
  while IFS= read -r path; do
    [ -n "$path" ] && stage_paths+=("$path")
  done < <(git config --file .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}')
  if ! git diff --quiet HEAD -- .gitmodules; then
    stage_paths+=(".gitmodules")
  fi
fi

lock="$(git rev-parse --path-format=absolute --git-path "submodule-pointer-transaction.lock")"
if ! mkdir "$lock" 2>/dev/null; then
  echo "❌ another submodule pointer transaction is active: $lock" >&2
  exit 1
fi
staged_by_transaction=0
cleanup() {
  status=$?
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "$staged_by_transaction" = "1" ]; then
    git restore --staged -- "${stage_paths[@]}" >/dev/null 2>&1 || true
  fi
  rmdir "$lock" 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT

echo "== submodule pointer transaction =="
if [ "$dry" = "1" ]; then
  bash "$ROOT/bin/ssot/sync-submodules-push.sh" --dry-run
  gate_args=(--source worktree --require-main)
  if [ -n "$changed_from" ]; then
    gate_args+=(--changed-from "$changed_from")
  fi
  python3 "$ROOT/bin/ssot/submodule-reachability-gate.py" "${gate_args[@]}"
  exit 0
fi

bash "$ROOT/bin/ssot/sync-submodules-push.sh"
gate_args=(--source worktree --fetch --require-main)
if [ -n "$changed_from" ]; then
  gate_args+=(--changed-from "$changed_from")
fi
python3 "$ROOT/bin/ssot/submodule-reachability-gate.py" "${gate_args[@]}"

if [ "${#stage_paths[@]}" -gt 0 ]; then
  staged_by_transaction=1
  git add -- "${stage_paths[@]}"
fi
python3 "$ROOT/bin/change-lane-check.py" --staged
python3 "$ROOT/bin/ssot/ssot-guardian.py"

if git diff --cached --quiet; then
  echo "no root submodule pointer changes to commit"
  exit 0
fi

if [ -n "$commit_msg" ]; then
  git commit -m "$commit_msg"
  staged_by_transaction=0
else
  echo "staged submodule pointers; pass --message to commit automatically"
fi
