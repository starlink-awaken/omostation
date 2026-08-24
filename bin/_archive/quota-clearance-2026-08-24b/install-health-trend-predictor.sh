#!/bin/bash
# install-health-trend-predictor.sh — Install launchd plist for health trend predictor

set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.omostation.health-trend-predictor.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Installing health-trend-predictor launchd service..."
echo "=================================================="

# Copy plist
cp "$REPO_ROOT/bin/gac/health-trend-predictor.plist" "$PLIST"
echo "✅ Copied plist to $PLIST"

# Load service
launchctl load "$PLIST" 2>/dev/null || echo "ℹ️  Service already loaded or failed to load"

echo ""
echo "Service installed. Status:"
launchctl list | grep health-trend-predictor || echo "  Not running (will start on next interval)"
echo ""
echo "Logs:"
echo "  tail -f /tmp/health-trend-predictor.log"
echo "  tail -f /tmp/health-trend-predictor.err"
echo ""
echo "To uninstall:"
echo "  launchctl uninstall com.omostation.health-trend-predictor && rm $PLIST"
