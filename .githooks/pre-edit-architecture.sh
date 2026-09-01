#!/bin/bash
# pre-edit-architecture.sh — 架构感知预编辑钩子
#
# 用途: 在 Agent 编辑架构相关文件前，自动检查合规性
# 触发: 编辑 docs/scene-cards/、docs/journey-specs/、.omo/standards/、bin/harness 时
#
# 安装: 由 .githooks/pre-commit 调用，或手动 pre-edit 触发
# 新 clone: make install-hooks 自动生效

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PY_RUNTIME="$ROOT/bin/gac/managed-python"

run_py() {
  "$PY_RUNTIME" run --profile stdlib -- "$@"
}

run_py_with_yaml() {
  "$PY_RUNTIME" run --profile pyyaml -- "$@"
}

# ── 参数: 待编辑文件列表 ──
EDIT_FILES="${@:-$(git diff --cached --name-only 2>/dev/null || true)}"

if [ -z "$EDIT_FILES" ]; then
  exit 0
fi

ARCHITECTURE_REGISTRY="$ROOT/.omo/_truth/registry/architecture-perception-registry.yaml"

if [ ! -f "$ARCHITECTURE_REGISTRY" ]; then
  echo "[pre-edit] ⚠️ 架构感知注册中心不存在，跳过检查" >&2
  exit 0
fi

echo "[pre-edit] 🔍 架构感知预编辑检查 (文件数: $(echo "$EDIT_FILES" | wc -l))" >&2

# ── 场景卡生命周期检查 ──
check_scene_cards() {
  local files="$1"
  local scene_card_files
  scene_card_files=$(echo "$files" | grep -E '^docs/scene-cards/.*\.yaml$' || true)

  if [ -z "$scene_card_files" ]; then
    return 0
  fi

  echo "[pre-edit] 📋 场景卡编辑检测，运行生命周期校验..." >&2

  for f in $scene_card_files; do
    if [ ! -f "$ROOT/$f" ]; then
      continue
    fi

    # 检查 lifecycle 字段
    if ! grep -q "lifecycle:" "$ROOT/$f" 2>/dev/null; then
      echo "[pre-edit] ❌ $f: 缺少 lifecycle 字段" >&2
      return 1
    fi

    # 检查 domain 字段
    if ! grep -q "domain:" "$ROOT/$f" 2>/dev/null; then
      echo "[pre-edit] ❌ $f: 缺少 domain 字段 (必填: work/health/research/knowledge/governance)" >&2
      return 1
    fi

    # 检查 promotion_evidence (assisted/supervised/routine 必须)
    local lifecycle
    lifecycle=$(grep "lifecycle:" "$ROOT/$f" | head -1 | sed 's/.*lifecycle: *//')
    case "$lifecycle" in
      assisted|supervised|routine)
        if ! grep -q "promotion_evidence:" "$ROOT/$f" 2>/dev/null; then
          echo "[pre-edit] ❌ $f: lifecycle=$lifecycle 必须包含 promotion_evidence" >&2
          return 1
        fi
        ;;
    esac
  done

  echo "[pre-edit] ✅ 场景卡生命周期检查通过" >&2
}

# ── Journey 规范检查 ──
check_journey_specs() {
  local files="$1"
  local journey_files
  journey_files=$(echo "$files" | grep -E '^docs/journey-specs/.*\.yaml$' || true)

  if [ -z "$journey_files" ]; then
    return 0
  fi

  echo "[pre-edit] 🗺️ Journey 规范编辑检测，运行状态机校验..." >&2

  for f in $journey_files; do
    if [ ! -f "$ROOT/$f" ]; then
      continue
    fi

    # 检查 states 字段
    if ! grep -q "states:" "$ROOT/$f" 2>/dev/null; then
      echo "[pre-edit] ❌ $f: 缺少 states 字段 (Journey 状态机定义)" >&2
      return 1
    fi

    # 检查 initial_state
    if ! grep -q "initial_state:" "$ROOT/$f" 2>/dev/null; then
      echo "[pre-edit] ❌ $f: 缺少 initial_state 字段" >&2
      return 1
    fi
  done

  echo "[pre-edit] ✅ Journey 规范检查通过" >&2
}

# ── 架构标准一致性检查 ──
check_standards() {
  local files="$1"
  local std_files
  std_files=$(echo "$files" | grep -E '^\.omo/standards/.*\.yaml$' || true)

  if [ -z "$std_files" ]; then
    return 0
  fi

  echo "[pre-edit] 📐 架构标准编辑检测，运行一致性校验..." >&2

  # 运行 architecture-check.py
  if [ -f "$ROOT/bin/gac/architecture-check.py" ]; then
    run_py "$ROOT/bin/gac/architecture-check.py" 2>&1 | sed 's/^/[pre-edit] /' >&2 || {
      echo "[pre-edit] ❌ 架构标准一致性检查失败" >&2
      return 1
    }
  fi

  echo "[pre-edit] ✅ 架构标准一致性检查通过" >&2
}

# ── Harness 策略合规检查 ──
check_harness() {
  local files="$1"
  local harness_files
  harness_files=$(echo "$files" | grep -E '^(bin/harness|\.omo/_truth/registry/harness-policy\.yaml)' || true)

  if [ -z "$harness_files" ]; then
    return 0
  fi

  echo "[pre-edit] 🎛️ Harness 编辑检测，运行合规校验..." >&2

  if [ -f "$ROOT/bin/gac/harness-compliance-check.py" ]; then
    run_py "$ROOT/bin/gac/harness-compliance-check.py" 2>&1 | sed 's/^/[pre-edit] /' >&2 || {
      echo "[pre-edit] ❌ Harness 合规检查失败" >&2
      return 1
    }
  fi

  echo "[pre-edit] ✅ Harness 合规检查通过" >&2
}

# ── 执行检查 ──
RC=0

check_scene_cards "$EDIT_FILES" || RC=1
check_journey_specs "$EDIT_FILES" || RC=1
check_standards "$EDIT_FILES" || RC=1
check_harness "$EDIT_FILES" || RC=1

if [ "$RC" -eq 0 ]; then
  echo "[pre-edit] ✅ 架构感知预编辑检查全部通过" >&2
else
  echo "[pre-edit] ⛔ 架构感知预编辑检查失败 — 请修复后重试" >&2
fi

exit $RC
