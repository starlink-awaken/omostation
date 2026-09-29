#!/bin/bash
# 跑 tests/ 下的 shell 测试套件.
#
# 为什么需要它 (2026-09-29): 这些 shell 测试此前**没有任何执行入口** —— CI 不跑、pytest 不收集、
# Makefile 不调 ⇒ 它们只被人工或某个 BET 的验收命令唤起, 回归保护等于零 (实测 4 个早已变红却无人知).
#
# 用法:
#   bash tests/run-shell-suites.sh            # 跑全部「已纳入」套件 (CI 用这条)
#   bash tests/run-shell-suites.sh --list     # 列纳入/排除清单 (含原因)
#   RUN_SHELL_TESTS_ALL=1 bash tests/run-shell-suites.sh   # 连排除项一起跑 (本地排查)
#
# 纳入规则: tests/ 下所有 *.sh, **减去** tests/shell-suites.exclude 里列出的路径.
#   · 排除名单每行 `路径  # 原因`; runner 会校验该路径确实存在 ⇒ 名单不会腐烂 (改名/删除即报错).
#   · 新加的测试**默认即被纳入** ⇒ 不会再出现「无人执行的死测试」.
#   · 单测超时 (RUN_SHELL_TESTS_TIMEOUT, 默认 120s) 即判失败 ⇒ 过慢的测试会立刻暴露而非拖垮门禁.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
EXCLUDE_FILE="$ROOT/tests/shell-suites.exclude"
TIMEOUT="${RUN_SHELL_TESTS_TIMEOUT:-120}"

list_only=0
[ "${1:-}" = "--list" ] && list_only=1

# ── 收集 ────────────────────────────────────────────────────────────────
SELF_REL="tests/run-shell-suites.sh"   # 聚合器自身, 必须排除 (否则自递归)
mapfile -t ALL < <(find tests -name '*.sh' -not -path '*/_archive/*' | LC_ALL=C sort)
[ "${#ALL[@]}" -gt 0 ] || { echo "❌ tests/ 下没找到任何 *.sh" >&2; exit 1; }
_filtered=()
for _t in "${ALL[@]}"; do [ "$_t" = "$SELF_REL" ] || _filtered+=("$_t"); done
ALL=("${_filtered[@]}")

declare -A REASON=()
if [ -f "$EXCLUDE_FILE" ]; then
  while IFS= read -r line; do
    case "$line" in ''|'#'*) continue ;; esac
    path="${line%%#*}"
    reason="${line#*#}"
    path="$(printf '%s' "$path" | tr -d '[:space:]')"
    reason="$(printf '%s' "$reason" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')"
    [ -n "$path" ] || continue
    # 名单不腐烂: 排除项必须真实存在
    if [ ! -f "$path" ]; then
      echo "❌ 排除名单指向不存在的文件: $path (改名/删除后请同步 $EXCLUDE_FILE)" >&2
      exit 1
    fi
    REASON["$path"]="${reason:-未注明原因}"
  done < "$EXCLUDE_FILE"
fi

INCLUDED=()
EXCLUDED=()
for t in "${ALL[@]}"; do
  if [ -n "${REASON[$t]:-}" ]; then EXCLUDED+=("$t"); else INCLUDED+=("$t"); fi
done

if [ "$list_only" = "1" ] || [ "${RUN_SHELL_TESTS_ALL:-0}" = "1" ]; then
  echo "== 纳入 (${#INCLUDED[@]}) =="
  printf '   %s\n' "${INCLUDED[@]}"
  echo "== 排除 (${#EXCLUDED[@]}) =="
  for t in "${EXCLUDED[@]}"; do printf '   %-56s %s\n' "$t" "${REASON[$t]}"; done
  [ "$list_only" = "1" ] && exit 0
  INCLUDED=("${ALL[@]}")   # RUN_SHELL_TESTS_ALL: 连排除项一起跑
fi

# ── 执行 ────────────────────────────────────────────────────────────────
# 超时: macOS 无 `timeout`, 用 perl alarm (与 tests/test_gac_worktree_trap.sh 同法)
run_one() {
  local t="$1"
  local start end rc
  start=$(python3 -c 'import time;print(time.time())')
  perl -e 'alarm shift; exec @ARGV' "$TIMEOUT" bash "$t" >/tmp/shell-test-$$.out 2>&1
  rc=$?
  end=$(python3 -c 'import time;print(time.time())')
  printf '%6.1fs' "$(python3 -c "print($end-$start)")"
  if [ "$rc" -eq 0 ]; then
    echo "  ✅ $t"
  elif [ "$rc" -eq 142 ]; then
    echo "  ⏱  $t (超时 >${TIMEOUT}s)"
    tail -5 /tmp/shell-test-$$.out | sed 's/^/        /'
  else
    echo "  ❌ $t (exit=$rc)"
    tail -8 /tmp/shell-test-$$.out | sed 's/^/        /'
  fi
  return "$rc"
}

echo "=== shell 测试套件 (纳入 ${#INCLUDED[@]} / 排除 ${#EXCLUDED[@]}; 单测超时 ${TIMEOUT}s) ==="
failed=0
for t in "${INCLUDED[@]}"; do
  run_one "$t" || failed=$((failed + 1))
done
rm -f /tmp/shell-test-$$.out

echo ""
if [ "$failed" -eq 0 ]; then
  echo "✅ shell 测试全通过 (${#INCLUDED[@]} 个)"
  exit 0
fi
echo "❌ shell 测试失败 $failed / ${#INCLUDED[@]}"
exit 1
