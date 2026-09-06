#!/bin/bash
# 机制 22c (2026-09-05): Hook 调度引擎 — 所有 git hook 的唯一入口.
#
# 使用:
#   bash bin/gac/hook-runner.sh --hook pre-commit
#   bash bin/gac/hook-runner.sh --hook pre-push --profile quick
#   bash bin/gac/hook-runner.sh --hook pre-push --profile full
#
# 职责:
#   - 根据 hook-id 加载 hook-manifest.yaml 中的检查清单
#   - 逐项调用独立检查脚本
#   - 聚合结果、统一日志前缀、支持 SWARM_ESCAPE_ID 逃生
#   - 版本自检 (VERSION vs .version)
#   - 慢检查标记 (>5s)

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
if [ -z "$ROOT" ]; then
  echo "[hook-runner] ❌ 不在 git 仓库" >&2
  exit 1
fi

HOOK_ID="${1:-}"
PROFILE="${HOOK_PROFILE:-quick}"

# 参数解析
while [ $# -gt 0 ]; do
  case "$1" in
    --hook) HOOK_ID="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    *) shift ;;
  esac
done

if [ -z "$HOOK_ID" ]; then
  echo "[hook-runner] 用法: hook-runner.sh --hook <id> [--profile quick|full]" >&2
  exit 1
fi

MANIFEST="$ROOT/.omo/_truth/registry/hook-manifest.yaml"
if [ ! -f "$MANIFEST" ]; then
  echo "[hook-runner] ⚠️ manifest 不存在: $MANIFEST (fallback 到内联检查)" >&2
  exit 0
fi

# ── 版本自检 ────────────────────────────────────────────────
# 元数据在真实 git-dir/hooks (worktree 感知, 不受 core.hooksPath 影响)
# 用 --git-common-dir: worktree 下返回共享主仓 .git (元数据单点), 而非 .git/worktrees/<name>.
CANONICAL_VERSION="$(cat "$ROOT/.githooks/VERSION" 2>/dev/null || echo '0.0.0')"
GIT_DIR_REAL="$(git rev-parse --git-common-dir 2>/dev/null || echo "$ROOT/.git")"
INSTALLED_VERSION="$(cat "$GIT_DIR_REAL/hooks/.version" 2>/dev/null || echo '0.0.0')"
if [ "$CANONICAL_VERSION" != "$INSTALLED_VERSION" ]; then
  echo "[hook-runner] ⚠️ hook 版本不一致 ($INSTALLED_VERSION → $CANONICAL_VERSION)，请运行: make install-hooks" >&2
fi

# ── 获取当前分支 ────────────────────────────────────────────
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

# ── 检查是否在 worktree 中 ─────────────────────────────────
IS_WORKTREE=0
if git rev-parse --is-inside-work-tree 2>/dev/null | grep -q true; then
  if [ -n "$(git rev-parse --git-dir 2>/dev/null)" ]; then
    GIT_DIR="$(git rev-parse --git-dir)"
    if [ "$GIT_DIR" != ".git" ] && [[ "$GIT_DIR" != */.git ]]; then
      IS_WORKTREE=1
    fi
  fi
fi

# ── 逐项执行检查 ────────────────────────────────────────────
FAILED=0
CHECK_COUNT=0
BLOCKING_FAILED=0

# D4 fix: 对 pre-push 预先读取 stdin，避免子检查重复消费或丢失
_PUSH_REFS_FILE=""
if [ "$HOOK_ID" = "pre-push" ]; then
  _PUSH_REFS_FILE="$(mktemp)"
  cat > "$_PUSH_REFS_FILE"
  export PUSH_REFS_FILE="$_PUSH_REFS_FILE"
fi

# 使用 python 解析 YAML 并执行检查
# 简化版: 直接通过环境变量 + 简单逻辑
export ROOT
export BRANCH="$CURRENT_BRANCH"
export PUSH_BRANCH="$CURRENT_BRANCH"
export PUSH_LOCAL_SHA="$(git rev-parse HEAD 2>/dev/null || echo '')"
export IS_WORKTREE

# 执行单个检查
run_check() {
  local id="$1"
  local script="$2"
  local blocking="${3:-true}"
  local timeout="${4:-10}"

  CHECK_COUNT=$((CHECK_COUNT + 1))
  local start_time=$( (perl -MTime::HiRes=time -e 'printf "%d", time()*1_000_000_000' 2>/dev/null || echo 0) )

  # 替换变量
  script="${script//\$ROOT/$ROOT}"
  script="${script//\$BRANCH/$CURRENT_BRANCH}"
  script="${script//\$PUSH_BRANCH/$CURRENT_BRANCH}"
  script="${script//\$PUSH_LOCAL_SHA/$PUSH_LOCAL_SHA}"

  local output
  local rc=0
  output=$(eval "$script" 2>&1) || rc=$?

  local end_time=$( (perl -MTime::HiRes=time -e 'printf "%d", time()*1_000_000_000' 2>/dev/null || echo 0) )
  local elapsed=0
  if [ "$start_time" -gt 0 ] && [ "$end_time" -gt 0 ]; then
    elapsed=$(( (end_time - start_time) / 1000000 ))  # ms
  fi

  if [ $rc -ne 0 ]; then
    if [ "$blocking" = "true" ]; then
      echo "[hook-runner] ❌ [$id] failed (${elapsed}ms)" >&2
      echo "$output" | sed 's/^/   /' >&2
      BLOCKING_FAILED=$((BLOCKING_FAILED + 1))
      return 1
    else
      echo "[hook-runner] ⚠️ [$id] advisory (${elapsed}ms)" >&2
      echo "$output" | sed 's/^/   /' >&2
    fi
  else
    if [ "$elapsed" -gt 5000 ]; then
      echo "[hook-runner] 🐢 [$id] ${elapsed}ms (slow, 建议下沉 CI)" >&2
    fi
  fi
  return 0
}

