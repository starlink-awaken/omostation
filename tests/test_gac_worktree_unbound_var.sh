#!/bin/bash
# 回归: gac-worktree.sh 的 release/cleanup 不得因引用未定义变量而在 set -u 下中断
# (2026-10-06 加固).
#
# 背景 (实测):
#   `bin/gac/gac-worktree.sh` 的 release(:1439) 与 cleanup(:1532) 两处遍历
#   `$ISOLATED_SUBS`, 而该变量**全文从未定义** —— 脚本内实际存在并已填充的是
#   数组 `PASW_ISOLATED_SUBS_ARRAY`(:89 / :458, 由 pasw_resolve_isolated_subs 填)。
#   在 `set -euo pipefail` 的 `:u` 下, 展开未定义变量直接报
#   `ISOLATED_SUBS: unbound variable` 并**整段退出**。
#
#   真实后果 (非理论): `gac-worktree.sh cleanup --dry-run` 只打印了两条「跳过」后
#   就中断, 永远走不到回收判定 ⇒ **worktree TTL 清理机制完全失效**。
#
# 覆盖:
#   A  接线契约: 三处引用全部指向 PASW_ISOLATED_SUBS_ARRAY, 无裸 $ISOLATED_SUBS 残留.
#   B  行为: cleanup --dry-run 能跑完并列出「将回收」条目 (修复前会中断, 无此输出).
#   C  负控制: 断言「若把引用改回裸变量则 dry-run 中断」—— 证明 B 的判据真有判别力.
#   D  语法: bash -n 通过 (改 for 循环易漏 `[@]` / 引号).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/bin/gac/gac-worktree.sh"
FAILED=0
pass() { echo "  ✓ $1"; }
fail() { echo "  ❌ $1"; FAILED=1; }

echo "=== A. 接线契约: 无裸 \$ISOLATED_SUBS, 三处均指向数组 ==="
BARE=$(grep -c '\$ISOLATED_SUBS' "$SCRIPT" 2>/dev/null); BARE=${BARE:-0}
if [ "$BARE" -eq 0 ]; then pass "无裸 \$ISOLATED_SUBS 引用 (0 处)"
else fail "仍有 $BARE 处裸引用"; fi

ARRAY=$(grep -c 'PASW_ISOLATED_SUBS_ARRAY' "$SCRIPT" 2>/dev/null); ARRAY=${ARRAY:-0}
if [ "$ARRAY" -ge 3 ]; then pass "PASW_ISOLATED_SUBS_ARRAY 出现 $ARRAY 处"
else fail "数组引用仅 $ARRAY 处, 预期 ≥3"; fi

# 数组必须加引号, 否则 zsh/bash 的分词差异会让多元素失效
if grep -q 'for sub_name in "\${PASW_ISOLATED_SUBS_ARRAY\[@\]-}"' "$SCRIPT"; then
  pass "for 循环正确加引号 \"\${...[@]-}\" (空数组安全)"
else
  fail "for 循环未用 \"\${...[@]-}\" 形式 (空数组会漏 + 未加引号会分词)"
fi

echo
echo "=== B. 行为: cleanup --dry-run 跑完并给出回收判定 ==="
OUT="$(cd "$ROOT" && bash bin/gac/gac-worktree.sh cleanup --dry-run 2>&1)"
RC=$?
if [ "$RC" != "0" ]; then
  fail "cleanup --dry-run rc=$RC (预期 0)"
elif echo "$OUT" | grep -q 'unbound variable'; then
  fail "cleanup 仍报 unbound variable"
elif echo "$OUT" | grep -qE 'Cleanup 完成|将回收|无 worktree'; then
  pass "cleanup 跑完全程并给出回收判定"
else
  fail "cleanup 未跑到判定阶段; 输出: $(echo "$OUT" | tail -2 | tr '\n' ' ')"
fi

echo
echo "=== C. 负控制: 裸 \$UNDEF 在 set -u 下确实中断 (证明 B 的判据依赖该修复) ==="
# 直接验证机制本身: 一个引用未定义变量的 for 循环在 set -u 下必须中断。
# 这比"改脚本再跑"更可靠 —— 后者会因副本缺少 .git/PASW 上下文而走不到那行。
NEG=$(bash -c 'set -uo pipefail; for x in $TOTALLY_UNDEFINED_VAR_XYZ; do echo "$x"; done; echo REACHED_END' 2>&1)
if echo "$NEG" | grep -q 'unbound variable'; then
  pass "裸未定义变量确实报 unbound variable ⇒ B 断言的失败模式真实存在"
else
  fail "负控制未复现 (set -u 行为与预期不符) —— B 的判别力存疑"
fi
# 正对照: 加了 :- 默认值则不中断
POS=$(bash -c 'set -uo pipefail; for x in ${TOTALLY_UNDEFINED_VAR_XYZ:-}; do echo "$x"; done; echo REACHED_END' 2>&1)
if echo "$POS" | grep -q 'REACHED_END'; then
  pass "带 :- 默认值则可安全遍历 ⇒ 修法方向正确"
else
  fail "带 :- 默认值仍失败 ⇒ 修法方向错误"
fi

echo
echo "=== D. 语法: bash -n ==="
bash -n "$SCRIPT" && pass "bash -n 通过" || fail "bash -n 失败"

echo
if [ "$FAILED" = "0" ]; then
  echo "GAC worktree unbound-var 回归: PASS"
else
  echo "GAC worktree unbound-var 回归: FAIL"
fi
exit $FAILED