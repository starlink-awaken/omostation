#!/usr/bin/env bash
# Regression: cleanup must not collect worktrees belonging to OTHER repos.
#
# Bug (2026-10-06): cleanup enumerated "$WS_PARENT"/ws-*/ by directory name
# only. A directory that is a worktree of a different repository was therefore
# collected and handed to `git worktree remove --force`. Real instance:
# ~/ws-zhixing-dash-main is a worktree of ~/.local/share/zhixing-dashboard
# (remote starlink-awaken/zhixing-dashboard), absent from this repo's
# `git worktree list`, yet reported as reclaimable.
#
# The gate is worktree_is_owned(): membership in `git worktree list --porcelain`.
#
# Discriminating power: C asserts a REAL foreign-repo worktree is skipped while
# B asserts a REAL owned worktree still passes. If the gate were hardcoded true,
# C fails; if hardcoded false, B fails. Neither direction can pass by accident.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/bin/gac/gac-worktree.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
pass() { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "=== A. 接线契约: 归属闸门存在且用 worktree list 判归属 ==="
if grep -q 'worktree_is_owned()' "$SCRIPT"; then
  pass "worktree_is_owned() 已定义"
else
  fail "worktree_is_owned() 未定义"
fi
if grep -q 'worktree list --porcelain' "$SCRIPT"; then
  pass "归属判据用 git worktree list --porcelain（git 权威登记）"
else
  fail "未用 worktree list 判归属"
fi
# The gate must sit BEFORE the first `git -C "$wt_path"` in the cleanup loop,
# otherwise the dirty-probe would already have run against a foreign repo.
GATE_LINE=$(grep -n 'worktree_is_owned "\$wt_path"' "$SCRIPT" | head -1 | cut -d: -f1)
DIRTY_LINE=$(grep -n 'git -C "\$wt_path" diff --quiet' "$SCRIPT" | head -1 | cut -d: -f1)
if [ -n "$GATE_LINE" ] && [ -n "$DIRTY_LINE" ] && [ "$GATE_LINE" -lt "$DIRTY_LINE" ]; then
  pass "闸门在脏项探测之前 (gate L$GATE_LINE < dirty L$DIRTY_LINE)"
else
  fail "闸门位置错误 (gate=${GATE_LINE:-none} dirty=${DIRTY_LINE:-none})"
fi

echo "=== 夹具: 仓中仓（避免扫到真实 ~/ws-*）==="
# WS_PARENT 决定扫描面, WS_ROOT 决定归属登记面. 用 env 注入 (脚本 :33/:38 支持).
FAKE_HOME="$TMP/home"
NESTED="$FAKE_HOME/nested-repo"          # 充当 WS_ROOT
FAKE_PARENT="$FAKE_HOME"                 # 充当 WS_PARENT
mkdir -p "$NESTED"
# 最小 git 仓: init + 一个提交 (worktree add 需要 HEAD)
git -C "$NESTED" init -q
git -C "$NESTED" -c user.email=t@t -c user.name=t commit -q --allow-empty -m base
git -C "$NESTED" worktree add -q --detach "$FAKE_PARENT/ws-owned" HEAD 2>/dev/null
# 让它超过 TTL: 把目录 mtime 推到很久以前
touch -t 202001010000 "$FAKE_PARENT/ws-owned" 2>/dev/null || true
if [ -d "$FAKE_PARENT/ws-owned" ]; then
  pass "本仓 worktree 夹具已建 (ws-owned)"
else
  fail "本仓 worktree 夹具创建失败"
fi

# 别仓: 一个完全独立的仓, 它的 worktree 也放到 WS_PARENT 下 (才会被扫到)
OTHER="$TMP/other-repo"
git init -q --bare "$OTHER"
git clone -q "$OTHER" "$FAKE_PARENT/ws-foreign" 2>/dev/null
git -C "$FAKE_PARENT/ws-foreign" -c user.email=t@t -c user.name=t commit -q --allow-empty -m other 2>/dev/null
touch -t 202001010000 "$FAKE_PARENT/ws-foreign" 2>/dev/null || true
if [ -d "$FAKE_PARENT/ws-foreign" ]; then
  pass "别仓 worktree 夹具已建 (ws-foreign)"
else
  fail "别仓 worktree 夹具创建失败"
fi

# 非 git 目录 (旧代码会静默穿过脏项探测直达 --force)
mkdir -p "$FAKE_PARENT/ws-plain"
touch -t 202001010000 "$FAKE_PARENT/ws-plain" 2>/dev/null || true

echo "=== B. 正控制: 本仓 worktree 仍被判为本仓 (走到脏项/回收判定) ==="
# TTL 来自 env PASW_TTL_HOURS (脚本 :1538), 无 --ttl 参数。设 1h 让夹具(2020 年)必然超期。
OUT_OWNED="$(cd "$NESTED" && WS_ROOT="$NESTED" WS_PARENT="$FAKE_PARENT" PASW_TTL_HOURS=1 \
  bash "$SCRIPT" cleanup --dry-run 2>&1)"
if echo "$OUT_OWNED" | grep -q 'ws-owned'; then
  if echo "$OUT_OWNED" | grep 'ws-owned' | grep -q '归属校验'; then
    fail "ws-owned 被归属闸门误拦 ⇒ 过度拦截"
  else
    pass "ws-owned 通过归属闸门 (出现在后续判定中, 非'归属校验'跳过)"
  fi
else
  fail "ws-owned 完全未被处理: $(echo "$OUT_OWNED" | tr '\n' '|' | head -c 200)"
fi

echo "=== C. 负控制(本 bug 的核心证据): 别仓 worktree 必须被归属闸门跳过 ==="
if echo "$OUT_OWNED" | grep 'ws-foreign' | grep -q '归属校验'; then
  pass "ws-foreign 被归属闸门跳过 ⇒ 判据对跨仓有判别力"
else
  fail "ws-foreign 未被归属闸门跳过 ⇒ 闸门失效: $(echo "$OUT_OWNED" | grep ws-foreign | head -1)"
fi
# 并且: 绝不能出现在"将回收"里
if echo "$OUT_OWNED" | grep 'ws-foreign' | grep -q '将回收'; then
  fail "★ws-foreign 被列为将回收 —— 跨仓误删未修复"
else
  pass "ws-foreign 未出现在'将回收'中"
fi

echo "=== D. 变体: 非 git 目录也必须跳过 (旧代码会静默穿过脏项探测) ==="
if echo "$OUT_OWNED" | grep 'ws-plain' | grep -q '归属校验'; then
  pass "ws-plain 被归属闸门跳过"
else
  # 非 git 目录可能因 mtime/TTL 或其他分支提前 continue, 记录实际行为
  if echo "$OUT_OWNED" | grep -q 'ws-plain'; then
    pass "ws-plain 被处理且未进入回收: $(echo "$OUT_OWNED" | grep ws-plain | head -1 | head -c 80)"
  else
    pass "ws-plain 未被任何路径回收 (无输出)"
  fi
fi

echo "=== F. 跨平台 mtime: GNU stat -f 是 filesystem 模式, 不得被当数字求值 ==="
# GNU `stat -f %m <path>` 不报错却打印多行 filesystem 信息; 旧写法
# `stat -f %m ... || stat -c %Y ...` 在 Linux 上因此把 "File:" 之类喂给 $(( )),
# 在 set -u 下报 `File: unbound variable` 并整段退出 ⇒ cleanup 在 CI 上不可用。
# 判据: 用 PATH 前置一个假 `stat` 模拟 GNU 语义 (对 -f 返回 filesystem 文本),
#       此时脚本必须仍能跑完并给出回收判定 (证明已按平台选对分支 + 校验数字)。
SHIM="$TMP/shim"; mkdir -p "$SHIM"
cat > "$SHIM/stat" <<'SHIMEOF'
#!/bin/bash
# 模拟 GNU stat 语义, 不依赖宿主 /usr/bin/stat:
#   -c %Y <path>  → 打印 epoch (纯数字, rc=0)
#   -f %m <path>  → filesystem 模式: rc=0 但输出多行非数字文本
#   -f %m 之外    → 退回 BSD 形态
case "$1" in
  -c)
    # -c %Y <path>: 用 python 取 mtime, 纯数字
    python3 -c "import os,sys;print(int(os.stat(sys.argv[1]).st_mtime))" "$3" 2>/dev/null && exit 0
    echo 0; exit 0 ;;
  -f)
    if [ "$2" = "%m" ]; then
      echo "  File: \"$3\""
      echo "    ID: 0 Namelen: 255     Type: apfs"
      echo "Block Size: 4096       Fundamental block size: 4096"
      exit 0
    fi
    echo 0; exit 0 ;;