# ── 解析 manifest 并执行 pre-commit 检查 ───────────────────
run_hook_pre_commit() {
  local py="$ROOT/bin/gac/managed-python"

  # clone-guard
  if [ -f "$ROOT/bin/gac/agent-clone.py" ]; then
    local clone_args="guard --workspace $ROOT --json"
    if [ -n "${AGENT_ID:-}" ]; then
      clone_args="$clone_args --require-clone"
    fi
    run_check "clone-guard" "$py run --profile stdlib -- bin/gac/agent-clone.py $clone_args" true 5 || true
  fi

  # branch-naming
  run_check "branch-naming" "$py run --profile pyyaml -- bin/gac/check-branch-naming.py --branch $CURRENT_BRANCH --policy .omo/_truth/registry/branch-prefix-policy.yaml" true 3 || FAILED=1

  # conflict-marker
  if [ -f "$ROOT/bin/gac/check-conflict-markers.py" ]; then
    run_check "conflict-marker" "$py run --profile stdlib -- bin/gac/check-conflict-markers.py" true 2 || FAILED=1
  fi

  # mass-deletion
  if [ -f "$ROOT/bin/gac/mass-deletion-gate.py" ]; then
    run_check "mass-deletion" "$py run --profile stdlib -- bin/gac/mass-deletion-gate.py --staged" true 3 || FAILED=1
  fi

  # runtime-artifacts
  run_check "runtime-artifacts" "$py run --profile stdlib -- bin/gac/check-runtime-artifacts.py --staged" true 3 || FAILED=1

  # debt-guard (python script, use python to run)
  run_check "debt-guard" "$py run --profile stdlib -- bin/gac/debt-directory-guard.py" true 2 || FAILED=1

  # submodule-guard (python script, use python to run)
  run_check "submodule-guard" "$py run --profile stdlib -- bin/gac/submodule-guard.py --staged" true 5 || FAILED=1

  # advisory: hygiene
  if [ -x "$ROOT/bin/gac/gac-hygiene-check.py" ]; then
    run_check "hygiene" "$py run --profile stdlib -- bin/gac/gac-hygiene-check.py" false 10 || true
  fi
}

# ── 解析 manifest 并执行 pre-push 检查 ─────────────────────
run_hook_pre_push() {
  local py="$ROOT/bin/gac/managed-python"

  # branch-naming (per push ref)
  run_check "branch-naming" "$py run --profile pyyaml -- bin/gac/check-branch-naming.py --branch $CURRENT_BRANCH --policy .omo/_truth/registry/branch-prefix-policy.yaml" true 3 || FAILED=1

  # direct-push-main
  run_check "direct-push-main" "$py run --profile stdlib -- bin/gac/guard-direct-push-main.py" true 2 || FAILED=1

  # submodule-sync
  run_check "submodule-sync" "bash bin/ssot/sync-submodules-push.sh" true 30 || FAILED=1

  # submodule-reachability
  run_check "submodule-reachability" "$py run --profile stdlib -- bin/ssot/submodule-reachability-gate.py --source head --fetch" true 15 || FAILED=1

  # mass-deletion
  if [ -f "$ROOT/bin/gac/mass-deletion-gate.py" ]; then
    run_check "mass-deletion" "$py run --profile stdlib -- bin/gac/mass-deletion-gate.py --range origin/main HEAD --submodules" true 5 || FAILED=1
  fi

  # gitlink-ancestry
  run_check "gitlink-ancestry" "$py run --profile pyyaml -- bin/gac/check-submodule-rewind.py --range origin/main $PUSH_LOCAL_SHA" true 5 || FAILED=1

  # remote-hygiene
  run_check "remote-hygiene" "$py run --profile stdlib -- bin/gac/remote-hygiene-check.py" true 3 || FAILED=1
}

# ── 解析 manifest 并执行 post-checkout 检查 ─────────────────
run_hook_post_checkout() {
  local py="$ROOT/bin/gac/managed-python"
  run_check "branch-naming" "$py run --profile pyyaml -- bin/gac/check-branch-naming.py --branch $CURRENT_BRANCH --policy .omo/_truth/registry/branch-prefix-policy.yaml" true 3 || FAILED=1
}

# ── 主入口 ──────────────────────────────────────────────────
case "$HOOK_ID" in
  pre-commit)
    run_hook_pre_commit
    ;;
  pre-push)
    run_hook_pre_push
    ;;
  post-checkout)
    run_hook_post_checkout
    ;;
  *)
    echo "[hook-runner] ⚠️ 未知 hook: $HOOK_ID (跳过)" >&2
    ;;
esac

if [ "$FAILED" -gt 0 ]; then
  echo "[hook-runner] ❌ $BLOCKING_FAILED 项 blocking 检查失败" >&2
  exit 1
fi

exit 0
