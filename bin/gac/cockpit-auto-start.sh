#!/bin/bash
# cockpit-auto-start.sh — Install/verify cockpit dashboard auto-start

set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.cockpit.dashboard.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "Cockpit Dashboard Auto-Start"
echo "=============================="

# Check if plist exists
if [ ! -f "$PLIST" ]; then
    echo "Creating plist: $PLIST"
    cat > "$PLIST" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cockpit.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/uv</string>
        <string>run</string>
        <string>--directory</string>
        <string>/Users/xiamingxing/Workspace/projects/cockpit</string>
        <string>python</string>
        <string>-m</string>
        <string>cockpit.cli</string>
        <string>dashboard</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</true>
    <false/>
    <key>StandardOutPath</key>
    <string>/tmp/cockpit-dashboard.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/cockpit-dashboard.err</string>
</dict>
</plist>
EOF
    echo "Created plist"
else
    echo "Plist exists: $PLIST"
    # Verify command
    if grep -q "cockpit.dashboard_server" "$PLIST"; then
        echo "WARNING: plist contains outdated command 'cockpit.dashboard_server'"
        echo "Run this script with --fix to update"
    fi
fi

# Load plist
echo "Loading plist..."
launchctl load "$PLIST" 2>/dev/null || echo "Already loaded or failed (may need --fix)"

echo "Done. Check status with: launchctl list | grep cockpit"
