#!/bin/bash
# lib/pasw-core.sh — PASW (Per-Agent Submodule Worktree) 核心函数库
#
# 被 gac-worktree.sh source 使用.
# 提供: pasw_create, pasw_cleanup, pasw_claim_*

# 需要独立 worktree 隔离的高冲突子模块 (按冲突频率排序)
export PASW_ISOLATED_SUBS="projects/gbrain projects/cockpit projects/agora"
# 子模块 worktree 存放路径 (root worktree 内)
export PASW_SUBTREE_DIR=".subtrees"
# 过期 TTL (小时)
export PASW_TTL_HOURS="${PASW_TTL_HOURS:-24}"
# claim 文件目录
export PASW_CLAIMS_DIR=".omo/_delivery/agent-claims"

pasw_create() {
  local wt="$1" session="$2"
  local created=0
  for sub in $PASW_ISOLATED_SUBS; do
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
  for sub in $PASW_ISOLATED_SUBS; do
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

pasw_claim_record() {
  local session="$1" wt="$2"
  mkdir -p "$WS_ROOT/$PASW_CLAIMS_DIR"
  local claim_file="$WS_ROOT/$PASW_CLAIMS_DIR/${session}.yaml"
  cat > "$claim_file" << EOF
session: $session
branch: work/$session
worktree: $wt
created_at: $(date -u +%Y-%m-%dT%H:%M:%SZ)
files: []
EOF
  echo "   📝 已记录 claim → $PASW_CLAIMS_DIR/${session}.yaml"
}

pasw_claim_check() {
  local session="$1"
  [ ! -d "$WS_ROOT/$PASW_CLAIMS_DIR" ] && return 0
  local conflicts=0
  for claim_file in "$WS_ROOT/$PASW_CLAIMS_DIR"/*.yaml; do
    [ -f "$claim_file" ] || continue
    local other_session
    other_session=$(python3 -c "import yaml; print(yaml.safe_load(open('$claim_file')).get('session',''))" 2>/dev/null || grep -o 'session:.*' "$claim_file" | head -1 | sed 's/session: //')
    [ -z "$other_session" ] && continue
    [ "$other_session" = "$session" ] && continue
    local other_wt
    other_wt=$(python3 -c "import yaml; print(yaml.safe_load(open('$claim_file')).get('worktree',''))" 2>/dev/null || grep -o 'worktree:.*' "$claim_file" | head -1 | sed 's/worktree: //')
    [ -d "$other_wt" ] || continue
    conflicts=$((conflicts + 1))
    echo "   ⚠️  活跃 session: $other_session (worktree: $other_wt)"
  done
  [ "$conflicts" -gt 0 ] && echo "   ℹ️  共 $conflicts 个活跃 session, 注意文件冲突风险"
}

pasw_claim_clean() {
  local session="$1"
  rm -f "$WS_ROOT/$PASW_CLAIMS_DIR/${session}.yaml" 2>/dev/null || true
}
