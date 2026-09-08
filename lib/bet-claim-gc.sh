#!/usr/bin/env bash
# bet-claim-gc wrapper (T10-140 迭代: T10-139 claim-gc 的调度补全).
#
# claim-bet 广播文件 7d TTL 自清理 — 过期视为放弃, 只删广播文件不动 ledger
# status (后续认领自然接管)。launchd com.l4.bet-claim-gc 每日触发。
# bet-ledger.py 需要 pyyaml, 走 uv (ADR-0435: uv-run 形态一律 wrapper)。
set -euo pipefail
exec /opt/homebrew/bin/uv run --with pyyaml \
  python /Users/xiamingxing/Workspace/bin/plan/bet-ledger.py claim-gc
