#!/bin/bash
# eCOS Alert Notification — checks for issues and delivers alerts
# Usage: notify-alerts.sh [--deliver weixin]

set -e
cd "$(dirname "$0")/.."
SCRIPT_DIR="$(dirname "$0")"
ALERTS=""
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
DELIVER=""

if [ "$1" = "--deliver" ]; then
    DELIVER="$2"
fi

# Check 1: Services down
DOWN=$(PYTHONPATH=src python3 "$SCRIPT_DIR/check_services_down.py" 2>/dev/null || true)

# ─── Auto-heal attempt before alerting ─────────────────────────────────────
if [ -n "$DOWN" ]; then
    echo "[$NOW] Offline services detected — running auto-heal..."
    bash "$SCRIPT_DIR/autoheal.sh" 2>&1 || true
    # Re-check after auto-heal
    DOWN=$(PYTHONPATH=src python3 "$SCRIPT_DIR/check_services_down.py" 2>/dev/null || true)
fi

if [ -n "$DOWN" ]; then
    ALERTS="$ALERTS
## Services Down
$DOWN"
fi

# Check 2: Stale debts
STALE=$(PYTHONPATH=src python3 "$SCRIPT_DIR/check_stale_debts.py" 2>/dev/null || true)
if [ -n "$STALE" ]; then
    ALERTS="$ALERTS
## Stale Debt Items
$STALE"
fi

# Check 3: Freshness report
FRESH_REPORT="$HOME/runtime/reports/freshness-report-latest.md"
if [ -f "$FRESH_REPORT" ] && grep -q "ANCIENT" "$FRESH_REPORT" 2>/dev/null; then
    ALERTS="$ALERTS
## Ancient Items
Freshness report shows ancient items. Run: check_freshness_staleness.py"
fi

if [ -z "$ALERTS" ]; then
    echo "[$NOW] No alerts. All clear."
    exit 0
fi

BODY="eCOS Alert ($NOW)
$ALERTS"

if [ "$DELIVER" = "weixin" ]; then
    echo "$BODY" > /tmp/ecos-alert-latest.md
    echo "[$NOW] Alert queued for WeChat delivery"
else
    echo "[$NOW] Dry-run:"
    echo "$BODY"
fi