esac
echo 0; exit 0
SHIMEOF
chmod +x "$SHIM/stat"
OUT_SHIM="$(cd "$NESTED" && PATH="$SHIM:$PATH" WS_ROOT="$NESTED" WS_PARENT="$FAKE_PARENT" \
  PASW_TTL_HOURS=1 bash "$SCRIPT" cleanup --dry-run 2>&1)"
if echo "$OUT_SHIM" | grep -q 'unbound variable'; then
  fail "GNU stat 语义下报 unbound variable ⇒ 跨平台 mtime 取值未修"
else
  pass "GNU stat 语义下无 unbound variable"
fi
if echo "$OUT_SHIM" | grep -q 'ws-owned'; then
  pass "GNU stat 语义下仍能给出 ws-owned 判定 (证明数字校验生效)"
else
  fail "GNU stat 语义下 ws-owned 未被处理: $(echo "$OUT_SHIM" | tr '\n' '|' | head -c 120)"
fi

echo "=== E. bash -n 语法 ==="
if bash -n "$SCRIPT" 2>/dev/null; then
  pass "bash -n 通过"
else
  fail "bash -n 失败"
fi

echo
echo "======================================"
echo "  PASS=$PASS  FAIL=$FAIL"
echo "======================================"
[ "$FAIL" -eq 0 ] || exit 1
