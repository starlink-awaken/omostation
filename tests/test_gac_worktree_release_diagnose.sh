#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
script="$repo_root/bin/gac/gac-worktree.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

make_repo() {
  local path="$1"
  mkdir -p "$path"
  git -C "$path" init -q
  git -C "$path" config user.email test@example.com
  git -C "$path" config user.name test
  touch "$path/tracked.txt"
  git -C "$path" add tracked.txt
  git -C "$path" commit -qm init
}

# Clean worktree returns 0.
clean_parent="$tmp/clean-parent"
make_repo "$clean_parent/ws-clean"
set +e
clean_output=$(WS_ROOT="$clean_parent/ws-clean" WS_PARENT="$clean_parent" bash "$script" release-diagnose clean 2>&1)
clean_rc=$?
set -e
[ "$clean_rc" -eq 0 ] || { printf '%s\n' "$clean_output" >&2; exit 1; }

# Dirty root returns 1 and preserves the file.
dirty_parent="$tmp/dirty-parent"
make_repo "$dirty_parent/ws-dirty"
printf 'dirty\n' >> "$dirty_parent/ws-dirty/tracked.txt"
set +e
dirty_output=$(WS_ROOT="$dirty_parent/ws-dirty" WS_PARENT="$dirty_parent" bash "$script" release-diagnose dirty 2>&1)
dirty_rc=$?
set -e
[ "$dirty_rc" -eq 1 ] || { printf 'expected dirty rc=1, got %s\n%s\n' "$dirty_rc" "$dirty_output" >&2; exit 1; }
printf '%s\n' "$dirty_output" | grep -Fq '[dirty-root] path=tracked.txt'
printf '%s\n' "$dirty_output" | grep -Fq 'recommendation=preserve-and-review'
test "$(git -C "$dirty_parent/ws-dirty" status --porcelain)" = ' M tracked.txt'

# Dirty submodule returns 1 and is classified separately.
sub_parent="$tmp/sub-parent"
make_repo "$sub_parent/ws-sub"
make_repo "$sub_parent/child"
git -C "$sub_parent/ws-sub" -c protocol.file.allow=always submodule add -q "$sub_parent/child" modules/child
git -C "$sub_parent/ws-sub" commit -qm 'add child submodule'
printf 'dirty\n' >> "$sub_parent/ws-sub/modules/child/tracked.txt"
set +e
sub_output=$(WS_ROOT="$sub_parent/ws-sub" WS_PARENT="$sub_parent" bash "$script" release-diagnose sub 2>&1)
sub_rc=$?
set -e
[ "$sub_rc" -eq 1 ] || { printf 'expected submodule rc=1, got %s\n%s\n' "$sub_rc" "$sub_output" >&2; exit 1; }
printf '%s\n' "$sub_output" | grep -Fq '[dirty-submodule] path=modules/child'

test -f "$sub_parent/ws-sub/modules/child/tracked.txt"

# Missing session metadata returns 2.
set +e
missing_output=$(WS_ROOT="$tmp" WS_PARENT="$tmp" bash "$script" release-diagnose missing 2>&1)
missing_rc=$?
set -e
[ "$missing_rc" -eq 2 ] || { printf 'expected missing rc=2, got %s\n%s\n' "$missing_rc" "$missing_output" >&2; exit 1; }

echo 'release-diagnose clean/dirty-root/dirty-submodule/missing cases: PASS'
