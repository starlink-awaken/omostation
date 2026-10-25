#!/usr/bin/env bash
# resident-role-tick wrapper (ADR-0435 模式角色 jobs 修复, 2026-09-08).
#
# com.l4.resident.<role> 的 launchd plist 由生成器组合出
#   uv <omo-dir> resident <role> --once
# 自创建起从未生效 (缺 `run` 动词; 且角色模块不接受 --once)。
# 与 event-ingest 修复 (ADR-0453) 同一模式: tracked wrapper 表达可运行形态。
#
# 两种角色形态:
#   tick 型  (sediment/decision/execute/monitor/heartbeat):
#     uv run --project <omo> python -m omo.resident.cli daemon --once --role <role>
#   直调型  (signals/inbox/promote):
#     uv run --project <omo> python -m omo.resident.cli <sub>
#
# ADR-0456 B4b: 项目根由脚本自身位置推导 (BASH_SOURCE), 不写死检出根 ——
# 检出根与安装位两份拷贝因此逐字节相同, 各自跑各自根下的 projects/omo;
# E6 (kernel_root_pins) 才不会判 pinned_other_root。
set -euo pipefail

ROLE="${1:-}"
if [[ -z "$ROLE" ]]; then
  echo "usage: $0 <role>" >&2
  exit 1
fi

# 仓库根 = 本脚本所在 lib/ 的上一级 (安装位与检出根各自自推, 互不引用)
_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_SELF_DIR/.." && pwd)"
OMO_PROJECT="$_REPO_ROOT/projects/omo"

case "$ROLE" in
  sediment|decision|execute|monitor|heartbeat)
    exec /opt/homebrew/bin/uv run --project "$OMO_PROJECT" \
      python -m omo.resident.cli daemon --once --role "$ROLE"
    ;;
  signals|inbox|promote)
    exec /opt/homebrew/bin/uv run --project "$OMO_PROJECT" \
      python -m omo.resident.cli "$ROLE"
    ;;
  *)
    echo "unknown role: $ROLE (可用: sediment/decision/execute/monitor/heartbeat/signals/inbox/promote)" >&2
    exit 1
    ;;
esac
