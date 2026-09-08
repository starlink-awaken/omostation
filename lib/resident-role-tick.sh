#!/usr/bin/env bash
# resident-role-tick wrapper (ADR-0435 模式角色 jobs 修复, 2026-09-08).
#
# com.l4.resident.<role> 的 launchd plist 由生成器组合出
#   uv <omo-dir> resident <role> --once
# 自创建起从未生效 (缺 `run` 动词; 且角色模块不接受 --once)。
# 与 event-ingest 修复 (ADR-0435) 同一模式: tracked wrapper 表达可运行形态。
#
# 两种角色形态:
#   tick 型  (sediment/decision/execute/monitor/heartbeat):
#     uv run --project <omo> python -m omo.resident.cli daemon --once --role <role>
#   直调型  (signals/inbox/promote):
#     uv run --project <omo> python -m omo.resident.cli <sub>
set -euo pipefail

ROLE="${1:-}"
if [[ -z "$ROLE" ]]; then
  echo "usage: $0 <role>" >&2
  exit 1
fi

case "$ROLE" in
  sediment|decision|execute|monitor|heartbeat)
    exec /opt/homebrew/bin/uv run --project /Users/xiamingxing/Workspace/projects/omo \
      python -m omo.resident.cli daemon --once --role "$ROLE"
    ;;
  signals|inbox|promote)
    exec /opt/homebrew/bin/uv run --project /Users/xiamingxing/Workspace/projects/omo \
      python -m omo.resident.cli "$ROLE"
    ;;
  *)
    echo "unknown role: $ROLE (可用: sediment/decision/execute/monitor/heartbeat/signals/inbox/promote)" >&2
    exit 1
    ;;
esac
