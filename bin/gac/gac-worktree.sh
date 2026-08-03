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

WS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$WS_ROOT" ]; then
  echo "❌ 不在 git 仓库" >&2
  exit 1
fi
WS_PARENT="$(dirname "$WS_ROOT")"

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

# PASW: Per-Agent Submodule Worktree (ADR-0346) — 高冲突子模块 per-agent 独立 worktree
# 设计文档: .omo/_knowledge/decisions/0346-pasw-submodule-isolation.md
# 需要独立 worktree 隔离的高冲突子模块 (按冲突频率排序)
ISOLATED_SUBS="projects/gbrain projects/cockpit projects/agora"
# PASW: 子模块 worktree 存放路径 (root worktree 内)
PASW_SUBTREE_DIR=".subtrees"
# PASW: 过期 TTL (小时)
PASW_TTL_HOURS="${PASW_TTL_HOURS:-24}"

pasw_create() {
  local wt="$1" session="$2"
  local created=0
  for sub in $ISOLATED_SUBS; do
    local sub_name
    sub_name=$(basename "$sub")
    local sub_wt="$wt/$PASW_SUBTREE_DIR/$sub_name"
    local sub_branch="agent/${session}-${sub_name}"
    if [ ! -e "$wt/$sub/.git" ]; then
      echo "   📥 init $sub (PASW 需要)..."
      (cd "$wt" && git submodule update --init "$sub" 2>&1) || { echo "   ⚠️  $sub init 失败, 跳过"; continue; }
    fi
    [ -d "$sub_wt" ] && { echo "   ⏭  $sub worktree 已存在"; continue; }
    ( cd "$wt/$sub" && local current_sha && current_sha=$(git rev-parse HEAD) && git branch -f "$sub_branch" "$current_sha" 2>/dev/null || true && mkdir -p "$(dirname "$sub_wt")" && git worktree add "$sub_wt" "$sub_branch" 2>&1 ) && {
      echo "   🔧 PASW: $sub → $PASW_SUBTREE_DIR/$sub_name (branch: $sub_branch)"
      created=$((created + 1))
    } || echo "   ⚠️  $sub worktree 创建失败, 跳过"
  done
  [ "$created" -gt 0 ] && echo "   ✅ PASW: $created 个子模块 worktree 已隔离"
}

