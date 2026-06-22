#!/usr/bin/env bash
# mof-fix-cross-project.sh - 跨子项目并发 lint 修复 (P44 R0)
#
# 对多个子项目并发跑 ruff --fix, 解决 P43 R4 那种跨项目 lint 漂移.
#
# 用法:
#   ./bin/mof-fix-cross-project.sh              默认 8 个子项目
#   ./bin/mof-fix-cross-project.sh --list        列出子项目
#   ./bin/mof-fix-cross-project.sh --dry-run     只 print, 不跑
#   ./bin/mof-fix-cross-project.sh --unsafe      也跑 --unsafe-fixes
#   ./bin/mof-fix-cross-project.sh --seq         串行 (默认并发)
#   ./bin/mof-fix-cross-project.sh proj1 proj2 ...  指定子项目
#
# 默认列表: kairon cockpit runtime omo metaos aetherforge c2g ecos
# 排除 aetherforge 的 _legacy/ (X1-ARCH-MERGE-LLMGATEWAY-20260616 策略)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ALL_PROJECTS=(kairon cockpit runtime omo metaos aetherforge c2g ecos)

UNSAFE="false"
DRY_RUN="false"
MODE="parallel"
SELECTED=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)
      printf '%s\n' "${ALL_PROJECTS[@]}"
      exit 0
      ;;
    --dry-run)   DRY_RUN="true" ;;
    --seq)       MODE="sequential" ;;
    --parallel)  MODE="parallel" ;;
    --unsafe)    UNSAFE="true" ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    -*) echo "Unknown arg: $1" >&2; exit 1 ;;
    *)  SELECTED+=("$1") ;;
  esac
  shift
done

if [[ ${#SELECTED[@]} -eq 0 ]]; then
  SELECTED=("${ALL_PROJECTS[@]}")
fi

run_fix() {
  local proj="$1"
  local proj_dir="$WORKSPACE_ROOT/projects/$proj"
  if [[ ! -d "$proj_dir" ]]; then
    echo "  SKIP $proj: directory missing"
    return 0
  fi

  local ruff_args=("check" "src/")
  if [[ "$proj" == "aetherforge" ]]; then
    ruff_args=("check" "src/" "packages/gateway/src" "packages/gateway/src/llm_gateway" "--exclude" "packages/gateway/src/llm_gateway/_legacy")
  elif [[ "$proj" == "kairon" ]]; then
    ruff_args=("check" "packages/")
  fi

  local extra_args=()
  if [[ "$UNSAFE" == "true" ]]; then
    extra_args+=("--unsafe-fixes")
  fi

  echo "  FIX $proj: ruff ${ruff_args[*]}"
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi
  (cd "$proj_dir" && uv run ruff check "${ruff_args[@]}" --fix "${extra_args[@]}" > /tmp/mof-fix-$proj.log 2>&1) || true
  echo "    log: /tmp/mof-fix-$proj.log"
}

echo "=== mof-fix-cross-project ==="
echo "  Mode: $MODE"
echo "  Unsafe: $UNSAFE"
echo "  Dry-run: $DRY_RUN"
echo "  Projects: ${SELECTED[*]}"
echo

if [[ "$MODE" == "parallel" ]]; then
  PIDS=()
  for proj in "${SELECTED[@]}"; do
    run_fix "$proj" &
    PIDS+=($!)
  done
  for pid in "${PIDS[@]}"; do
    wait "$pid" || true
  done
else
  for proj in "${SELECTED[@]}"; do
    run_fix "$proj"
  done
fi

echo
echo "=== verify ==="
for proj in "${SELECTED[@]}"; do
  proj_dir="$WORKSPACE_ROOT/projects/$proj"
  [[ ! -d "$proj_dir" ]] && continue
  if [[ "$proj" == "kairon" ]]; then
    errs=$(cd "$proj_dir" && uv run ruff check packages/ --statistics 2>/dev/null | grep -E "^Found" | head -1)
  else
    errs=$(cd "$proj_dir" && uv run ruff check src/ --statistics 2>/dev/null | grep -E "^Found" | head -1)
  fi
  echo "  $proj: $errs"
done