#!/bin/bash
# install-launchd.sh — Install ecos BOS registry daemon for crash recovery
# Run: bash scripts/install-launchd.sh
#
# Wires:
#   L0/ecos/scripts/com.ecos.bos-registry-daemon.plist → ~/Library/LaunchAgents
# This daemon watches L0-constraints.yaml → auto-update routes.json

set -euo pipefail

ECOS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/.ecos/bos"
PLIST_NAME="com.ecos.bos-registry-daemon"

mkdir -p "$LOG_DIR"

PLIST_SRC="$ECOS_DIR/scripts/${PLIST_NAME}.plist"
PLIST_DST="$LAUNCH_DIR/${PLIST_NAME}.plist"

if [ ! -f "$PLIST_SRC" ]; then
    echo "❌ Source plist not found: $PLIST_SRC"
    exit 1
fi

# Substitute any future placeholders (none today, but keep pattern aligned with agora/install-launchd.sh)
sed "s|__ECOS_DIR__|$ECOS_DIR|g" "$PLIST_SRC" > "$PLIST_DST"
sed -i '' "s|__LOG_DIR__|$LOG_DIR|g" "$PLIST_DST"

# Load (unload first to avoid duplicates)
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl load "$PLIST_DST"

echo "✅ ecos BOS registry daemon installed:"
launchctl list | grep "$PLIST_NAME" || echo "  (load succeeded but not in launchctl list yet — may need a moment)"
echo ""
echo "Logs:    $LOG_DIR/daemon-stdout.log"
echo "Stderr:  $LOG_DIR/daemon-stderr.log"
echo "Status:  launchctl list | grep $PLIST_NAME"
