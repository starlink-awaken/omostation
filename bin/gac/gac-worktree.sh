#!/bin/bash
# gac-worktree.sh — GaC worktree per session (ADR-0106, P2, 多 agent 并行终态)
#
# 多 agent 并行的物理隔离: 每 session 独立 worktree + 分支, 各改各的, PR 合并.
# 治本 concurrent-agent-contention (共享工作树撞车 → worktree 隔离).
#
# 用法:
#   gac-worktree.sh claim <session>      # 创建 worktree + 分支 work/<session>
#   gac-worktree.sh submit <session>     # push 分支 + 开 PR (base main)
#   gac-worktree.sh merge <session>      # squash 合并 PR + release worktree + 删分支
#   gac-worktree.sh release <session>    # 清理 worktree (手动, 合并后)
#   gac-worktree.sh bump-fast <submodule-path> [--sha <sha>|--latest-main]
#                                         # 流程内快速更新单个子模块指针
#   gac-worktree.sh list                 # 列所有 worktree
#
# session 命名: 只允许 [a-z0-9-] (防 git 分支非法字符), 如 "fix-route-bug".
# 模式: 主仓 worktree (子模块共享). 子模块撞车则需独立 worktree (Phase 1 验证后定).
# 对标: git worktree + PR 流程 (Linux kernel / Devin / Codex).
# 落地计划: docs/AGENT-ISOLATION-ROLLOUT.md (Phase 1).

set -euo pipefail

# Canonical root remote resolution (fail closed if wrong remote)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/resolve-root-remote.sh"

# WS_ROOT/WS_PARENT 可注入 (测试隔离用); 默认从 cwd 解析
WS_ROOT="${WS_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -z "$WS_ROOT" ]; then
  echo "❌ 不在 git 仓库" >&2
  exit 1
fi
WS_PARENT="${WS_PARENT:-$(dirname "$WS_ROOT")}"

cmd="${1:-list}"
session="${2:-}"

# session 名只允许小写字母/数字/连字符 (防 work/<session> 含 git 分支非法字符)
validate_session() {
  local s="$1"
  if ! printf '%s' "$s" | grep -qE '^[a-z0-9][a-z0-9-]*$'; then
    echo "❌ session 名非法: '$s' (只允许 [a-z0-9-], 首字符须字母/数字)" >&2
    exit 1
  fi
}

# PASW: Per-Agent Submodule Worktree (ADR-0371) — 高冲突子模块 per-agent 独立 worktree
# 设计文档: .omo/_knowledge/decisions/0371-pasw-submodule-isolation.md
# 核心函数在根 lib/pasw-core.sh (脚本在 bin/gac/, 需 ../../lib/ 到仓库根)
source "$(dirname "${BASH_SOURCE[0]}")/../../lib/pasw-core.sh"

