#!/usr/bin/env bash
set -euo pipefail
# 多仓库治理健康度审计编排器 (REPO-AUDIT-IMPLEMENTATION-PLAN.md)
# 只读: 不修改任何仓库状态

log() {
  local level="${1:-INFO}" msg="${2:-}"
  echo "[audit] ${level} ${msg}" >&2
}

enumerate_repos() {
  # 主仓库
  git remote get-url origin 2>/dev/null | sed -E 's#(https?://|git@|//)##; s#\.git$##; s#:#/#; s#^github\.com/##' | awk -F/ '{print $(NF-1)"/"$NF}'
  # 子模块
  git submodule status 2>/dev/null | awk '{print $2}' | while read -r sub; do
    git -C "$sub" remote get-url origin 2>/dev/null | sed -E 's#(https?://|git@|//)##; s#\.git$##; s#:#/#; s#^github\.com/##' | awk -F/ '{print $(NF-1)"/"$NF}'
  done
}
