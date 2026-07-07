#!/usr/bin/env bash
# install-foundry-cron.sh — P76 Phase 7.2
# 安装 foundry LaunchAgent (macOS) 或 systemd-timer (Linux).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

case "${1:-install}" in
  install)
    OS=$(uname)
    if [ "$OS" = "Darwin" ]; then
      PLIST_SRC="$SCRIPT_DIR/com.omostation.knowledge-foundry.plist"
      PLIST_DST="$HOME/Library/LaunchAgents/com.omostation.knowledge-foundry.plist"
      mkdir -p ~/.local/state/omostation
      echo "Installing LaunchAgent: $PLIST_DST (workspace=$WS_ROOT)"
      python3 -c "
import sys, pathlib
src = pathlib.Path(sys.argv[1]).read_text()
dst = pathlib.Path(sys.argv[2]).write_text(src.replace('/Users/xiamingxing/Workspace', sys.argv[3]))
" "$PLIST_SRC" "$PLIST_DST" "$WS_ROOT"
      launchctl unload "$PLIST_DST" 2>/dev/null || true
      launchctl load "$PLIST_DST"
      echo "✅ Loaded. Verify: launchctl list | grep omostation.knowledge-foundry"
    elif [ "$OS" = "Linux" ]; then
      SVC_SRC="$SCRIPT_DIR/systemd/omostation-knowledge-foundry.service"
      TMR_SRC="$SCRIPT_DIR/systemd/omostation-knowledge-foundry.timer"
      SVC_DST="/etc/systemd/system/omostation-knowledge-foundry.service"
      TMR_DST="/etc/systemd/system/omostation-knowledge-foundry.timer"
      [ -w /etc/systemd/system ] || { echo "❌ need root"; exit 1; }
      python3 -c "
import sys, pathlib
src = pathlib.Path(sys.argv[1]).read_text()
dst = pathlib.Path(sys.argv[2]).write_text(src.replace('/Users/xiamingxing/Workspace', sys.argv[3]))
" "$SVC_SRC" "$SVC_DST" "$WS_ROOT"
      cp "$TMR_SRC" "$TMR_DST"
      systemctl daemon-reload
      systemctl enable omostation-knowledge-foundry.timer
      systemctl start omostation-knowledge-foundry.timer
      echo "✅ Done."
    else
      echo "❌ unsupported OS: $OS"
      exit 1
    fi
    ;;
  uninstall)
    OS=$(uname)
    if [ "$OS" = "Darwin" ]; then
      PLIST="$HOME/Library/LaunchAgents/com.omostation.knowledge-foundry.plist"
      [ -f "$PLIST" ] && launchctl unload "$PLIST" 2>/dev/null
      rm -f "$PLIST"
      echo "✅ unloaded LaunchAgent"
    else
      systemctl disable omostation-knowledge-foundry.timer 2>/dev/null || true
      systemctl stop omostation-knowledge-foundry.timer 2>/dev/null || true
      rm -f /etc/systemd/system/omostation-knowledge-foundry.{service,timer}
      systemctl daemon-reload
      echo "✅ unloaded systemd-timer"
    fi
    ;;
  status)
    OS=$(uname)
    if [ "$OS" = "Darwin" ]; then
      launchctl list | grep omostation.knowledge-foundry || echo "(not loaded)"
    else
      systemctl status omostation-knowledge-foundry.timer 2>&1 | head -10
    fi
    ;;
  *)
    echo "Usage: $0 {install|uninstall|status}"
    exit 1
    ;;
esac
