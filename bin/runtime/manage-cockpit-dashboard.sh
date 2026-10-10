#!/usr/bin/env bash
# Manage the registered Cockpit Dashboard LaunchAgent.
set -euo pipefail

LABEL="${COCKPIT_DASHBOARD_LABEL:-com.cockpit.dashboard}"
PLIST="${COCKPIT_DASHBOARD_PLIST:-$HOME/Library/LaunchAgents/${LABEL}.plist}"
WORKSPACE_ROOT="${WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3}"
DOMAIN="gui/$(id -u)"
CMD="${1:-status}"

loaded() {
  launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1
}

case "$CMD" in
  start)
    if [[ ! -f "$PLIST" ]]; then
      echo "LaunchAgent plist not found: $PLIST" >&2
      exit 1
    fi
    if [[ ! -x "$PYTHON_BIN" ]]; then
      echo "Python executable not found: $PYTHON_BIN" >&2
      exit 1
    fi
    "$PYTHON_BIN" "$WORKSPACE_ROOT/bin/mof/gen-service-configs.py" \
      --check --service-id cockpit.dashboard
    if loaded; then
      launchctl kickstart "$DOMAIN/$LABEL"
    else
      launchctl bootstrap "$DOMAIN" "$PLIST"
      launchctl kickstart "$DOMAIN/$LABEL"
    fi
    echo "started $LABEL"
    ;;
  stop)
    if loaded; then
      launchctl bootout "$DOMAIN/$LABEL"
      echo "stopped $LABEL"
    else
      echo "$LABEL is not loaded"
    fi
    ;;
  status)
    if loaded; then
      launchctl print "$DOMAIN/$LABEL"
    else
      echo "$LABEL is not loaded"
      exit 1
    fi
    ;;
  *)
    echo "usage: $0 {start|stop|status}" >&2
    exit 2
    ;;
esac
