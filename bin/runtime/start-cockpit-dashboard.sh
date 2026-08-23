#!/usr/bin/env bash
# start-cockpit-dashboard.sh — launch the cockpit Web console in the background.
#
# Usage:
#   bash bin/runtime/start-cockpit-dashboard.sh              # start with default port
#   PORT=9000 bash bin/runtime/start-cockpit-dashboard.sh    # custom port
#   bash bin/runtime/start-cockpit-dashboard.sh stop        # stop the background instance
#   bash bin/runtime/start-cockpit-dashboard.sh status      # check if running
#
# Design notes:
#   - Forks the process; writes PID + log to runtime/cockpit-dashboard.{pid,log}.
#   - Idempotent: if a previous instance is alive, refuses to double-start.
#   - No background launchd dependency (those are user-specific). This script
#     is the minimal hand-on launcher; pair with `nohup ... &` for boot-time
#     auto-start (caller's responsibility).
#
# Exit codes:
#   0 = started (or already running) or stopped cleanly
#   1 = error (port busy, uv missing, etc.)
set -euo pipefail

WORKSPACE="${WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
RUNTIME_DIR="$WORKSPACE/runtime"
PID_FILE="$RUNTIME_DIR/cockpit-dashboard.pid"
LOG_FILE="$RUNTIME_DIR/cockpit-dashboard.log"
PORT="${PORT:-8090}"

mkdir -p "$RUNTIME_DIR"

# ----- subcommands ---------------------------------------------------------
cmd="${1:-start}"

is_alive() {
  [ -f "$PID_FILE" ] || return 1
  local pid
  pid=$(cat "$PID_FILE" 2>/dev/null || true)
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null
}

case "$cmd" in
  status)
    if is_alive; then
      echo "running (pid=$(cat "$PID_FILE"), port=$PORT, log=$LOG_FILE)"
      exit 0
    else
      echo "not running"
      exit 0
    fi
    ;;

  stop)
    if ! is_alive; then
      echo "not running (no live pid)"
      rm -f "$PID_FILE"
      exit 0
    fi
    pid=$(cat "$PID_FILE")
    echo "stopping pid=$pid"
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
      echo "force-killing pid=$pid"
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
    exit 0
    ;;

  start) ;;

  *)
    echo "usage: $0 {start|stop|status}" >&2
    exit 2
    ;;
esac

# ----- start path ----------------------------------------------------------
if is_alive; then
  echo "already running (pid=$(cat "$PID_FILE"))"
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv not in PATH" >&2
  exit 1
fi

# Check port availability (best-effort)
if command -v lsof >/dev/null 2>&1; then
  if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "error: port $PORT already in use" >&2
    exit 1
  fi
fi

# Double-fork so the process detaches from the controlling TTY. On Linux
# setsid gives the child its own process group; on macOS it's not present
# by default so we fall back to a nohup-only detach.
if command -v setsid >/dev/null 2>&1; then
  nohup setsid uv --project "$WORKSPACE/projects/cockpit" run cockpit-dashboard \
    > "$LOG_FILE" 2>&1 < /dev/null &
else
  nohup uv --project "$WORKSPACE/projects/cockpit" run cockpit-dashboard \
    > "$LOG_FILE" 2>&1 < /dev/null &
fi
echo $! > "$PID_FILE"
disown || true

# Give uvicorn a moment to bind; if the child dies quickly, surface the log.
sleep 1
if ! is_alive; then
  echo "error: cockpit-dashboard failed to start; tail of $LOG_FILE:" >&2
  tail -n 20 "$LOG_FILE" >&2 || true
  rm -f "$PID_FILE"
  exit 1
fi

echo "started (pid=$(cat "$PID_FILE"), port=$PORT, log=$LOG_FILE)"
echo "tail -f $LOG_FILE  # to follow logs"
echo "open http://127.0.0.1:$PORT  # to use the dashboard"
exit 0