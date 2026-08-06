#!/bin/bash
# install-launchd.sh — Install Agora launchd plists for crash recovery
# Run: bash scripts/install-launchd.sh

set -euo pipefail

AGORA_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH_DIR="$HOME/Library/LaunchAgents"
LOG_DIR="$HOME/.agora/logs"

mkdir -p "$LOG_DIR"

# ── SSE Server (:7431, requires --sse flag) ──
cat > "$LAUNCH_DIR/com.agora.sse.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.agora.sse</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/uv</string>
        <string>run</string>
        <string>--directory</string>
        <string>__AGORA_DIR__</string>
        <string>agora-mcp</string>
        <string>--sse</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/xiamingxing/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>WORKSPACE_HOME</key>
        <string>/Users/xiamingxing/Workspace</string>
        <key>AGORA_ADMISSION_MODE</key>
        <string>degraded</string>
        <key>AGORA_DATA_DIR</key>
        <string>__LOG_DIR__</string>
        <key>AGORA_AUTH_MODE</key>
        <string>permissive</string>
    </dict>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>__LOG_DIR__/sse-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>__LOG_DIR__/sse-stderr.log</string>
    <key>Nice</key>
    <integer>-5</integer>
</dict>
</plist>
PLIST

# ── Gateway (:7422) ──
cat > "$LAUNCH_DIR/com.agora.gateway.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.agora.gateway</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/uv</string>
        <string>run</string>
        <string>--directory</string>
        <string>__AGORA_DIR__</string>
        <string>python</string>
        <string>-m</string>
        <string>agora.auth.mcp_gateway</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/xiamingxing/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>WORKSPACE_HOME</key>
        <string>/Users/xiamingxing/Workspace</string>
        <key>AGORA_ADMISSION_MODE</key>
        <string>degraded</string>
        <key>AGORA_DATA_DIR</key>
        <string>__LOG_DIR__</string>
    </dict>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>__LOG_DIR__/gateway-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>__LOG_DIR__/gateway-stderr.log</string>
</dict>
</plist>
PLIST

# Substitute placeholders
sed -i '' "s|__AGORA_DIR__|$AGORA_DIR|g" "$LAUNCH_DIR/com.agora.sse.plist"
sed -i '' "s|__LOG_DIR__|$LOG_DIR|g" "$LAUNCH_DIR/com.agora.sse.plist"

sed -i '' "s|__AGORA_DIR__|$AGORA_DIR|g" "$LAUNCH_DIR/com.agora.gateway.plist"
sed -i '' "s|__LOG_DIR__|$LOG_DIR|g" "$LAUNCH_DIR/com.agora.gateway.plist"

# Load (unload first to avoid duplicates)
launchctl unload "$LAUNCH_DIR/com.agora.sse.plist" 2>/dev/null || true
launchctl unload "$LAUNCH_DIR/com.agora.gateway.plist" 2>/dev/null || true
launchctl load "$LAUNCH_DIR/com.agora.sse.plist"
launchctl load "$LAUNCH_DIR/com.agora.gateway.plist"

echo "✅ Agora launchd services installed:"
launchctl list | grep com.agora
