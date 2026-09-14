#!/usr/bin/env bash
# architecture-health-weekly.sh — 跑 arch-health-meter 并写周报到 docs/reports/
# (BET-Y1Q4-T6-18)
#
# 用法:
#   bash bin/ops/architecture-health-weekly.sh
#
# 周报输出:
#   docs/reports/architecture-health-weekly.md
#   docs/reports/architecture-health-weekly-<date>.md (snapshot)
#
# 调度 (人工, 不自动注册):
#   launchd snippet: bin/ops/launchd/com.omostation.arch-health-weekly.plist

set -euo pipefail

WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPORT_DIR="$WS/docs/reports"
LIVE="$REPORT_DIR/architecture-health-weekly.md"
SNAPSHOT="$REPORT_DIR/architecture-health-weekly-$(date -u +%Y%m%d).md"

mkdir -p "$REPORT_DIR"

echo "Collecting 6-dim architecture health..."
RAW=$(python3 "$WS/bin/arch-health-meter.py" --week 2>/dev/null) || {
    echo "ERROR: arch-health-meter failed" >&2
    exit 1
}

{
    echo "# 架构健康度 6 维度周报"
    echo
    echo "> 自动生成: \`bash bin/ops/architecture-health-weekly.sh\` (T6-18)"
    echo
    echo "$RAW"
} > "$LIVE"

cp "$LIVE" "$SNAPSHOT"

echo "✅ Wrote $LIVE"
echo "📸 Snapshot: $SNAPSHOT"