# ── Fail-closed verification before --force worktree removal ──────────────
# Bug: git worktree remove (without --force) returns exit 128 on worktrees
# with initialized submodules even when everything is clean; --force succeeds.
# This function is the safety gate: dirty root/submodule → abort before removal.
verify_clean_for_force_removal() {
  local wt="$1"
  local dirty=""
  declare -p PASW_ISOLATED_SUBS_ARRAY >/dev/null 2>&1 || PASW_ISOLATED_SUBS_ARRAY=()

  # Use porcelain rather than only diff/diff --cached: it covers unstaged,
  # staged, and untracked changes in one fail-closed check.  .subtrees is an
  # ignored container, not root content; its linked repos are checked below.
  local root_status root_status_line
  if ! root_status=$(git -C "$wt" status --porcelain --untracked-files=all 2>/dev/null); then
    echo "❌ 无法检查 root worktree 状态, 拒绝释放: $wt" >&2
    return 1
  fi
  while IFS= read -r root_status_line; do
    [ -z "$root_status_line" ] && continue
    case "$root_status_line" in
      "?? $PASW_SUBTREE_DIR"|"?? $PASW_SUBTREE_DIR"/*) ;;
      *) dirty="${dirty}root has changes; " ;;
    esac
  done <<< "$root_status"

  # Every initialized ordinary submodule, including nested initialized ones,
  # must be clean before PASW or root worktree removal.
  local sub_path sub_status sub_paths
  if ! sub_paths=$(git -C "$wt" submodule foreach --quiet --recursive 'printf "%s\\n" "$displaypath"' 2>/dev/null); then
    echo "❌ 无法枚举已初始化子模块, 拒绝释放: $wt" >&2
    return 1
  fi
  while IFS= read -r sub_path; do
    [ -z "$sub_path" ] && continue
    if ! sub_status=$(git -C "$wt/$sub_path" status --porcelain --untracked-files=all 2>/dev/null); then
      echo "❌ 无法检查子模块状态, 拒绝释放: $wt/$sub_path" >&2
      return 1
    fi
    if [ -n "$sub_status" ]; then
      dirty="${dirty}submodule $sub_path has changes; "
    fi
  done <<< "$sub_paths"

  # PASW worktrees live under an ignored root directory, so git status at the
  # root cannot protect them.  Check each existing PASW worktree explicitly.
  local sub sub_name pasw_wt pasw_status
  for sub in "${PASW_ISOLATED_SUBS_ARRAY[@]-}"; do
    [ -n "$sub" ] || continue
    sub_name=$(basename "$sub")
    pasw_wt="$wt/$PASW_SUBTREE_DIR/$sub_name"
    [ -d "$pasw_wt" ] || continue
    if ! git -C "$pasw_wt" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      dirty="${dirty}PASW $sub has invalid worktree metadata; "
      continue
    fi
    if ! pasw_status=$(git -C "$pasw_wt" status --porcelain --untracked-files=all 2>/dev/null); then
      echo "❌ 无法检查 PASW worktree 状态, 拒绝释放: $pasw_wt" >&2
      return 1
    fi
    if [ -n "$pasw_status" ]; then
      dirty="${dirty}PASW $sub has changes; "
    fi
  done

  if [ -n "$dirty" ]; then
    echo "❌ worktree 不干净, 拒绝释放 ($dirty)" >&2
    git -C "$wt" status --short 2>/dev/null | head -10 >&2 || true
    return 1
  fi
  return 0
}

# PASW paths are exact, registered git worktrees.  Do not call the legacy
# pasw_cleanup helper here: it falls back to rm -rf when Git refuses removal,
# which would turn a failed safety operation into data loss.  This helper is
# called only after verify_clean_for_force_removal and stops on its first error.
remove_verified_pasw() {
  local wt="$1"
  local sub sub_name pasw_wt pasw_branch registrations

  # Preflight every registered path before touching the first child.  This
  # cannot make Git removal transactional, but catches invalid registrations
  # before a partial cleanup is possible.
  for sub in "${PASW_ISOLATED_SUBS_ARRAY[@]-}"; do
    [ -n "$sub" ] || continue
    sub_name=$(basename "$sub")
    pasw_wt="$wt/$PASW_SUBTREE_DIR/$sub_name"
    [ -d "$pasw_wt" ] || continue

    pasw_branch=$(git -C "$pasw_wt" rev-parse --abbrev-ref HEAD 2>/dev/null) || {
      echo "❌ PASW worktree 元数据无效, 拒绝释放: $pasw_wt" >&2
      return 1
    }
    if ! registrations=$(git -C "$wt/$sub" worktree list --porcelain 2>/dev/null); then
      echo "❌ 无法枚举 PASW worktree, 拒绝释放: $pasw_wt" >&2
      return 1
    fi
    if ! printf '%s\n' "$registrations" | grep -Fqx "worktree $pasw_wt"; then
      echo "❌ PASW worktree 未注册, 拒绝释放: $pasw_wt" >&2
      return 1
    fi
  done

  for sub in "${PASW_ISOLATED_SUBS_ARRAY[@]-}"; do
    [ -n "$sub" ] || continue
    sub_name=$(basename "$sub")
    pasw_wt="$wt/$PASW_SUBTREE_DIR/$sub_name"
    [ -d "$pasw_wt" ] || continue
    pasw_branch=$(git -C "$pasw_wt" rev-parse --abbrev-ref HEAD 2>/dev/null) || {
      echo "❌ PASW worktree 元数据无效, 拒绝释放: $pasw_wt" >&2
      return 1
    }
    if ! git -C "$wt/$sub" worktree remove --force "$pasw_wt"; then
      echo "❌ PASW worktree 清理失败, 拒绝继续释放: $pasw_wt" >&2
      return 1
    fi
    if [ -n "$pasw_branch" ] && [ "$pasw_branch" != "HEAD" ]; then
      git -C "$wt/$sub" branch -d "$pasw_branch" 2>/dev/null || true
    fi
    echo "   🧹 PASW: 已清理 $sub worktree"
  done

  rmdir "$wt/$PASW_SUBTREE_DIR" 2>/dev/null || true
}

case "$cmd" in
  claim)
    [ -z "$session" ] && echo "用法: claim <session>" >&2 && exit 1
    validate_session "$session"
    ROOT_REMOTE=$(cd "$WS_ROOT" && resolve_root_remote) || exit 1
    wt="$WS_PARENT/ws-$session"
    branch="work/$session"
    claim_in_progress="$WS_PARENT/.ws-$session.claiming"
    cleanup_claim_marker() {
      rm -f "$claim_in_progress"
    }
    trap cleanup_claim_marker EXIT INT TERM
    # ── G-CONV.7 / ADR-0220 D2: branch occupancy lock ─────────────────
    # Register before creating worktree so concurrent claim of same slug fails closed.
    if [ -f "$WS_ROOT/bin/gac/swarm-discipline-cli.py" ]; then
      if ! python3 "$WS_ROOT/bin/gac/swarm-discipline-cli.py" branch-claim --session "$session" --branch "$branch" >/tmp/gconv7-branch-claim-$$.json 2>/tmp/gconv7-branch-claim-$$.err; then
        echo "❌ D2 branch occupancy: 无法占用 $branch" >&2
        cat /tmp/gconv7-branch-claim-$$.err >&2 || true
        cat /tmp/gconv7-branch-claim-$$.json 2>/dev/null | head -20 >&2 || true
        rm -f /tmp/gconv7-branch-claim-$$.json /tmp/gconv7-branch-claim-$$.err
        exit 1
      fi
      rm -f /tmp/gconv7-branch-claim-$$.json /tmp/gconv7-branch-claim-$$.err
      echo "   🔒 D2 branch lock: $branch (session=$session)"
    fi
    # 分支已存在但 worktree 缺失 → 残留/重名, 提示清理 (防 claim 撞残留分支)
    if git -C "$WS_ROOT" show-ref --verify --quiet "refs/heads/$branch" 2>/dev/null && [ ! -d "$wt" ]; then
      echo "⚠️  分支 $branch 已存在但 worktree 缺失 (残留? 清理: git branch -D $branch)" >&2
      exit 1
    fi
    if [ -d "$wt" ]; then
      echo "⚠️  worktree 已存在: $wt (cd 过去继续工作)"
    else
      : > "$claim_in_progress"
      git -C "$WS_ROOT" fetch "$ROOT_REMOTE" main 2>&1 | sed '/FETCH_HEAD/d' >&2
      git -C "$WS_ROOT" worktree add "$wt" -b "$branch" "$ROOT_REMOTE/main" 2>&1
      echo "✅ worktree 创建: $wt"
      echo "   分支: $branch (base: $ROOT_REMOTE/main, repo: $CANONICAL_ROOT_REPO)"
    fi
    # PASW: 默认 init 全部子模块 (disk 便宜, 完整环境避免按需 init 的摩擦).
    # Existing root worktrees are repaired and verified too; success must mean
    # full PASW isolation, never merely that the root directory exists.
    if [ "${SKIP_SUBMODULE_INIT:-}" = "1" ]; then
      echo "   ⚠️ SKIP_SUBMODULE_INIT=1 — root worktree only; PASW isolation not established."
      echo "   子模块未 init (按需: cd $wt && git submodule update --init <sub>)"
    else
      echo "   init 全部子模块 (完整环境, 慢 ~60s; SKIP_SUBMODULE_INIT=1 跳过)..."
      t0=$(date +%s)
      init_rc=0
      init_out=$(cd "$wt" && git submodule update --init 2>&1) || init_rc=$?
      t1=$(date +%s)
      init_cnt=$(echo "$init_out" | grep -cE "checked out|initialized" || echo 0)
      if [ "$init_rc" -ne 0 ]; then
        echo "❌ 全部子模块 init 失败 (rc=$init_rc, $((t1-t0))s); 拒绝 PASW claim" >&2
        echo "$init_out" | tail -3 >&2
        # G9 (T10-09): 环境感知 — 未 checkout 的子模块会导致本地 gate 环境性失败
        # (CR-RESIDENT-BOS-01 缺 bos-services.yaml / omo-state-projection-guard 缺投影),
        # 应 init 后重跑, 不是真实缺陷.
        echo "  ℹ️ [环境感知] 子模块未 checkout → gate 环境性失败 (CR-RESIDENT-BOS-01 /" >&2
        echo "    omo-state-projection-guard). 修复: cd $wt && git submodule update --init <sub>;" >&2
        echo "    或完整 init: cd $wt && git submodule update --init" >&2
        exit 1
      fi
      echo "   ✅ 全部 init (${init_cnt} 子模块, $((t1-t0))s)"
      if ! pasw_create "$wt" "$session"; then
        echo "❌ PASW isolation 未完整建立; 保留现有 worktree 供诊断/重试: $wt" >&2
        exit 1
      fi
    fi
    # ADR 占号提示 (不落锁文件除非 --claim; 防并发撞号)
    if [ -x "$WS_ROOT/bin/adr/next-adr-id.py" ] || [ -f "$WS_ROOT/bin/adr/next-adr-id.py" ]; then
      next_adr=$(cd "$wt" && python3 "$WS_ROOT/bin/adr/next-adr-id.py" --session "$session" 2>/dev/null || true)
      if [ -n "$next_adr" ]; then
        echo "   📋 next ADR hint: $next_adr  (claim: python3 bin/adr/next-adr-id.py --session $session --claim)"
      fi
    fi
    echo ""
    echo "   下一步:"
    echo "     cd $wt"
    echo "     uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> --profile <agent> --objective '...'"
    echo "     # ... 工作 (改文件, commit) ..."
    echo "     # 如需改子模块: cd $wt/$PASW_SUBTREE_DIR/<sub_name> && git add . && git commit"
    echo "     # 更新指针:    gac-worktree.sh bump-pointer $session projects/<sub_name>"
    echo "     gac-worktree.sh submit $session"
    cleanup_claim_marker
    trap - EXIT INT TERM
    ;;

  submit)
    [ -z "$session" ] && echo "用法: submit <session>" >&2 && exit 1
    validate_session "$session"
    wt="$WS_PARENT/ws-$session"
    branch="work/$session"
    if [ ! -d "$wt" ]; then
      echo "❌ worktree 不存在: $wt (先 claim)" >&2
      exit 1
    fi
    cd "$wt"
    ROOT_REMOTE=$(resolve_root_remote) || exit 1
    # 提交未提交改动 (如有). PASW: 只 commit root 已 staged 的改动
    if ! git diff --quiet || ! git diff --cached --quiet; then
      # .gitignore 含 .subtrees/ → git add 撞上被忽略路径会返回 1
      # (实测 ':!.subtrees' / ':!.subtrees/' / ':(exclude).subtrees/*' 都是 1),
      # 但非忽略文件其实已暂存成功。set -euo pipefail 下必须吞掉这个返回码,
      # 否则 submit 在此静默中断 —— 后面的 push / 开 PR / CI 校验一个都不执行。
      git add -- ':!.subtrees' . || true
      git commit -m "wip: $session worktree 提交" 2>&1 | tail -2
    fi
    # BET-Y1Q1-T1-05A: fencing token 校验 (shadow 阶段只判定不阻断, exit 2 才停)
    # token 从 claim 文件读 (claim 时由镜像写入 coordination_token 字段);
    # 无 token (claim 早于本 bet / 镜像失败) 也必须进入可审计 shadow verdict
    _t05a_root="$(git rev-parse --show-toplevel)"
    if [ -f "$_t05a_root/bin/gac/swarm-discipline-cli.py" ]; then
      _t05a_token=""
      _claim_file="$_t05a_root/.omo/_delivery/branch-claims/${session}.json"
      if [ -f "$_claim_file" ]; then
        _t05a_token="$(python3 -c "
import json,sys
try:
    print(json.load(open('${_claim_file}')).get('coordination_token', ''))
except Exception: print('')" 2>/dev/null || true)"
      fi
      _t05a_args=(token-check --resource-type branch --resource-id "$branch" \
        --owner "$session" --token "${_t05a_token:-0}")
      if [ -z "$_t05a_token" ]; then
        _t05a_args+=(--missing-token)
      fi
      _t05a_rc=0
      _t05a_out="$(python3 "$_t05a_root/bin/gac/swarm-discipline-cli.py" \
        "${_t05a_args[@]}" 2>&1)" || _t05a_rc=$?
      if [ "$_t05a_rc" -eq 2 ]; then
        echo "❌ coordination store fail-closed (T1-05A): verdict 未记录" >&2
        echo "$_t05a_out" | sed 's/^/   [t05a] /' >&2
        exit 1
      fi
      printf '%s\n' "$_t05a_out" | grep -q '"ok": false' && \
        echo "⚠️  T1-05A shadow: fencing reject on $branch (recorded, not blocking)" >&2
    fi
    # 防 CI 死锁: 检查 dependency-baseline drift (submodule bump 可能引入新依赖)
    # 若 baseline 缺失新依赖, 自动补录 + amend commit, 避免 gac-gate strict 失败阻塞所有 PR
    if [ -f "bin/gen-dependency-baseline.py" ]; then
      BASELINE_RC=0
      uv run --with "pyyaml" python "bin/gen-dependency-baseline.py" --check 2>&1 || BASELINE_RC=$?
      if [ "$BASELINE_RC" -ne 0 ]; then
        echo "⚡ 检测到 dependency-baseline drift, 尝试 --direct-write 自动补录..."
        uv run --with "pyyaml" python "bin/gen-dependency-baseline.py" --direct-write 2>&1 | tail -5
        if [ -f ".omo/_truth/registry/dependency-baseline.yaml" ]; then
          git add .omo/_truth/registry/dependency-baseline.yaml
          git commit --amend --no-edit 2>&1 | tail -1
          echo "   ✅ baseline 已自动补录, commit 已 amend"
        fi
      fi
    fi
    # 推送子模块 commit 到远程 (防 CI "not our ref" 错误)
    echo "⚡ 检查子模块未推送的 commit..."
    bash "$(dirname "$0")/../sync-submodules.sh" --dry-run 2>&1 | tail -5
    bash "$(dirname "$0")/../sync-submodules.sh" 2>&1 | tail -5
    # push 分支
    ROOT_REMOTE=$(resolve_root_remote) || exit 1
    echo "   remote: $ROOT_REMOTE ($(git remote get-url "$ROOT_REMOTE")); repo: $CANONICAL_ROOT_REPO"
    git push -u "$ROOT_REMOTE" "$branch" 2>&1 | tail -3
    # 开 PR
    if command -v gh &>/dev/null; then
      gh pr create --repo "$CANONICAL_ROOT_REPO" --base main --head "$branch" \
        --title "[$session] worktree 提交" \
        --body "GaC worktree per session (ADR-0106 P2). 自动生成 PR." 2>&1 | tail -2
      # PR 文件清单校验 (P74: 防运行时文件混入 PR)
      pr_num=$(gh pr list --repo "$CANONICAL_ROOT_REPO" --head "$branch" --base main --state open --json number 2>/dev/null \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['number'] if d else '')" 2>/dev/null)
      if [ -n "$pr_num" ]; then
        bad_files=$(gh pr view "$pr_num" --repo "$CANONICAL_ROOT_REPO" --json files 2>/dev/null \
          | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    bad = [f['path'] for f in d.get('files',[])
            if ('.jsonl' in f['path'] or '.lock' in f['path'] or f['path'].startswith('.omo/_knowledge/workflow-mesh/'))
            and f.get('changeType') in ('ADDED', 'MODIFIED')]
    print('\n'.join(bad))
except Exception:
    print('')
" 2>/dev/null)
        if [ -n "$bad_files" ]; then
          echo "❌ PR #$pr_num 混入运行时文件, 请移除后重推:" >&2
          echo "$bad_files" | sed 's/^/    /' >&2
          echo "   git rm --cached <file> && git commit --amend && git push --force" >&2
          exit 1
        fi
        echo "   ✅ PR #$pr_num 文件清单校验通过"
      fi
    else
      echo "⚠️  gh 未装, 手动开 PR: base main <- $branch"
    fi
    echo "✅ submit: push $branch + PR"
    ;;

  release)
    [ -z "$session" ] && echo "用法: release <session>" >&2 && exit 1
    validate_session "$session"
    wt="$WS_PARENT/ws-$session"
    # G-CONV.7 D2: release branch occupancy lock (even if worktree already gone)
    if [ -f "$WS_ROOT/bin/gac/swarm-discipline-cli.py" ]; then
      python3 "$WS_ROOT/bin/gac/swarm-discipline-cli.py" branch-release --session "$session" >/dev/null 2>&1 || true
    fi
    if [ ! -d "$wt" ]; then
      echo "⚠️  worktree 不存在: $wt (已释放?)"
      exit 0
    fi
    # 检查未提交
    cd "$wt"
    if ! git diff --quiet || ! git diff --cached --quiet; then
      echo "⚠️  worktree 有未提交改动, 先 submit 或 stash" >&2
      git status --short | head -5
      exit 1
    fi
    cd "$WS_ROOT"
    # Fail-closed: verify root untracked + submodules clean before --force removal
    # (plain git worktree remove returns 128 on worktrees with initialized submodules)
    verify_clean_for_force_removal "$wt" || exit 1
    # PASW: only remove verified Git worktrees; no filesystem fallback.
    remove_verified_pasw "$wt" || exit 1
    git worktree remove --force "$wt" 2>&1
    echo "✅ worktree 释放: $wt"
    # PASW: 清理 claim 记录
    pasw_claim_clean "$session"
    # 分支清理: 已合并到 main → 删; 否则保留
    branch="work/$session"
    if git rev-parse --verify "$branch" >/dev/null 2>&1; then
      if git log --oneline --not "origin/main" "$branch" 2>/dev/null | head -1 | grep -q .; then
        echo "   分支 $branch 有 main 外 commit, 保留 (可手动 git branch -D)"
      else
        git branch -D "$branch" 2>&1 | tail -1
        echo "   ✅ 分支 $branch 已删除 (内容已并入 main)"
      fi
    fi
    ;;

  merge)
    # Phase 2a-3: PR 合并 + release + 删分支 (补全 PR 闭环: claim→submit→merge)
    # L0 萃取在 worktree commit 时已触发 (post-commit commit 级, worktree 共享 .git/hooks),
    # 派生文件进 PR. squash merge 到 main 后无需重跑 (ISC-3c).
    # D3 (F5, 2026-07-02): --auto = GitHub native auto-merge (等 CI+review 自动合, 非立即;
    #   cleanup 待真合后手动 release).
    AUTO=0
    for _a in "$@"; do [ "$_a" = "--auto" ] && AUTO=1; done
    [ -z "$session" ] && echo "用法: merge <session> [--auto]" >&2 && exit 1
    validate_session "$session"
    wt="$WS_PARENT/ws-$session"
    branch="work/$session"
    if [ ! -d "$wt" ]; then
      echo "❌ worktree 不存在: $wt (先 claim + submit)" >&2
      exit 1
    fi
    # worktree 必须已 submit (push + 开 PR). 有未提交 → 提示先 submit.
    cd "$wt"
    if ! git diff --quiet || ! git diff --cached --quiet; then
      echo "⚠️  worktree 有未提交改动, 先 submit" >&2
      git status --short | head -5
      exit 1
    fi
    cd "$WS_ROOT"
    # gh 必备
    if ! command -v gh &>/dev/null; then
      echo "❌ gh 未装, 手动: gh pr merge --squash --head $branch --delete-branch" >&2
      exit 1
    fi
    ROOT_REMOTE=$(resolve_root_remote) || exit 1
    echo "   remote: $ROOT_REMOTE ($(git remote get-url "$ROOT_REMOTE")); repo: $CANONICAL_ROOT_REPO"
    # 查 PR (head work/<session>, base main, open)
    pr_number=$(gh pr list --repo "starlink-awaken/omostation" --head "$branch" --base main --state open --json number 2>/dev/null \
      | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['number'] if d else '')" 2>/dev/null)
    if [ -z "$pr_number" ]; then
      echo "❌ 未找到 open PR (head=$branch base=main). 先 submit 开 PR." >&2
      exit 1
    fi
    if [ "$AUTO" = "1" ]; then
      # D3 (F5): GitHub native auto-merge — 启用 (等 CI+review 满足后 GitHub 自动合).
      # 不做 cleanup (PR 未真合). 真合后手动: gac-worktree.sh release <session>.
      echo "🔗 PR #$pr_number 启用 auto-merge (squash, 等 CI+review 满足自动合)..."
      if ! gh pr merge "$pr_number" --repo "$CANONICAL_ROOT_REPO" --squash --auto --delete-branch 2>&1; then
        echo "❌ PR #$pr_number 启用 auto-merge 失败 (repo 未 enable auto-merge 或 conditions 不满足)" >&2
        exit 1
      fi
      echo "✅ PR #$pr_number 已启用 auto-merge (GitHub 将在 CI+review 过后自动 squash 合并)"
      echo "   合并后手动 release: bash bin/gac-worktree.sh release $session"
    else
      echo "🔗 合并 PR #$pr_number ($branch → main, squash)..."
      # squash merge + 删远程分支. 失败即停 (冲突/constraint 失败等).
      if ! gh pr merge "$pr_number" --repo "$CANONICAL_ROOT_REPO" --squash --delete-branch 2>&1; then
        echo "❌ PR #$pr_number 合并失败 (可能冲突或 CI 未过)" >&2
        exit 1
      fi
      echo "✅ PR #$pr_number 已 squash 合并"
      # 主仓切 main + 拉最新 (含刚合并的)
      git checkout main 2>&1 | tail -1
      git pull --ff-only "$ROOT_REMOTE" main 2>&1 | tail -2
      # Fail-closed: verify clean before --force (plain remove fails on initialized submodules)
      verify_clean_for_force_removal "$wt" || exit 1
      # PASW: only remove verified Git worktrees; no filesystem fallback.
      remove_verified_pasw "$wt" || exit 1
      # 释放 worktree (verified clean; --force needed for initialized submodules)
      git worktree remove --force "$wt" 2>&1
      echo "✅ worktree 释放: $wt"
      # 删本地分支 (远程已 --delete-branch)
      git branch -D "$branch" 2>&1 | tail -1
      echo ""
      echo "🎉 merge 完成: PR #$pr_number → main, worktree + 分支已清理"
    fi
    ;;


  bump-fast)
    sub="${2:-}"
    arg2="${3:---latest-main}"
    [ -z "$sub" ] && echo "用法: bump-fast <submodule-path> [--sha <sha>|--latest-main]" >&2 && exit 1

    cd "$WS_ROOT"

    # bump-fast 只改根仓 index。它仍要在已建立的 D2/D3 claim 内运行，
    # 不是绕过 claim/commit/PR 的通道。全程不 checkout/fetch 子模块工作树。
    sub_url=$(git config --file .gitmodules --get "submodule.$sub.url" || true)
    [ -z "$sub_url" ] && { echo "❌ 找不到子模块 $sub 的 URL 配置" >&2; exit 1; }

    index_entry=$(git ls-files -s -- "$sub")
    index_meta="${index_entry%%$'\t'*}"
    read -r old_mode old_sha old_stage <<< "$index_meta"
    if [ "$old_mode" != "160000" ] || [ "$old_stage" != "0" ]; then
      echo "❌ $sub 不是当前 index 中的已跟踪子模块" >&2
      exit 1
    fi

    # ls-remote 是唯一远端真相源。显式 --sha 用作乐观并发保护：
    # 只有仍是远端 main tip 才允许写入，避免验证后又落后一个版本。
    if ! remote_main=$(git ls-remote "$sub_url" refs/heads/main); then
      echo "❌ 无法通过 ls-remote 访问 $sub 远端 main" >&2
      exit 1
    fi
    main_tip=$(printf '%s\n' "$remote_main" | awk '$2 == "refs/heads/main" {print $1}')
    if ! printf '%s' "$main_tip" | grep -qE '^[0-9a-fA-F]{40}$'; then
      echo "❌ $sub 远端 main 未返回唯一合法 SHA" >&2
      exit 1
    fi

    if [ "$arg2" = "--latest-main" ]; then
      [ -n "${4:-}" ] && { echo "❌ --latest-main 不接受额外参数" >&2; exit 1; }
      new_sha="$main_tip"
    elif [[ "$arg2" == --sha* ]]; then
      if [ "$arg2" = "--sha" ]; then
        new_sha="${4:-}"
        [ -n "${5:-}" ] && { echo "❌ --sha 不接受额外参数" >&2; exit 1; }
      else
        new_sha="${arg2#--sha=}"
        [ -n "${4:-}" ] && { echo "❌ --sha=<sha> 不接受额外参数" >&2; exit 1; }
      fi
      if ! printf '%s' "$new_sha" | grep -qE '^[0-9a-fA-F]{40}$'; then
        echo "❌ 缺少或非法 sha 值: $new_sha" >&2
        exit 1
      fi
      if [ "$new_sha" != "$main_tip" ]; then
        echo "❌ SHA $new_sha 在远端 main 不可达（当前 main tip: ${main_tip}）" >&2
        exit 1
      fi
    else
      echo "❌ 未知参数: $arg2" >&2
      exit 1
    fi

    # 先解析 registry 和远端版本，所有先决条件通过后才改 index。
    # 若对应项目有 version，读取失败必须 fail-closed，不允许静默跳过。
    sub_name=$(basename "$sub")
    registry_version=$(python3 - "$sub_name" <<'PYEOF'
import re
import sys
from pathlib import Path

name = re.escape(sys.argv[1])
text = Path("docs/project-registry.yaml").read_text(encoding="utf-8")
project = re.search(rf"(?ms)^  {name}:\n(?P<body>(?:    .*\n|\s*\n)*)", text)
if not project:
    raise SystemExit(3)
version = re.search(r'(?m)^    version:\s*["\x27]([^"\x27]+)["\x27]\s*$', project.group("body"))
if not version:
    raise SystemExit(4)
print(version.group(1))
PYEOF
    ) || registry_rc=$?
    registry_rc="${registry_rc:-0}"

    new_version=""
    if [ "$registry_rc" = "0" ]; then
      repo_path=$(printf '%s' "$sub_url" | sed -nE 's|.*github\.com[:/]([^/]+/[^/]+)(\.git)?$|\1|p' | sed 's|\.git$||')
      [ -z "$repo_path" ] && { echo "❌ $sub 存在 registry version，但 URL 不是可识别的 GitHub 仓库" >&2; exit 1; }
      command -v gh >/dev/null 2>&1 || { echo "❌ 同步 $sub registry version 需要 gh" >&2; exit 1; }

      if new_version=$(gh api "repos/$repo_path/contents/pyproject.toml?ref=$new_sha" -q .content 2>/dev/null \
          | python3 -c 'import base64,re,sys; t=base64.b64decode(sys.stdin.read()).decode(); s=re.search(r"(?ms)^\[(?:project|tool\.poetry)\]\s*\n(?P<body>.*?)(?=^\[|\Z)", t); v=re.search(r"(?m)^version\s*=\s*[\x27\"]([^\x27\"]+)[\x27\"]", s.group("body") if s else ""); print(v.group(1) if v else "")') \
          && [ -n "$new_version" ]; then
        :
      elif new_version=$(gh api "repos/$repo_path/contents/package.json?ref=$new_sha" -q .content 2>/dev/null \
          | python3 -c 'import base64,json,sys; print(json.loads(base64.b64decode(sys.stdin.read())).get("version", ""))') \
          && [ -n "$new_version" ]; then
        :
      else
        echo "❌ 无法从 $sub@$new_sha 读取 version，registry 与指针将保持未变" >&2
        exit 1
      fi
    elif [ "$registry_rc" != "3" ] && [ "$registry_rc" != "4" ]; then
      echo "❌ 无法检查 docs/project-registry.yaml 中的 $sub_name" >&2
      exit 1
    fi

    git update-index --cacheinfo 160000,"$new_sha","$sub"
    if [ -n "$new_version" ]; then
      if ! python3 - "$sub_name" "$new_version" <<'PYEOF'
import os
import re
import sys
import tempfile
from pathlib import Path

path = Path("docs/project-registry.yaml")
name = re.escape(sys.argv[1])
version = sys.argv[2]
text = path.read_text(encoding="utf-8")
project = re.search(rf"(?ms)^  {name}:\n(?P<body>(?:    .*\n|\s*\n)*)", text)
if not project:
    raise SystemExit(f"project not found: {sys.argv[1]}")
version_match = re.search(
    r'(?m)^(    version:\s*)["\x27]([^"\x27]+)["\x27](\s*)$', project.group("body")
)
if not version_match:
    raise SystemExit(f"version not found: {sys.argv[1]}")
start = project.start("body") + version_match.start()
end = project.start("body") + version_match.end()
replacement = f'{version_match.group(1)}"{version}"{version_match.group(3)}'
updated = text[:start] + replacement + text[end:]
fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(updated)
    os.chmod(temp_name, path.stat().st_mode)
    os.replace(temp_name, path)
except BaseException:
    try:
        os.unlink(temp_name)
    except FileNotFoundError:
        pass
    raise
PYEOF
      then
        git update-index --cacheinfo 160000,"$old_sha","$sub" || true
        echo "❌ registry version 更新失败，已回滚 $sub index 指针" >&2
        exit 1
      fi
      echo "   ✅ docs/project-registry.yaml: $sub_name $registry_version → $new_version"
    fi
    echo "✅ 指针已更新: $sub → $new_sha (bump-fast)"
    echo "   治理要求: 继续完成 claim 校验、commit、tag 与 PR；本命令不替代 D2/D3 门禁"
    ;;
  bump-pointer)
    [ -z "$session" ] && echo "用法: bump-pointer <session> <submodule>" >&2 && exit 1
    validate_session "$session"
    wt="$WS_PARENT/ws-$session"
    sub="${3:-}"
    [ -z "$sub" ] && { echo "❌ 缺少子模块参数" >&2; exit 1; }
    [ ! -d "$wt" ] && { echo "❌ worktree 不存在: $wt" >&2; exit 1; }
    sub_name=$(basename "$sub")
    sub_wt="$wt/$PASW_SUBTREE_DIR/$sub_name"
    [ ! -d "$sub_wt" ] && { echo "❌ 子模块 worktree 不存在: $sub_wt" >&2; exit 1; }
    new_sha=$(git -C "$sub_wt" rev-parse HEAD 2>/dev/null)
    [ -z "$new_sha" ] && { echo "❌ 无法获取 $sub worktree HEAD" >&2; exit 1; }
    # PASW: 验证 SHA 在 submodule remote 上可达 (任意 branch, 不限于 main)
    ( cd "$wt/$sub" && if git branch -r --contains "$new_sha" 2>/dev/null | grep -q .; then
        echo "   ✅ SHA $new_sha 在子模块 remote 上 (CI 可达)"
      else
        echo "   ❌ SHA $new_sha 不在子模块 remote 上" >&2
        echo "   请先 push 子模块分支: cd $sub_wt && git push origin HEAD" >&2
        exit 1
      fi )
    cd "$wt"
    git update-index --cacheinfo 160000,"$new_sha","$sub"
    # ── A (2026-08-06): agora bump → auto-sync bos-registry mirror (防 drift 复发, #1051/#1055 根因) ──
    # agora 改 etc/bos-services.yaml 后, Workspace 根 bos-registry.json 镜像必须跟着 sync,
    # 否则 evidence-gate 报 drift (live vs file) 阻塞 PR. bump-pointer 是精准触发点.
    if [ "$sub" = "projects/agora" ] && [ -f "$wt/bin/ssot/sync-bos-registry.py" ]; then
      if ( cd "$wt" && uv run --with pyyaml python bin/ssot/sync-bos-registry.py --write ) >/dev/null 2>&1; then
        if git -C "$wt" add .omo/_knowledge/bos-registry.json 2>/dev/null; then
          echo "   ✅ bos-registry mirror auto-synced + staged (防 drift, evidence-gate 友好)"
        else
          echo "   ⚠️ bos-registry sync 完成但 stage 失败, 请手动: git add .omo/_knowledge/bos-registry.json"
        fi
      else
        echo "   ⚠️ bos-registry auto-sync 跳过 (sync 失败或 agora 未 init), 记得手动: make sync-bos-registry"
      fi
    fi
    echo "✅ 指针已更新: $sub → $new_sha"
    echo "   下一步: git commit -m 'bump $sub' && gac-worktree.sh submit $session"
    ;;

  list)
    echo "=== GaC worktree 列表 ==="
    git worktree list
    echo ""
    echo "=== PASW 子模块 Worktree ==="
    for wt_path in "$WS_PARENT"/ws-*/; do
      [ -d "$wt_path" ] || continue
      wt_name=$(basename "$wt_path")
      sub_list=""
      for sub in "${PASW_ISOLATED_SUBS_ARRAY[@]-}"; do
        [ -n "$sub" ] || continue
        sub_name=$(basename "$sub")
        [ -d "$wt_path/$PASW_SUBTREE_DIR/$sub_name" ] && sub_list="$sub_list $sub_name"
      done
      [ -n "$sub_list" ] && echo "  $wt_name:$sub_list"
    done
    ;;

  agents)
    # Agent 活动看板: 显示所有活跃 worktree 及其状态 + 文件冲突检测
    echo "=== Agent 活动看板 $(date -u +%Y-%m-%dT%H:%M:%Z) ==="
    echo ""

    # 用临时文件存储每个 session 的文件列表 (兼容 bash 3.2)
    TMP_DIR=$(mktemp -d)
    # 清理临时目录 (脚本退出时)
    trap "rm -rf $TMP_DIR" EXIT

    # 第一遍: 收集所有 agent 的修改文件
    for wt_path in "$WS_PARENT"/ws-*/; do
      [ -d "$wt_path" ] || continue
      wt_name=$(basename "$wt_path")
      session="${wt_name#ws-}"
      git -C "$wt_path" diff --name-only HEAD 2>/dev/null > "$TMP_DIR/$session.files" || true
    done

    # 第二遍: 显示状态 + 冲突检测
    printf "%-28s %-22s %-10s %-8s %-12s %s\n" "SESSION" "BRANCH" "LAST" "PR" "PASW" "CONFLICT"
    printf "%-28s %-22s %-10s %-8s %-12s %s\n" "------" "------" "----" "--" "----" "--------"
    now=$(date +%s)
    for wt_path in "$WS_PARENT"/ws-*/; do
      [ -d "$wt_path" ] || continue
      wt_name=$(basename "$wt_path")
      session="${wt_name#ws-}"

      # 分支
      branch=$(git -C "$wt_path" branch --show-current 2>/dev/null || echo "detached")
      [ ${#branch} -gt 20 ] && branch="${branch:0:17}..."

      # 最后 commit 时间
      last_commit=$(git -C "$wt_path" log -1 --format=%ct 2>/dev/null || echo 0)
      if [ "$last_commit" -gt 0 ]; then
        age_min=$(( (now - last_commit) / 60 ))
        if [ "$age_min" -lt 60 ]; then
          age="${age_min}m"
        elif [ "$age_min" -lt 1440 ]; then
          age=$(( age_min / 60 ))"h"
        else
          age=$(( age_min / 1440 ))"d"
        fi
      else
        age="?"
      fi

      # PR 状态
      pr_status="-"
      if command -v gh >/dev/null 2>&1 && [ "$branch" != "detached" ]; then
        pr_num=$(gh pr list --head "$branch" --state open --json number 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['number'] if d else '')" 2>/dev/null)
        [ -n "$pr_num" ] && pr_status="#${pr_num}"
        if [ -z "$pr_num" ]; then
          merged=$(gh pr list --head "$branch" --state merged --json number 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['number'] if d else '')" 2>/dev/null)
          [ -n "$merged" ] && pr_status="merged"
        fi
      fi

      # PASW 隔离状态
      pasw=""
      for sub in $ISOLATED_SUBS; do
        sub_name=$(basename "$sub")
        [ -d "$wt_path/$PASW_SUBTREE_DIR/$sub_name" ] && pasw="$pasw $sub_name"
      done
      pasw=$(echo "$pasw" | xargs)
      [ -z "$pasw" ] && pasw="-"

      # 冲突检测: 检查与其他 agent 修改的文件是否重叠
      conflict=""
      if [ -f "$TMP_DIR/$session.files" ]; then
        for other_file in "$TMP_DIR"/*.files; do
          [ -f "$other_file" ] || continue
          other_session=$(basename "$other_file" .files)
          [ "$other_session" = "$session" ] && continue
          # 找交集 (comm 需要排序, 用 sort + uniq -d 替代)
          if sort "$TMP_DIR/$session.files" "$other_file" | uniq -d | grep -q .; then
            conflict="$other_session"
            break
          fi
        done
      fi
      [ -z "$conflict" ] && conflict="-"

      printf "%-28s %-22s %-10s %-8s %-12s %s\n" "$session" "$branch" "$age" "$pr_status" "$pasw" "$conflict"
    done
    echo ""
    echo "总计: $(ls -d "$WS_PARENT"/ws-*/ 2>/dev/null | wc -l | tr -d ' ') 个活跃 worktree"
    ;;

  onboard)
    # 新 Agent 入职引导: claim + 环境初始化 + 引导信息
    [ -z "$session" ] && echo "用法: onboard <session>" >&2 && exit 1
    validate_session "$session"
    echo "🚀 Agent 入职引导: $session"
    echo ""

    # 1. Claim worktree (自动 PASW 隔离 + 冲突检测)
    echo "── 1. 创建隔离 worktree ──"
    bash "$0" claim "$session" || exit 1
    wt="$WS_PARENT/ws-$session"

    # 2. 显示项目引导
    echo ""
    echo "── 2. 项目引导 ──"
    if [ -f "$wt/AGENTS.md" ]; then
      echo "📄 项目 AGENTS.md 前 30 行:"
      head -30 "$wt/AGENTS.md"
      echo "..."
    fi

    # 3. 推荐 workflow
    echo ""
    echo "── 3. 推荐工作流 ──"
    echo "  启动 agent-workflow:"
    echo "    cd $wt"
    echo "    uv run --with pyyaml python bin/agent-workflow.py bootstrap"
    echo "    uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> --profile <agent> --objective '<summary>'"

    # 4. 下一步
    echo ""
    echo "── 4. 快速开始 ──"
    echo "   编辑文件: cd $wt"
    echo "   提交改动: git add . && git commit -m '...'"
    echo "   推送 PR:  bash bin/gac-gac-worktree.sh submit $session"
    echo "   查看状态: bash bin/gac-gac-worktree.sh agents"
    echo ""
    echo "✅ 入职完成! 祝编码愉快 🎉"
    ;;

  cleanup)
    # TTL 过期 worktree 回收 (cron 调用入口; gac-worktree-cleanup.sh 委托本子命令)
    # 判定: mtime (非 atime — relatime 下 atime 不更新) 超 TTL 且无脏改动 → 删除
    TTL_HOURS="${PASW_TTL_HOURS:-24}"
    DRY=false
    [ "${2:-}" = "--dry-run" ] && DRY=true
    echo "=== Worktree Cleanup TTL=${TTL_HOURS}h dry=$DRY ==="
    now=$(date +%s)
    pruned=0
    for wt_path in "$WS_PARENT"/ws-*/; do
      [ -d "$wt_path" ] || continue
      wt_name=$(basename "$wt_path")
      # 用 mtime (stat -f %m on macOS / %Y on Linux)
      last_mtime=$(stat -f %m "$wt_path" 2>/dev/null || stat -c %Y "$wt_path" 2>/dev/null || echo 0)
      age_hours=$(( (now - last_mtime) / 3600 ))
      if [ "$age_hours" -lt "$TTL_HOURS" ]; then
        continue
      fi
      # 有未提交改动则跳过 (防丢工作)
      if ! git -C "$wt_path" diff --quiet 2>/dev/null || ! git -C "$wt_path" diff --cached --quiet 2>/dev/null; then
        echo "  ⏭️  $wt_name 有未提交改动, 跳过 (age=${age_hours}h)"
        continue
      fi
      # PASW: 先清理子模块 worktree
      for sub in $ISOLATED_SUBS; do
        sub_name=$(basename "$sub")
        sub_wt="$wt_path/$PASW_SUBTREE_DIR/$sub_name"
        if [ -d "$sub_wt" ]; then
          (git -C "$wt_path/$sub" worktree remove "$sub_wt" 2>/dev/null) || rm -rf "$sub_wt" 2>/dev/null || true
          echo "   🧹 已清理 $sub worktree"
        fi
      done
      rmdir "$wt_path/$PASW_SUBTREE_DIR" 2>/dev/null || true
      if [ "$DRY" = true ]; then
        echo "  🧹 [dry-run] 将回收: $wt_name (age=${age_hours}h)"
      else
        git worktree remove --force "$wt_path" 2>&1 | head -1
        branch="work/${wt_name#ws-}"
        git branch -D "$branch" 2>/dev/null | head -1
        echo "  🧹 回收: $wt_name (age=${age_hours}h)"
      fi
      pruned=$((pruned+1))
    done
    echo "=== Cleanup 完成 (回收 $pruned) ==="
    ;;

  *)
    echo "GaC worktree per session (ADR-0106 P2)"
    echo ""
    echo "用法: gac-worktree.sh {claim|submit|merge|release|bump-fast|bump-pointer|list|agents|onboard|cleanup} [args]"
    echo ""
    echo "  claim <session>      创建 worktree + 分支 work/<session>"
    echo "  submit <session>     push 分支 + 开 PR (base main)"
    echo "  merge <session>      squash 合并 PR + release worktree + 删分支"
    echo "  release <session>    清理 worktree (手动, 合并后)"
    echo "  bump-fast <submodule-path> [--sha <sha>|--latest-main]  流程内快速更新单个子模块指针"
    echo "  bump-pointer <session> <submodule>  更新子模块指针到 worktree HEAD"
    echo "  list                 列所有 worktree + PASW 状态"
    echo "  agents               Agent 活动看板 (session/分支/PR/活跃时间)"
    echo "  onboard <session>    新 Agent 入职引导 (claim + 环境 + 引导)"
    echo "  cleanup              回收 TTL 过期 worktree (PASW_TTL_HOURS, 默认 24h)"
    echo ""
    echo "PASW 隔离子模块: ${ISOLATED_SUBS:-}"
    echo "session 命名: 只允许 [a-z0-9-] (如 fix-route-bug)"
    exit 1
    ;;
esac
