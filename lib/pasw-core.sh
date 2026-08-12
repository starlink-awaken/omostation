#!/bin/bash
# lib/pasw-core.sh — PASW (Per-Agent Submodule Worktree) 核心函数库
#
# 被 gac-worktree.sh source 使用.
# 提供: pasw_create, pasw_cleanup, pasw_claim_*

# 子模块 worktree 存放路径 (root worktree 内)
export PASW_SUBTREE_DIR=".subtrees"
# 过期 TTL (小时)
export PASW_TTL_HOURS="${PASW_TTL_HOURS:-24}"
# claim 文件目录
export PASW_CLAIMS_DIR=".omo/_delivery/agent-claims"

pasw_resolve_isolated_subs() {
  local repo_root="$1"
  local gitmodules="$repo_root/.gitmodules"
  local config_entry sub_path

  if [ ! -r "$gitmodules" ]; then
    echo "❌ 无法读取 PASW 子模块清单: $gitmodules" >&2
    return 1
  fi
  PASW_ISOLATED_SUBS_ARRAY=()
  while IFS= read -r -d '' config_entry; do
    sub_path="${config_entry#*$'\n'}"
    if [ "$sub_path" = "$config_entry" ] || [ -z "$sub_path" ]; then
      echo "❌ 无法解析 PASW 子模块清单: $gitmodules" >&2
      return 1
    fi
    PASW_ISOLATED_SUBS_ARRAY+=("$sub_path")
  done < <(git -C "$repo_root" config --null --file "$gitmodules" --get-regexp '^submodule\..*\.path$' 2>/dev/null)
  if [ "${#PASW_ISOLATED_SUBS_ARRAY[@]}" -eq 0 ]; then
    echo "❌ PASW 子模块清单为空: $gitmodules" >&2
    return 1
  fi
  export PASW_ISOLATED_SUBS="$(printf '%s\n' "${PASW_ISOLATED_SUBS_ARRAY[@]}")"
}

pasw_verify_isolation() {
  local wt="$1"
  local failed=0
  local sub sub_name sub_wt root_sha ordinary_sha pasw_sha registrations

  pasw_resolve_isolated_subs "$wt" || return 1
  for sub in "${PASW_ISOLATED_SUBS_ARRAY[@]}"; do
    sub_name=$(basename "$sub")
    sub_wt="$wt/$PASW_SUBTREE_DIR/$sub_name"
    if ! root_sha=$(git -C "$wt" rev-parse "HEAD:$sub" 2>/dev/null); then
      echo "❌ PASW 验证失败: root gitlink 不存在: $sub" >&2
      failed=1
      continue
    fi
    if ! ordinary_sha=$(git -C "$wt/$sub" rev-parse HEAD 2>/dev/null); then
      echo "❌ PASW 验证失败: 普通子模块不可用: $sub" >&2
      failed=1
      continue
    fi
    if [ ! -d "$sub_wt" ]; then
      echo "❌ PASW 验证失败: worktree 缺失: $sub_wt" >&2
      failed=1
      continue
    fi
    if ! registrations=$(git -C "$wt/$sub" worktree list --porcelain 2>/dev/null) \
      || ! printf '%s\n' "$registrations" | grep -Fqx "worktree $sub_wt"; then
      echo "❌ PASW 验证失败: worktree 未注册: $sub_wt" >&2
      failed=1
      continue
    fi
    if ! pasw_sha=$(git -C "$sub_wt" rev-parse HEAD 2>/dev/null); then
      echo "❌ PASW 验证失败: worktree 不可用: $sub_wt" >&2
      failed=1
      continue
    fi
    if [ "$root_sha" != "$ordinary_sha" ] || [ "$root_sha" != "$pasw_sha" ]; then
      echo "❌ PASW 验证失败: SHA 不一致: $sub" >&2
      failed=1
    fi
  done
  [ "$failed" -eq 0 ]
}

pasw_create() {
  local wt="$1" session="$2"
  local created=0
  local failed=0
  local sub sub_name sub_wt sub_branch sub_branch_name root_sha

  pasw_resolve_isolated_subs "$wt" || return 1
  for sub in "${PASW_ISOLATED_SUBS_ARRAY[@]}"; do
    sub_name=$(basename "$sub")
    sub_wt="$wt/$PASW_SUBTREE_DIR/$sub_name"
    sub_branch_name="${sub_name// /-}"
    sub_branch="agent/${session}-${sub_branch_name}"
    if [ ! -e "$wt/$sub/.git" ]; then
      echo "   📥 init $sub (PASW 需要)..."
      if ! (cd "$wt" && git submodule update --init "$sub" 2>&1); then
        echo "   ❌ $sub init 失败" >&2
        failed=1
        continue
      fi
    fi
    if ! root_sha=$(git -C "$wt" rev-parse "HEAD:$sub" 2>/dev/null); then
      echo "   ❌ $sub root gitlink 不可用" >&2
      failed=1
      continue
    fi
    if [ -d "$sub_wt" ]; then
      echo "   ⏭  $sub worktree 已存在, 将验证"
      continue
    fi
    if ! (
      cd "$wt/$sub" \
        && git branch -f "$sub_branch" "$root_sha" \
        && mkdir -p "$(dirname "$sub_wt")" \
        && git worktree add "$sub_wt" "$sub_branch" 2>&1
    ); then
      echo "   ❌ $sub worktree 创建失败" >&2
      failed=1
      continue
    fi
    {
      echo "   🔧 PASW: $sub → $PASW_SUBTREE_DIR/$sub_name (branch: $sub_branch)"
      created=$((created + 1))
    }
  done
  [ "$created" -gt 0 ] && echo "   ✅ PASW: $created 个子模块 worktree 已创建"
  [ "$failed" -eq 0 ] && pasw_verify_isolation "$wt" || return 1
  echo "   ✅ PASW isolation established"
}

# Source-time consumers (for example coverage tests) get a best-effort value
# from the library's owning repository, never the caller's current directory.
PASW_LIBRARY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASW_REPOSITORY_ROOT="${WS_ROOT:-$PASW_LIBRARY_ROOT}"
export PASW_ISOLATED_SUBS=""
declare -a PASW_ISOLATED_SUBS_ARRAY=()
if [ -r "$PASW_REPOSITORY_ROOT/.gitmodules" ]; then
  pasw_resolve_isolated_subs "$PASW_REPOSITORY_ROOT" >/dev/null || true
fi
unset PASW_LIBRARY_ROOT PASW_REPOSITORY_ROOT

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
