#!/usr/bin/env bash
# submodule-autobump.sh — 自动 bump 子模块指针到远端 main 的精确 SHA
#
# 合同 (contract):
#   C1  --check-only: exit 0 = 无待更新; exit 1 = 有待更新; exit 2 = 错误
#   C2  current == remote main → noop, 不动 index/HEAD
#   C3  仅当 current 是 remote main 的祖先时前进到远端精确 SHA (no-rewind)
#   C4  ahead / diverged / missing object → 拒绝, index 不变
#   C5  fetch 失败 → fail-closed (非零退出, index 不变)
#   C6  先全量验证所有子模块, 再一次性原子写入 index (无部分更新)
#   C7  任何失败 → 不 commit
#   C8  bot identity 由 workflow 在调用前 git config, 脚本不设置身份
#
# 用法:
#   bash bin/ssot/submodule-autobump.sh              # 验证全部通过后 bump + commit
#   bash bin/ssot/submodule-autobump.sh --check-only  # 只报告: 0=无更新 1=有更新 2=错误
#   bash bin/ssot/submodule-autobump.sh --dry-run    # 只显示将要做的修改

set -euo pipefail

DRY_RUN=false
CHECK_ONLY=false
case "${1:-}" in
  --dry-run) DRY_RUN=true ;;
  --check-only) CHECK_ONLY=true ;;
esac

WS_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
[ -z "$WS_ROOT" ] && { echo "❌ 不在 git 仓库" >&2; exit 2; }
cd "$WS_ROOT"

echo "=== Submodule Autobump $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

# .gitmodules 的 value 可以含空格。`git config -z` 每条输出为
# "key\nvalue\0"，不能用 whitespace split。
SUBMODULE_CONFIG="$(mktemp "${TMPDIR:-/tmp}/submodule-autobump.XXXXXX")"
trap 'rm -f "$SUBMODULE_CONFIG"' EXIT
[ -f .gitmodules ] || { echo "✅ 没有子模块"; exit 0; }
if ! git config --null --file .gitmodules --get-regexp '^submodule\..*\.path$' > "$SUBMODULE_CONFIG"; then
  echo "❌ 无法读取 .gitmodules, 拒绝 bump" >&2
  exit 2
fi
[ -s "$SUBMODULE_CONFIG" ] || { echo "✅ 没有子模块"; exit 0; }

errors=0
declare -a cand_subs
declare -a cand_shas
cand_subs=()
cand_shas=()

while IFS= read -r -d '' sub_entry; do
  sub="${sub_entry#*$'\n'}"
  if [ ! -e "$sub/.git" ]; then
    echo "❌ $sub: 子模块未初始化, 拒绝使用不完整状态" >&2
    errors=$((errors + 1))
    continue
  fi

  current_sha=$(git ls-files --stage -- "$sub" | awk '{print $2}')
  if [ -z "$current_sha" ]; then
    echo "❌ $sub: 无法读取当前 gitlink, 拒绝 bump" >&2
    errors=$((errors + 1))
    continue
  fi

  # C3/C5: 从远端权威 refs/heads/main 获得唯一的精确 SHA；绝不把
  # 旧的本地 origin/main 当作真相。随后 fetch main，并确认 fetched ref
  # 仍是同一个 SHA，避免远端在 check/apply 间发生静默漂移。
  remote_line_count=0
  latest_sha=""
  if ! remote_output=$(git -C "$sub" ls-remote origin refs/heads/main 2>/dev/null); then
    echo "❌ $sub: 查询远端 main 失败 (fail-closed)" >&2
    errors=$((errors + 1))
    continue
  fi
  while IFS=$'\t' read -r candidate_sha candidate_ref; do
    remote_line_count=$((remote_line_count + 1))
    if [ "$candidate_ref" = "refs/heads/main" ] \
      && printf '%s' "$candidate_sha" | grep -Eq '^[0-9a-f]{40}$'; then
      latest_sha="$candidate_sha"
    fi
  done <<EOF
$remote_output
EOF
  if [ "$remote_line_count" -ne 1 ] || [ -z "$latest_sha" ]; then
    echo "❌ $sub: 无法取得唯一合法的远端 main SHA (fail-closed)" >&2
    errors=$((errors + 1))
    continue
  fi

  if ! git -C "$sub" fetch origin 'refs/heads/main:refs/remotes/origin/main' >/dev/null 2>&1; then
    echo "❌ $sub: fetch origin main 失败 (fail-closed)" >&2
    errors=$((errors + 1))
    continue
  fi
  if ! fetched_sha=$(git -C "$sub" rev-parse --verify refs/remotes/origin/main 2>/dev/null); then
    echo "❌ $sub: fetch 后无法解析远端 main (fail-closed)" >&2
    errors=$((errors + 1))
    continue
  fi
  if [ "$fetched_sha" != "$latest_sha" ]; then
    echo "❌ $sub: 远端 main 在 fetch 期间变化, 拒绝非精确 bump" >&2
    errors=$((errors + 1))
    continue
  fi

  # C2: 相等 → noop
  if [ "$current_sha" = "$latest_sha" ]; then
    continue
  fi

  # C4: missing object — 远端 main 指向本地不可达的 commit → 拒绝
  if ! git -C "$sub" cat-file -e "$latest_sha^{commit}" 2>/dev/null; then
    echo "❌ $sub: 远端 main ($latest_sha) 对象缺失, 拒绝 bump" >&2
    errors=$((errors + 1))
    continue
  fi

  # C4: no-rewind — current 必须是 latest 的祖先, 否则 ahead/diverged → 拒绝
  if ! git -C "$sub" merge-base --is-ancestor "$current_sha" "$latest_sha" 2>/dev/null; then
    echo "❌ $sub: current ($current_sha) 不是远端 main ($latest_sha) 的祖先 (ahead/diverged), 拒绝 bump" >&2
    errors=$((errors + 1))
    continue
  fi

  cand_subs+=("$sub")
  cand_shas+=("$latest_sha")
  echo "🔄 $sub: ${current_sha:0:8} → ${latest_sha:0:8}"
done < "$SUBMODULE_CONFIG"

# C6/C7: 任一子模块验证失败 → 非零退出, 完全不碰 index
if [ "$errors" -gt 0 ]; then
  echo "❌ $errors 个子模块验证失败, 中止 (index 未修改)" >&2
  exit 2
fi

bumped=${#cand_subs[@]}
echo "---"
echo "需要 bump: $bumped 个子模块"

# C1: check-only 退出码 0/1/2; dry-run 只报告
if [ "$CHECK_ONLY" = true ]; then
  [ "$bumped" -gt 0 ] && exit 1
  exit 0
fi
if [ "$DRY_RUN" = true ] || [ "$bumped" -eq 0 ]; then
  exit 0
fi

# C6: 原子 index 更新 — 所有已验证的 gitlink 一次性喂给单个
# `git update-index -z --index-info`, Git 持锁后一次写入, 无部分更新.
{
  i=0
  while [ "$i" -lt "$bumped" ]; do
    printf '160000 %s\t%s\0' "${cand_shas[$i]}" "${cand_subs[$i]}"
    i=$((i + 1))
  done
} | git update-index -z --index-info

# C7: 只有全部成功才 commit (身份由 workflow 预先 git config, C8)
git commit -m "chore: auto-bump $bumped submodule pointers to latest main"
echo "✅ 已提交 bump"
exit 0
