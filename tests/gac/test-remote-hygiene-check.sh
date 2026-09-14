#!/bin/bash
# test-remote-hygiene-check.sh — remote-hygiene-check.py 强化回归 (2026-09-13)
#
# 实证污染事故: origin 被并发会话改写为 omostation-runtime, push URL 可被
# 单独改写. 校验矩阵:
# 1. fetch URL 污染 → exit 1
# 2. 仅 push URL 污染 (fetch 干净) → exit 1
# 3. fetch+push 均正确 (SSH/HTTPS 等价) → exit 0
# 4. 子模块 URL 与 .gitmodules 不符 → exit 1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="$SCRIPT_DIR/../../bin/gac/remote-hygiene-check.py"
CANONICAL="https://github.com/starlink-awaken/omostation.git"

PASS=0
FAIL=0

assert_exit() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  ✅ $label"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $label: expected exit $expected, got $actual"
    FAIL=$((FAIL + 1))
  fi
}

assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [ "$expected" = "$actual" ]; then
    echo "  ✅ $label"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $label: expected '$expected', got '$actual'"
    FAIL=$((FAIL + 1))
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 准备带 .gitmodules 的最小主仓 (无真实子仓, 子仓路径缺目录时 check 跳过)
git init -q "$TMP/repo"
cd "$TMP/repo"
git config user.email t@t
git config user.name t
cat > .gitmodules <<'EOF'
[submodule "projects/omo"]
	path = projects/omo
	url = https://github.com/starlink-awaken/omostation-omo.git
EOF
mkdir -p projects
git add .gitmodules
git commit -qm init
git remote add origin "$CANONICAL"

# 1. fetch URL 污染
git remote set-url origin https://github.com/starlink-awaken/omostation-runtime.git
rc=0; python3 "$CHECK" >/dev/null 2>&1 || rc=$?
assert_exit "fetch URL 污染 → fail" 1 $rc

# 2. 仅 push URL 污染 (fetch 干净)
git remote set-url origin "$CANONICAL"
git remote set-url --push origin https://github.com/starlink-awaken/omostation-runtime.git
rc=0; python3 "$CHECK" >/dev/null 2>&1 || rc=$?
assert_exit "仅 push URL 污染 → fail" 1 $rc

# 3. SSH/HTTPS 等价 → pass
git remote set-url --push origin git@github.com:starlink-awaken/omostation.git
rc=0; python3 "$CHECK" >/dev/null 2>&1 || rc=$?
assert_exit "SSH 等价 HTTPS → pass" 0 $rc

# 4. 子模块 URL 与 .gitmodules 不符 → fail
git remote set-url --push origin "$CANONICAL"
mkdir -p projects/omo
git -C projects/omo init -q
git -C projects/omo remote add origin https://github.com/starlink-awaken/omostation-runtime.git
rc=0; python3 "$CHECK" >/dev/null 2>&1 || rc=$?
assert_exit "子模块 URL 污染 → fail" 1 $rc

# 5. 未初始化子模块 (有目录无 .git) → 不误报 (git -C 向上解析防护)
rm -rf projects/omo
mkdir -p projects/runtime
rc=0; python3 "$CHECK" >/dev/null 2>&1 || rc=$?
assert_exit "未初始化子模块目录 → pass (不误报)" 0 $rc

# 6. fix-remotes.py 安全性: 未初始化子模块存在时不得改写主仓 origin
ROOT_WS="$PWD"
python3 "$SCRIPT_DIR/../../bin/ssot/fix-remotes.py" >/dev/null 2>&1
assert_eq "fix-remotes 不写穿未初始化子模块" "$CANONICAL" "$(git -C "$ROOT_WS" remote get-url origin)"

echo "── $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
