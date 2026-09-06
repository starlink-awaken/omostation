#!/bin/bash
# 本地 pre-commit 预检脚本 — 与 .githooks/pre-commit 完全对齐的手动执行版.
#
# 使用:
#   bash bin/gac/local-preflight.sh              # 完整检查
#   bash bin/gac/local-preflight.sh --quick      # 快速模式 (跳过慢检查)
#   bash bin/gac/local-preflight.sh --no-branch  # 跳过分支名检查
#
# 本脚本复制 .githooks/pre-commit 的全部检查项, 可独立运行.
# 用于: 手动验证、CI 独立执行、--no-verify 提交后的补救检查.

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
if [ -z "$ROOT" ]; then
  echo "❌ 不在 git 仓库内" >&2
  exit 1
fi

PY_RUNTIME="$ROOT/bin/gac/managed-python"
QUICK=0
NO_BRANCH=0

for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1 ;;
    --no-branch) NO_BRANCH=1 ;;
    --help|-h)
      echo "Usage: bash bin/gac/local-preflight.sh [--quick] [--no-branch]"
      echo "  --quick     跳过慢检查 (submodule 校验等)"
      echo "  --no-branch 跳过分支名检查"
      exit 0
      ;;
  esac
done

run_py() { "$PY_RUNTIME" run --profile stdlib -- "$@"; }
run_py_with_yaml() { "$PY_RUNTIME" run --profile pyyaml -- "$@"; }

echo "════════════════════════════════════════════════════"
echo "  Local Preflight — $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Quick=$QUICK  NoBranch=$NO_BRANCH"
echo "════════════════════════════════════════════════════"

FAILED=0

# ── 1. branch naming ────────────────────────────────────
if [ "$NO_BRANCH" -eq 0 ]; then
  echo ""
  echo "── Branch Naming ────────────────────────────────────"
  BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
  POLICY="$ROOT/.omo/_truth/registry/branch-prefix-policy.yaml"
  if [ "$BRANCH" != "main" ] && [ "$BRANCH" != "HEAD" ] && [ -n "$BRANCH" ] && [ -f "$POLICY" ]; then
    if run_py_with_yaml "$ROOT/bin/gac/check-branch-naming.py" --branch "$BRANCH" --policy "$POLICY" 2>&1; then
      echo "[branch-naming] ✅ 分支 '$BRANCH' 合规"
    else
      echo "[branch-naming] ❌ 分支 '$BRANCH' 不符合策略"
      FAILED=1
    fi
  else
    echo "[branch-naming] ⏭ 跳过 (当前: ${BRANCH:-detached})"
  fi
fi

# ── 2. runtime artifacts ───────────────────────────────
echo ""
echo "── Runtime Artifacts ───────────────────────────────"
if [ -f "$ROOT/bin/gac/check-runtime-artifacts.py" ]; then
  if run_py "$ROOT/bin/gac/check-runtime-artifacts.py" --staged 2>&1; then
    echo "[runtime-art] ✅ 无运行时产物违规"
  else
    echo "[runtime-art] ❌ 发现运行时产物被 staged"
    FAILED=1
  fi
else
  echo "[runtime-art] ⏭ 脚本不存在, 跳过"
fi

# ── 3. mass-deletion gate ──────────────────────────────
echo ""
echo "── Mass Deletion Gate ──────────────────────────────"
GATE="$ROOT/bin/gac/mass-deletion-gate.py"
if [ -f "$GATE" ]; then
  if run_py "$GATE" --staged 2>&1; then
    echo "[mass-del] ✅ 无大量删除"
  else
    echo "[mass-del] ❌ 检测到大量删除"
    FAILED=1
  fi
else
  echo "[mass-del] ⏭ 脚本不存在, 跳过"
fi

