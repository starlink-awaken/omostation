#!/usr/bin/env bash
# Contract tests for bin/ssot/submodule-autobump.sh.
#
# T0-T7 each create and tear down their own real Git superproject + remotes.
# The script under test is copied into that superproject, so no scenario can
# read, write, or log the real Workspace submodules.  Historical RED evidence
# from the pre-fix implementation was 20 pass / 8 fail; this harness replaces
# its contaminated fixture with reproducible, isolated evidence.

set -u

TEST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_UNDER_TEST="${SCRIPT_UNDER_TEST:-$TEST_ROOT/bin/ssot/submodule-autobump.sh}"
REAL_GIT="${REAL_GIT:-$(command -v git)}"

PASS=0
FAIL=0
FAILED=()

ok() { PASS=$((PASS + 1)); printf '  PASS %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); FAILED+=("$1"); printf '  FAIL %s\n' "$1"; }
expect_rc() { [ "$2" -eq "$3" ] && ok "$1" || bad "$1 (rc=$2, expected=$3)"; }
expect_nonzero() { [ "$2" -ne 0 ] && ok "$1" || bad "$1 (rc=$2, expected non-zero)"; }

fixture_init() {
  FIXTURE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/submodule-autobump.XXXXXX")"
  REMOTES="$FIXTURE_ROOT/remotes"
  SUPER="$FIXTURE_ROOT/super"
  mkdir -p "$REMOTES"
  export GIT_AUTHOR_NAME=fixture GIT_AUTHOR_EMAIL=fixture@example.test
  export GIT_COMMITTER_NAME=fixture GIT_COMMITTER_EMAIL=fixture@example.test
  export GIT_ALLOW_PROTOCOL=file

  local name seed path remote
  for name in alpha beta gamma delta; do
    "$REAL_GIT" init -q --bare "$REMOTES/$name.git"
    seed="$FIXTURE_ROOT/seed-$name"
    "$REAL_GIT" clone -q "file://$REMOTES/$name.git" "$seed"
    (
      cd "$seed" || exit 1
      printf 'init %s\n' "$name" > state.txt
      "$REAL_GIT" add state.txt
      "$REAL_GIT" commit -qm "init $name"
      "$REAL_GIT" branch -M main
      "$REAL_GIT" push -q origin main
    )
  done

  "$REAL_GIT" init -q -b main "$SUPER"
  for path in alpha beta gamma delta 'space alpha'; do
    remote="$path"
    [ "$path" = 'space alpha' ] && remote=alpha
    "$REAL_GIT" -C "$SUPER" -c protocol.file.allow=always submodule add -q \
      "file://$REMOTES/$remote.git" "$path"
  done
  "$REAL_GIT" -C "$SUPER" commit -qm 'add test submodules'
  "$REAL_GIT" -C "$SUPER" submodule foreach -q 'git fetch -q origin main'
  mkdir -p "$SUPER/bin/ssot"
  cp "$SCRIPT_UNDER_TEST" "$SUPER/bin/ssot/submodule-autobump.sh"
  chmod +x "$SUPER/bin/ssot/submodule-autobump.sh"
}

fixture_teardown() { [ -n "${FIXTURE_ROOT:-}" ] && rm -rf "$FIXTURE_ROOT"; }

run_script() {
  "$REAL_GIT" -C "$SUPER" config user.name 'github-actions[bot]'
  "$REAL_GIT" -C "$SUPER" config user.email '41898282+github-actions[bot]@users.noreply.github.com'
  (cd "$SUPER" && bash bin/ssot/submodule-autobump.sh "$@") 2>&1
}

remote_sha() { "$REAL_GIT" -C "$REMOTES/$1.git" rev-parse refs/heads/main; }
parent_sha() { "$REAL_GIT" -C "$SUPER" ls-files --stage -- "$1" | awk '{print $2}'; }
parent_head() { "$REAL_GIT" -C "$SUPER" rev-parse HEAD; }
parent_tree() { "$REAL_GIT" -C "$SUPER" write-tree; }
index_clean() { [ -z "$("$REAL_GIT" -C "$SUPER" diff --cached --name-only)" ]; }

advance_remote() {
  local name="$1" clone="$FIXTURE_ROOT/advance-$1"
  "$REAL_GIT" clone -q "file://$REMOTES/$name.git" "$clone"
  (
    cd "$clone" || exit 1
    "$REAL_GIT" config user.name fixture
    "$REAL_GIT" config user.email fixture@example.test
    printf 'advance %s %s\n' "$name" "$(date +%s)" >> state.txt
    "$REAL_GIT" add state.txt
    "$REAL_GIT" commit -qm "advance $name"
    "$REAL_GIT" push -q origin main
  )
}

stage_parent_at() {
  "$REAL_GIT" -C "$SUPER" update-index --cacheinfo "160000,$2,$1"
  "$REAL_GIT" -C "$SUPER" commit -qm "parent pointer $1"
}

logs_are_isolated() {
  ! printf '%s' "$1" | grep -qE 'projects/(omo|ecos|kairon|gbrain|cockpit|agora)|/Workspace/|submodule-autobump-safe'
}

assert_failure_unchanged() {
  local label="$1" before_tree="$2" before_head="$3" after_tree after_head
  after_tree="$(parent_tree)"
  after_head="$(parent_head)"
  { [ "$before_tree" = "$after_tree" ] && [ "$before_head" = "$after_head" ] && index_clean; } \
    && ok "$label index tree and HEAD unchanged" || bad "$label index tree or HEAD changed"
}

test_t0() {
  fixture_init
  local out rc
  out="$(run_script --check-only)"; rc=$?
  expect_rc 'T0 equal check-only is noop' "$rc" 0
  logs_are_isolated "$out" && ok 'T0 logs fixture-only paths' || bad 'T0 log isolation'
  fixture_teardown
}

test_t1() {
  fixture_init
  local before_tree before_head out rc
  before_tree="$(parent_tree)"; before_head="$(parent_head)"
  out="$(run_script)"; rc=$?
  expect_rc 'T1 equal apply is noop' "$rc" 0
  assert_failure_unchanged 'T1 noop' "$before_tree" "$before_head"
  logs_are_isolated "$out" && ok 'T1 logs fixture-only paths' || bad 'T1 log isolation'
  fixture_teardown
}

test_t2() {
  fixture_init
  local out rc before_tree before_head
  advance_remote alpha
  before_tree="$(parent_tree)"; before_head="$(parent_head)"
  out="$(run_script --check-only)"; rc=$?
  expect_rc 'T2 pending check-only is exactly one' "$rc" 1
  assert_failure_unchanged 'T2 check-only' "$before_tree" "$before_head"
  logs_are_isolated "$out" && ok 'T2 logs fixture-only paths' || bad 'T2 log isolation'
  fixture_teardown
}

test_t3() {
  fixture_init
  local name out rc before
  for name in alpha beta gamma delta; do advance_remote "$name"; done
  before="$(parent_head)"
  out="$(run_script)"; rc=$?
  expect_rc 'T3 all validated paths apply' "$rc" 0
  for name in alpha beta gamma delta; do
    [ "$(parent_sha "$name")" = "$(remote_sha "$name")" ] \
      && ok "T3 $name points to exact remote SHA" || bad "T3 $name wrong SHA"
  done
  [ "$(parent_sha 'space alpha')" = "$(remote_sha alpha)" ] \
    && ok 'T3 space path points to exact remote SHA' || bad 'T3 space path wrong SHA'
  [ "$("$REAL_GIT" -C "$SUPER" rev-list --count "$before..HEAD")" -eq 1 ] \
    && ok 'T3 creates one commit after aggregate validation' || bad 'T3 commit count is not one'
  logs_are_isolated "$out" && ok 'T3 logs fixture-only paths' || bad 'T3 log isolation'
  fixture_teardown
}

test_t4() {
  fixture_init
  local local_sha before_tree before_head out rc
  (
    cd "$SUPER/alpha" || exit 1
    "$REAL_GIT" config user.name fixture
    "$REAL_GIT" config user.email fixture@example.test
    printf 'local ahead\n' >> state.txt
    "$REAL_GIT" add state.txt
    "$REAL_GIT" commit -qm 'local ahead'
  )
  local_sha="$("$REAL_GIT" -C "$SUPER/alpha" rev-parse HEAD)"
  stage_parent_at alpha "$local_sha"
  before_tree="$(parent_tree)"; before_head="$(parent_head)"
  out="$(run_script)"; rc=$?
  expect_nonzero 'T4 current ahead rejects rewind' "$rc"
  assert_failure_unchanged 'T4' "$before_tree" "$before_head"
  logs_are_isolated "$out" && ok 'T4 logs fixture-only paths' || bad 'T4 log isolation'
  fixture_teardown
}

test_t5() {
  fixture_init
  local local_sha before_tree before_head out rc
  (
    cd "$SUPER/beta" || exit 1
    "$REAL_GIT" config user.name fixture
    "$REAL_GIT" config user.email fixture@example.test
    printf 'local branch\n' >> state.txt
    "$REAL_GIT" add state.txt
    "$REAL_GIT" commit -qm 'local branch'
  )
  local_sha="$("$REAL_GIT" -C "$SUPER/beta" rev-parse HEAD)"
  advance_remote beta
  stage_parent_at beta "$local_sha"
  before_tree="$(parent_tree)"; before_head="$(parent_head)"
  out="$(run_script)"; rc=$?
  expect_nonzero 'T5 divergent current rejects bump' "$rc"
  assert_failure_unchanged 'T5' "$before_tree" "$before_head"
  logs_are_isolated "$out" && ok 'T5 logs fixture-only paths' || bad 'T5 log isolation'
  fixture_teardown
}

test_t6() {
  fixture_init
  local before_tree before_head out rc
  "$REAL_GIT" -C "$SUPER/delta" remote set-url origin "file://$FIXTURE_ROOT/missing.git"
  before_tree="$(parent_tree)"; before_head="$(parent_head)"
  out="$(run_script)"; rc=$?
  expect_nonzero 'T6 fetch failure is fail-closed' "$rc"
  assert_failure_unchanged 'T6' "$before_tree" "$before_head"
  logs_are_isolated "$out" && ok 'T6 logs fixture-only paths' || bad 'T6 log isolation'
  fixture_teardown
}

test_t6b() {
  # alpha 先成为合法候选；随后仅 delta 的 fetch 失败。check-only 也必须
  # 返回 error(2)，且因所有验证完成前不写 index 而保持原样。
  fixture_init
  local wrapdir wrapper_log before_tree before_head out rc
  advance_remote alpha
  wrapdir="$FIXTURE_ROOT/git-fetch-wrapper"
  wrapper_log="$FIXTURE_ROOT/git-fetch-wrapper.log"
  mkdir -p "$wrapdir"
  cat > "$wrapdir/git" <<EOF
#!/usr/bin/env bash
target=""
command=""
expect_target=0
for arg in "\$@"; do
  if [ "\$expect_target" = 1 ]; then
    target="\$arg"
    expect_target=0
    continue
  fi
  if [ "\$arg" = '-C' ]; then
    expect_target=1
    continue
  fi
  [ -z "\$command" ] && command="\$arg"
done
# The script runs from SUPER and intentionally uses relative git -C delta.
if { [ "\$target" = delta ] || [ "\$target" = "$SUPER/delta" ]; } \
  && [ "\$command" = 'ls-remote' ]; then
  printf '%s\n' 'delta ls-remote passed-through' >> "$wrapper_log"
fi
if { [ "\$target" = delta ] || [ "\$target" = "$SUPER/delta" ]; } \
  && [ "\$command" = fetch ]; then
  printf '%s\n' 'delta fetch intercepted' >> "$wrapper_log"
  echo 'controlled fetch failure: delta' >&2
  exit 1
fi
exec "$REAL_GIT" "\$@"
EOF
  chmod +x "$wrapdir/git"
  before_tree="$(parent_tree)"; before_head="$(parent_head)"
  out="$(PATH="$wrapdir:$PATH" run_script --check-only)"; rc=$?
  printf '%s' "$out" | grep -q '🔄 alpha:' \
    && ok 'T6b alpha becomes pending before later failure' || bad 'T6b alpha pending evidence absent'
  grep -q '^delta ls-remote passed-through$' "$wrapper_log" \
    && ok 'T6b delta ls-remote remains real' || bad 'T6b delta ls-remote was not passed through'
  grep -q '^delta fetch intercepted$' "$wrapper_log" \
    && ok 'T6b wrapper intercepts only delta fetch' || bad 'T6b delta fetch was not intercepted'
  expect_rc 'T6b candidate plus fetch failure exits exactly 2' "$rc" 2
  assert_failure_unchanged 'T6b' "$before_tree" "$before_head"
  printf '%s' "$out" | grep -q 'fetch origin main 失败' \
    && ok 'T6b reports public fetch-failure reason' || bad 'T6b fetch-failure reason absent'
  logs_are_isolated "$out" && ok 'T6b logs fixture-only paths' || bad 'T6b log isolation'
  fixture_teardown
}

test_t7() {
  fixture_init
  local wrapdir before_tree before_head out rc
  advance_remote gamma
  wrapdir="$FIXTURE_ROOT/git-wrapper"
  mkdir -p "$wrapdir"
  cat > "$wrapdir/git" <<EOF
#!/usr/bin/env bash
target=""
command=""
expect_target=0
saw_e=0
for arg in "\$@"; do
  if [ "\$expect_target" = 1 ]; then
    target="\$arg"
    expect_target=0
    continue
  fi
  if [ "\$arg" = '-C' ]; then
    expect_target=1
    continue
  fi
  [ -z "\$command" ] && command="\$arg"
  [ "\$arg" = '-e' ] && saw_e=1
done
# The script runs from SUPER and intentionally uses relative git -C gamma.
if [ "\$target" = gamma ] && [ "\$command" = 'cat-file' ] && [ "\$saw_e" = 1 ]; then
  echo 'controlled missing object: gamma' >&2
  exit 1
fi
exec "$REAL_GIT" "\$@"
EOF
  chmod +x "$wrapdir/git"
  before_tree="$(parent_tree)"; before_head="$(parent_head)"
  out="$(PATH="$wrapdir:$PATH" run_script)"; rc=$?
  expect_nonzero 'T7 missing object rejects bump' "$rc"
  assert_failure_unchanged 'T7' "$before_tree" "$before_head"
  printf '%s' "$out" | grep -q '对象缺失' \
    && ok 'T7 reports missing-object reason' || bad 'T7 missing-object reason absent'
  logs_are_isolated "$out" && ok 'T7 logs fixture-only paths' || bad 'T7 log isolation'
  fixture_teardown
}

echo '=== submodule-autobump contract tests ==='
test_t0; test_t1; test_t2; test_t3; test_t4; test_t5; test_t6; test_t6b; test_t7
printf '=== RESULT: PASS=%s FAIL=%s ===\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  printf 'failed: %s\n' "${FAILED[*]}"
  exit 1
fi
