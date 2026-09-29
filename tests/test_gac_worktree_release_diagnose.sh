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

assert_contains() {
  local haystack="$1" needle="$2"
  printf '%s\n' "$haystack" | grep -Fq "$needle" || {
    printf 'missing expected output: %s\n%s\n' "$needle" "$haystack" >&2
    exit 1
  }
}

snapshot_tree() {
  local root="$1"
  (cd "$root" && find . \( -type f -o -type l \) -print | sort | shasum -a 256)
}

run_diagnose() {
  local parent="$1" session="$2"
  local output_var="$3" rc_var="$4" output rc
  set +e
  output=$(WS_ROOT="$parent/ws-$session" WS_PARENT="$parent" bash "$script" release-diagnose "$session" 2>&1)
  rc=$?
  set -e
  printf -v "$output_var" '%s' "$output"
  printf -v "$rc_var" '%s' "$rc"
}

# Clean worktree returns 0.
clean_parent="$tmp/clean-parent"
make_repo "$clean_parent/ws-clean"
run_diagnose "$clean_parent" clean clean_output clean_rc
[ "$clean_rc" -eq 0 ] || { printf '%s\n' "$clean_output" >&2; exit 1; }

# Dirty root returns 1 and preserves the file.
dirty_parent="$tmp/dirty-parent"
make_repo "$dirty_parent/ws-dirty"
printf 'dirty\n' >> "$dirty_parent/ws-dirty/tracked.txt"
before_status=$(git -C "$dirty_parent/ws-dirty" status --porcelain --untracked-files=all)
before_tree=$(snapshot_tree "$dirty_parent/ws-dirty")
run_diagnose "$dirty_parent" dirty dirty_output dirty_rc
[ "$dirty_rc" -eq 1 ] || { printf 'expected dirty rc=1, got %s\n%s\n' "$dirty_rc" "$dirty_output" >&2; exit 1; }
assert_contains "$dirty_output" '[dirty-root] path=tracked.txt recommendation=preserve-and-review'
[ "$(git -C "$dirty_parent/ws-dirty" status --porcelain --untracked-files=all)" = "$before_status" ]
[ "$(snapshot_tree "$dirty_parent/ws-dirty")" = "$before_tree" ]

# A normal projects/* file is not a pointer.
ordinary_parent="$tmp/ordinary-parent"
make_repo "$ordinary_parent/ws-ordinary-project"
mkdir -p "$ordinary_parent/ws-ordinary-project/projects/ordinary"
printf 'ordinary\n' > "$ordinary_parent/ws-ordinary-project/projects/ordinary/tracked.txt"
git -C "$ordinary_parent/ws-ordinary-project" add projects/ordinary/tracked.txt
git -C "$ordinary_parent/ws-ordinary-project" commit -qm ordinary-project
printf 'changed\n' >> "$ordinary_parent/ws-ordinary-project/projects/ordinary/tracked.txt"
run_diagnose "$ordinary_parent" ordinary-project ordinary_output ordinary_rc
[ "$ordinary_rc" -eq 1 ] || { printf '%s\n' "$ordinary_output" >&2; exit 1; }
assert_contains "$ordinary_output" '[dirty-root] path=projects/ordinary/tracked.txt recommendation=preserve-and-review'
if printf '%s\n' "$ordinary_output" | grep -Fq '[pointer]'; then
  printf 'ordinary projects/* file was misclassified as pointer\n%s\n' "$ordinary_output" >&2
  exit 1
fi

# Generated paths keep their generated recommendation.
generated_parent="$tmp/generated-parent"
make_repo "$generated_parent/ws-generated"
mkdir -p "$generated_parent/ws-generated/.omo"
printf 'generated\n' > "$generated_parent/ws-generated/.omo/generated-state.yaml"
run_diagnose "$generated_parent" generated generated_output generated_rc
[ "$generated_rc" -eq 1 ] || { printf '%s\n' "$generated_output" >&2; exit 1; }
assert_contains "$generated_output" '[generated] path=.omo/generated-state.yaml recommendation=review-generated'

