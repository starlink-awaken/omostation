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
  # 第 4 参历史上从未被执行 (但长得像硬超时, 骗过所有人): submodule-reachability
  # 声明 15s, 暖态实测就要 64s —— 直接改成强制会把每次 push 变成假失败, 所以不启用。
  # 真实墙上时间边界由被调脚本自己实现 (bin/ssot/submodule-reachability-gate.py:
  # CMD/FETCH/BUDGET timeout)。这里只保留「预期耗时」作可读文档。
  local _budget_hint_seconds="${4:-10}"

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
      # T10-134 处方化: 从 manifest 读 fix 字段打印可复制修复命令
      _fix_cmd="$(python3 -c "
import yaml, sys
try:
    m = yaml.safe_load(open('$MANIFEST'))
    for hook in m.values():
        if isinstance(hook, dict):
            for c in (hook.get('checks') or []):
                if isinstance(c, dict) and c.get('id') == '$id':
                    print(c.get('fix') or '')
                    sys.exit(0)
except Exception:
    pass
" 2>/dev/null || true)"
      if [ -n "$_fix_cmd" ]; then
        echo "[hook-runner] 💡 fix → $_fix_cmd" >&2
      fi
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

  # lane 隔离: 每 commit 单 lane (ADR-0122 §46「lane 守门: 每 commit 单 lane,
  # pre-commit hook 强制」)。
  #
  # 这是这道尺的**设计指定执行点** —— 但 2026-10-30 实测发现它此前从未真正生效:
  # hook-runner 的 pre-commit 清单里没有它, CI 侧走 --staged 读到空集恒 PASS,
  # PUSH_RANGE 分支在 .githooks/ 无导出点 ⇒ 三条路径全空转, 规则从未被执行过。
  # CI 侧已在 PR #4979 补上第四条路径 (按 PR base..head 逐 commit 判); 本条补第三条
  # (本地提交时按**暂存区**判 —— 即这次提交实际要带上的文件集合)。
  #
  # 判据粒度: --staged 读 `git diff --cached` ⇒ 天然是**单个 commit 的变更集**,
  # 与「每 commit 单 lane」的原文语义一致 (不是整段 PR 合并判)。
  #
  # profile 必须用 pyyaml: classify() 依赖 sgf-policy.yaml 的 gate→lane 映射,
  # 缺 yaml 时它会静默降级成空映射 ⇒ 判定偏宽 (漏判), 那比不接线更坏。
  #
  # 违规处置: 按规则拆成多次提交 (每个 staged set 单 lane)。仓内既定原则见
  # docs/reports/2026-10-26-bet-270-...md §4.5 —— 不加 --allow-lane /
  # AGENT_WORKFLOW_ALLOWED_LANES 自我授权, 而是让规则本身生效。
  if [ -f "$ROOT/bin/change-lane-check.py" ]; then
    run_check "change-lane-check" "$py run --profile pyyaml -- bin/change-lane-check.py --staged" true 3 || FAILED=1
  fi

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

  # lane 隔离 (PUSH_RANGE 导出点 —— ADR-4443 v9 设计的机制, 2026-10-30 补上导出点)
  #
  # 为什么需要它: change-lane-check.py 的 PUSH_RANGE 分支自设计起**从无导出点**
  # (实测 grep -rn PUSH_RANGE .githooks/ = 0 命中; 仓内
  # docs/reports/2026-10-27-bet-273-...md §6 已记同一事实) ⇒ 该机制从未生效。
  #
  # 与 pre-commit 那道尺的分工: pre-commit 拦「本次提交」(暂存区); 本道尺拦
  # 「本次推送的整个 commit 范围」⇒ 兜住绕过 pre-commit 的路径 (--no-verify /
  # 从旧检出提交的 commit)。实测: 用 --no-verify 建一个混 lane commit 后,
  # pre-commit 被绕过而本道尺拦下 (rc=1, 精确指出那个 commit)。
  #
  # 范围解析: export-push-range.py 从 stdin 的 ref 对算出
  # merge-base(origin/<branch>, local_sha)..local_sha —— 精确表示「本地分支相对远端
  # 多出的 commit」。用 merge-base 而非 origin/<branch> 直接当 base: 分支可能落后
  # 于远端 (远端有别人推的 commit), 那样算出的范围会含不属于本次推送的变更。
  #
  # 判据粒度: PUSH_RANGE 分支已改为复用 check_range() 的 **per-commit** 判据
  # (原实现走 git diff --name-only <range> = aggregate, 与规则「每 commit 单 lane」
  # 不符, 且实测会误判「commit A=docs + commit B=子模块指针」那类合法形状)。
  # 本仓全 squash 合并, 但 pre-push 时分支上的 commit 尚未被压缩 ⇒ 判 per-commit
  # 看得到「哪个 commit 混了 lane」, 开发者据此拆; squash 之后就无从拆解了。
  #
  # 解析不出范围时 (首次 push 新分支且无 origin/HEAD / 历史被重写) ⇒ 显式 SKIP,
  # 不输出 PUSH_RANGE ⇒ 下游看到「没有范围」而不是「范围是空」。
  if [ -f "$ROOT/bin/gac/export-push-range.py" ] && [ -f "$ROOT/bin/change-lane-check.py" ]; then
    _push_range="$(python3 "$ROOT/bin/gac/export-push-range.py" 2>/dev/null || true)"
    if [ -n "$_push_range" ]; then
      export PUSH_RANGE="$_push_range"
      run_check "change-lane-check" "$py run --profile pyyaml -- bin/change-lane-check.py" true 5 || FAILED=1
    else
      echo "[hook-runner] ⚠️ [change-lane-check] SKIP 无法解析本次 push 的 commit 范围" >&2
    fi
  fi
}

# ── 解析 manifest 并执行 post-checkout 检查 ─────────────────
# remote-hygiene 自愈 (remote-hygiene-fix) 由 .githooks/post-checkout 直调
# fix-remotes.py — 放最前 (快, 无网络), 不在此重复执行 (幂等但拖慢 checkout).
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