# ── 4. conflict markers ────────────────────────────────
echo ""
echo "── Conflict Markers ────────────────────────────────"
CONFLICT_CHECK="$ROOT/bin/ssot/conflict-marker-check.py"
if [ -f "$CONFLICT_CHECK" ]; then
  if run_py "$CONFLICT_CHECK" 2>&1; then
    echo "[conflict] ✅ 无冲突标记"
  else
    echo "[conflict] ❌ 发现未解决冲突标记"
    FAILED=1
  fi
else
  echo "[conflict] ⏭ 脚本不存在, 跳过"
fi

# ── 5. gitignore drift (advisory) ──────────────────────
echo ""
echo "── Gitignore Drift (advisory) ──────────────────────"
GITIGNORE_CHECK="$ROOT/bin/gac/check-gitignore-enforce.py"
if [ -f "$GITIGNORE_CHECK" ]; then
  if run_py "$GITIGNORE_CHECK" 2>&1; then
    echo "[gitignore] ✅ 无 gitignore 漂移"
  else
    echo "[gitignore] ⚠️ 发现漂移 (advisory, 不阻断)"
  fi
else
  echo "[gitignore] ⏭ 脚本不存在, 跳过"
fi

# ── 6. debt-guard ──────────────────────────────────────
echo ""
echo "── Debt Directory Guard ────────────────────────────"
if git status --short -- ".omo/debt/" 2>/dev/null | grep -q "^.D"; then
  echo "[debt-guard] ❌ .omo/debt/ 下有关联删除文件:"
  git status --short -- ".omo/debt/" | grep "^.D" | sed 's/^/[debt-guard]   /'
  FAILED=1
else
  echo "[debt-guard] ✅ 无债务文件删除"
fi

# ── 7. submodule guard (skip in quick mode) ────────────
if [ "$QUICK" -eq 0 ]; then
  echo ""
  echo "── Submodule Guard ─────────────────────────────────"
  if git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then
    echo "[submodule-guard] ⏭ merge commit, 跳过"
  elif [ -f "$ROOT/.gitmodules" ] && grep -q "path = " "$ROOT/.gitmodules" 2>/dev/null; then
    SUBMODULE_CHECK=$(grep 'path = ' "$ROOT/.gitmodules" | sed 's/.*path = //' | tr '\n' ' ')
    SUB_FAILED=0
    for sub in $SUBMODULE_CHECK; do
      if git diff --cached --name-only 2>/dev/null | grep -qxF "$sub"; then
        sub_path="$ROOT/$sub"
        if [ ! -f "$sub_path/.git" ] && [ ! -d "$sub_path/.git" ]; then
          echo "[submodule-guard] ❌ $sub 未初始化"
          SUB_FAILED=1
        else
          staged_sha=$(git ls-files --stage -- "$sub" | awk '$1 == "160000" {print $2}')
          base_sha=$(git rev-parse -q --verify "HEAD:$sub" 2>/dev/null || echo "")
          if [ -n "$base_sha" ] && [ -n "$staged_sha" ] && [ "$base_sha" != "$staged_sha" ]; then
            if ! (unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES; git -C "$sub_path" merge-base --is-ancestor "$base_sha" "$staged_sha") 2>/dev/null; then
              echo "[submodule-guard] ❌ $sub 不是 fast-forward"
              SUB_FAILED=1
            fi
          fi
        fi
      fi
    done
    if [ "$SUB_FAILED" -eq 0 ]; then
      echo "[submodule-guard] ✅ 所有子模块校验通过"
    else
      FAILED=1
    fi
  else
    echo "[submodule-guard] ⏭ 无 .gitmodules, 跳过"
  fi
else
  echo ""
  echo "── Submodule Guard ─────────────────────────────────"
  echo "[submodule-guard] ⏭ quick 模式, 跳过"
fi

# ── 8. result ──────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
if [ "$FAILED" -eq 0 ]; then
  echo "  ✅ 全部通过"
  echo "════════════════════════════════════════════════════"
  exit 0
else
  echo "  ❌ 存在失败项, 请修复后重试"
  echo "════════════════════════════════════════════════════"
  exit 1
fi