pasw_cleanup() {
  local wt="$1"
  local cleaned=0
  for sub in $ISOLATED_SUBS; do
    local sub_name
    sub_name=$(basename "$sub")
    local sub_wt="$wt/$PASW_SUBTREE_DIR/$sub_name"
    local sub_branch
    if [ -d "$sub_wt" ]; then
      sub_branch=$(git -C "$sub_wt" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
      ( cd "$wt/$sub" && git worktree remove "$sub_wt" 2>/dev/null && [ -n "$sub_branch" ] && [ "$sub_branch" != "HEAD" ] && git branch -d "$sub_branch" 2>/dev/null || true ) && {
        echo "   🧹 PASW: 已清理 $sub worktree"
        cleaned=$((cleaned + 1))
      } || { echo "   ⚠️  $sub 清理失败, 强制移除"; rm -rf "$sub_wt" 2>/dev/null || true; }
    fi
  done
  rmdir "$wt/$PASW_SUBTREE_DIR" 2>/dev/null || true
  [ "$cleaned" -gt 0 ] && echo "   ✅ PASW: $cleaned 个子模块 worktree 已清理"
}

case "$cmd" in
  claim)
    [ -z "$session" ] && echo "用法: claim <session>" >&2 && exit 1
    validate_session "$session"
    ROOT_REMOTE=$(resolve_root_remote) || exit 1
    wt="$WS_PARENT/ws-$session"
    branch="work/$session"
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
    if git show-ref --verify --quiet "refs/heads/$branch" 2>/dev/null && [ ! -d "$wt" ]; then
      echo "⚠️  分支 $branch 已存在但 worktree 缺失 (残留? 清理: git branch -D $branch)" >&2
      exit 1
    fi
    if [ -d "$wt" ]; then
      echo "⚠️  worktree 已存在: $wt (cd 过去继续工作)"
    else
      git fetch "$ROOT_REMOTE" main 2>&1 | sed '/FETCH_HEAD/d' >&2
      git worktree add "$wt" -b "$branch" "$ROOT_REMOTE/main" 2>&1
      echo "✅ worktree 创建: $wt"
      echo "   分支: $branch (base: $ROOT_REMOTE/main, repo: $CANONICAL_ROOT_REPO)"
      # Phase 2d ISC-3e + ADR-0204: default init set for gate + agent-workflow + cockpit/agora.
      # worktree 默认不 init → mof-*/doc-ssot-snapshots / omo.workflow / doctor-cron 等跑不了.
      # 默认: ecos+scripts (gate) + omo+cockpit+agora (workflow/L3/I0).
      # INIT_ALL_SUBMODULES=1 全部 (~60s); SKIP_SUBMODULE_INIT=1 跳过.
      # 其他子模块 agent 碰时按需: git submodule update --init <submodule>.
      GATE_SUBS="projects/ecos scripts projects/omo projects/cockpit projects/agora"
      if [ "${SKIP_SUBMODULE_INIT:-}" = "1" ]; then
        echo "   ⏭ SKIP_SUBMODULE_INIT=1 — 子模块未 init (GaC gate / agent-workflow 可能跑不了, 按需 init)"
      elif [ "${INIT_ALL_SUBMODULES:-}" = "1" ]; then
        echo "   init 全部子模块 (INIT_ALL_SUBMODULES=1, 完整环境, 慢 ~60s)..."
        t0=$(date +%s)
        init_out=$(cd "$wt" && git submodule update --init 2>&1)
        init_rc=$?
        t1=$(date +%s)
        init_cnt=$(echo "$init_out" | grep -cE "checked out|initialized" || echo 0)
        echo "   ✅ 全部 init (${init_cnt} 子模块, $((t1-t0))s)"
      else
        echo "   init 默认子模块 ($GATE_SUBS; 其余按需 / INIT_ALL_SUBMODULES=1)..."
        t0=$(date +%s)
        init_out=$(cd "$wt" && git submodule update --init $GATE_SUBS 2>&1)
        init_rc=$?
        t1=$(date +%s)
        init_cnt=$(echo "$init_out" | grep -cE "checked out|initialized" || echo 0)
        if [ $init_rc -eq 0 ]; then
          echo "   ✅ 默认子模块 init 完成 (${init_cnt} 子模块, $((t1-t0))s)"
        else
          echo "   ⚠️  默认子模块 init 失败 (rc=$init_rc, $((t1-t0))s):"
          echo "$init_out" | tail -3
        fi
      fi
      # ADR 占号提示 (不落锁文件除非 --claim; 防并发撞号)
      if [ -x "$WS_ROOT/bin/adr/next-adr-id.py" ] || [ -f "$WS_ROOT/bin/adr/next-adr-id.py" ]; then
        next_adr=$(cd "$wt" && python3 "$WS_ROOT/bin/adr/next-adr-id.py" --session "$session" 2>/dev/null || true)
        if [ -n "$next_adr" ]; then
          echo "   📋 next ADR hint: $next_adr  (claim: python3 bin/adr/next-adr-id.py --session $session --claim)"
        fi
      fi
      # PASW: 创建子模块隔离 worktree
      pasw_create "$wt" "$session"
      echo ""
      echo "   下一步:"
      echo "     cd $wt"
      echo "     uv run --with pyyaml python bin/agent-workflow.py start <workflow-id> --profile <agent> --objective '...'"
      echo "     # ... 工作 (改文件, commit) ..."
      echo "     # 如需改子模块: cd $wt/$PASW_SUBTREE_DIR/<sub_name> && git add . && git commit"
      echo "     # 更新指针:    gac-worktree.sh bump-pointer $session projects/<sub_name>"
      echo "     gac-worktree.sh submit $session"
    fi
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
      git add -- ':!.subtrees' .
      git commit -m "wip: $session worktree 提交" 2>&1 | tail -2
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
    bad = [f['path'] for f in d.get('files',[]) if '.jsonl' in f['path'] or '.lock' in f['path'] or f['path'].startswith('.omo/_knowledge/workflow-mesh/')]
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
    # PASW: 清理子模块 worktree (在移除 root worktree 前)
    pasw_cleanup "$wt"
    git worktree remove "$wt" 2>&1
    echo "✅ worktree 释放: $wt"
    # 分支清理: 已合并到 main → 删; 否则保留 (check-branch-redundant 判重)
    branch="work/$session"
    if git rev-parse --verify "$branch" >/dev/null 2>&1; then
      if git log --oneline --not "origin/main" "$branch" 2>/dev/null | head -1 | grep -q .; then
        echo "   分支 $branch 有 main 外 commit, 保留 (可手动 git branch -D)"
      else
        # 已合并 (无 main 外 commit) → 安全删
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
      # PASW: 清理子模块 worktree (在移除 root worktree 前)
      pasw_cleanup "$wt"
      # 释放 worktree (clean, 因 submit 已 push 全部)
      git worktree remove "$wt" 2>&1
      echo "✅ worktree 释放: $wt"
      # 删本地分支 (远程已 --delete-branch)
      git branch -D "$branch" 2>&1 | tail -1
      echo ""
      echo "🎉 merge 完成: PR #$pr_number → main, worktree + 分支已清理"
    fi
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
    # PASW: 验证 SHA 在 submodule origin/main 上
    ( cd "$wt/$sub" && if git branch -r --contains "$new_sha" 2>/dev/null | grep -q "origin/main"; then
        echo "   ✅ SHA $new_sha 在子模块 origin/main 上 (CI 可达)"
      else
        echo "   ❌ SHA $new_sha 不在子模块 origin/main 上" >&2
        echo "   请先合并子模块 PR 到 main, 再运行 bump-pointer" >&2
        exit 1
      fi )
    cd "$wt"
    git update-index --cacheinfo 160000,"$new_sha","$sub"
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
      for sub in $ISOLATED_SUBS; do
        sub_name=$(basename "$sub")
        [ -d "$wt_path/$PASW_SUBTREE_DIR/$sub_name" ] && sub_list="$sub_list $sub_name"
      done
      [ -n "$sub_list" ] && echo "  $wt_name:$sub_list"
    done
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
    echo "用法: gac-worktree.sh {claim|submit|merge|release|bump-pointer|list|cleanup} [args]"
    echo ""
    echo "  claim <session>      创建 worktree + 分支 work/<session> (+ PASW 子模块隔离)"
    echo "  submit <session>     push 分支 + 开 PR (base main)"
    echo "  merge <session>      squash 合并 PR + release worktree + 删分支"
    echo "  release <session>    清理 worktree (手动, 合并后)"
    echo "  bump-pointer <session> <submodule>  更新子模块指针到 worktree HEAD"
    echo "  list                 列所有 worktree + PASW 状态"
    echo "  cleanup              回收 TTL 过期 worktree (PASW_TTL_HOURS, 默认 24h)"
    echo ""
    echo "PASW 隔离子模块: $ISOLATED_SUBS"
    echo "session 命名: 只允许 [a-z0-9-] (如 fix-route-bug)"
    exit 1
    ;;
esac