# Dirty submodule returns 1 and is classified separately.
sub_parent="$tmp/sub-parent"
make_repo "$sub_parent/ws-sub"
make_repo "$sub_parent/child"
git -C "$sub_parent/ws-sub" -c protocol.file.allow=always submodule add -q "$sub_parent/child" modules/child
git -C "$sub_parent/ws-sub" commit -qm 'add child submodule'
printf 'dirty\n' >> "$sub_parent/ws-sub/modules/child/tracked.txt"
before_status=$(git -C "$sub_parent/ws-sub" status --porcelain --untracked-files=all)
before_tree=$(snapshot_tree "$sub_parent/ws-sub")
run_diagnose "$sub_parent" sub sub_output sub_rc
[ "$sub_rc" -eq 1 ] || { printf 'expected submodule rc=1, got %s\n%s\n' "$sub_rc" "$sub_output" >&2; exit 1; }
assert_contains "$sub_output" '[dirty-submodule] path=modules/child'
test -f "$sub_parent/ws-sub/modules/child/tracked.txt"
[ "$(git -C "$sub_parent/ws-sub" status --porcelain --untracked-files=all)" = "$before_status" ]
[ "$(snapshot_tree "$sub_parent/ws-sub")" = "$before_tree" ]

# A changed gitlink is classified from index mode, not from its path.
pointer_parent="$tmp/pointer-parent"
make_repo "$pointer_parent/ws-pointer"
make_repo "$pointer_parent/child"
git -C "$pointer_parent/ws-pointer" -c protocol.file.allow=always submodule add -q "$pointer_parent/child" modules/child
git -C "$pointer_parent/ws-pointer" commit -qm 'add pointer child'
printf 'second\n' >> "$pointer_parent/child/tracked.txt"
git -C "$pointer_parent/child" add tracked.txt
git -C "$pointer_parent/child" commit -qm 'advance child'
new_child_sha=$(git -C "$pointer_parent/child" rev-parse HEAD)
git -C "$pointer_parent/ws-pointer/modules/child" fetch -q
GIT_ALLOW_PROTOCOL=file git -C "$pointer_parent/ws-pointer/modules/child" checkout -q "$new_child_sha"
git -C "$pointer_parent/ws-pointer" add modules/child
run_diagnose "$pointer_parent" pointer pointer_output pointer_rc
[ "$pointer_rc" -eq 1 ] || { printf '%s\n' "$pointer_output" >&2; exit 1; }
assert_contains "$pointer_output" '[gitlink] path=modules/child recommendation=review-pointer'
if printf '%s\n' "$pointer_output" | grep -Fq '[dirty-root] path=modules/child'; then
  printf 'changed gitlink was misclassified as dirty root\n%s\n' "$pointer_output" >&2
  exit 1
fi

# Configured invalid PASW and unconfigured orphan PASW are distinct.
mkdir -p "$sub_parent/ws-sub/.subtrees/child" "$sub_parent/ws-sub/.subtrees/orphan"
printf 'invalid\n' > "$sub_parent/ws-sub/.subtrees/child/marker.txt"
printf 'orphan\n' > "$sub_parent/ws-sub/.subtrees/orphan/marker.txt"
run_diagnose "$sub_parent" sub pasw_output pasw_rc
[ "$pasw_rc" -eq 1 ] || { printf '%s\n' "$pasw_output" >&2; exit 1; }
assert_contains "$pasw_output" '[invalid-pasw] path='
assert_contains "$pasw_output" '[orphan-pasw] path='

# Spaces and rename state report only the destination path.
rename_parent="$tmp/rename-parent"
make_repo "$rename_parent/ws-rename"
mkdir -p "$rename_parent/ws-rename/notes"
printf 'rename\n' > "$rename_parent/ws-rename/notes/old name.txt"
git -C "$rename_parent/ws-rename" add notes/'old name.txt'
git -C "$rename_parent/ws-rename" commit -qm 'add spaced path'
git -C "$rename_parent/ws-rename" mv notes/'old name.txt' notes/'new name.txt'
run_diagnose "$rename_parent" rename rename_output rename_rc
[ "$rename_rc" -eq 1 ] || { printf '%s\n' "$rename_output" >&2; exit 1; }
assert_contains "$rename_output" '[dirty-root] path=notes/new name.txt recommendation=preserve-and-review'
if printf '%s\n' "$rename_output" | grep -Fq 'old name.txt'; then
  printf 'rename source path was emitted separately\n%s\n' "$rename_output" >&2
  exit 1
fi

# Missing session metadata returns 2.
run_diagnose "$tmp" missing missing_output missing_rc
[ "$missing_rc" -eq 2 ] || { printf 'expected missing rc=2, got %s\n%s\n' "$missing_rc" "$missing_output" >&2; exit 1; }

echo 'release-diagnose precise classification and read-only cases: PASS'
