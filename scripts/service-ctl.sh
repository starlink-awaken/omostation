#!/usr/bin/env bash
# =============================================================================
# Runtime Service Control — start/stop/restart/status for Runtime services
# Usage: bash ~/runtime/scripts/service-ctl.sh <service-name> <start|stop|restart|status>
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_HOME="${RUNTIME_HOME:-$HOME/runtime}"
source "$RUNTIME_HOME/config/env.sh" 2>/dev/null || true

show_usage() {
  echo "Usage: $(basename "$0") <service> <action>"
  echo ""
  echo "Services: hermes-gateway  agent-runtime  cron-service  ollama"
  echo "Actions:  start  stop  restart  status"
  echo ""
  echo "Docker services:"
  echo "  $(basename "$0") docker <container> <start|stop|restart|status>"
  echo "  e.g. $(basename "$0") docker gbrain-postgres status"
  echo ""
  echo "All services:"
  echo "  $(basename "$0") list"
  exit 1
}

# ─── launchd service map ────────────────────────────────────────────────────
# Format: service_name|launchd_label|port|workdir
LAUNCHD_SERVICES=(
  "hermes-gateway|ai.hermes.gateway|—|$HOME/.hermes/hermes-agent"
  "agent-runtime|com.agent-runtime|$AGENT_RUNTIME_PORT|$WORKSPACE_HOME/projects/cockpit"
  "cron-service|com.user.cron-service|$CRON_SERVICE_PORT|$WORKSPACE_HOME/projects/runtime"
  "ollama|ollama|$OLLAMA_PORT|—"
)

find_service() {
  local name="$1"
  for entry in "${LAUNCHD_SERVICES[@]}"; do
    local svc_name="${entry%%|*}"
    [[ "$svc_name" == "$name" ]] && { echo "$entry"; return 0; }
  done
  return 1
}

list_service_names() {
  local sep=""
  for entry in "${LAUNCHD_SERVICES[@]}"; do
    echo -n "$sep${entry%%|*}"
    sep=" "
  done
  echo
}

# Special: 'list' doesn't need a second arg
if [[ "${1:-}" == "list" ]]; then
  SERVICE_NAME="list"
  ACTION="list"
else
  [[ $# -lt 2 ]] && show_usage
  SERVICE_NAME="$1"
  ACTION="$2"
fi

case "$ACTION" in
  list)
    echo "Runtime services:"
    echo ""
    echo "── Launchd Services ──"
    for entry in "${LAUNCHD_SERVICES[@]}"; do
      svc_name="${entry%%|*}"
      rest="${entry#*|}"
      label="${rest%%|*}"
      pid=$(launchctl list "$label" 2>/dev/null | grep -o '"PID" = [0-9]*' | awk '{print $3}' || true)
      if [[ -n "$pid" && "$pid" != "0" ]]; then
        echo "  ✅ $svc_name (PID $pid)"
      else
        echo "  ❌ $svc_name"
      fi
    done
    echo ""
    echo "── Docker Services ──"
    for container in gbrain-postgres integration-agora-1 integration-sharedbrain-1 integration-agora-mcp-1; do
      s=$(docker ps --filter "name=$container" --format "{{.Status}}" 2>/dev/null || echo "")
      [[ -n "$s" ]] && echo "  ✅ $container ($s)" || echo "  ❌ $container (stopped)"
    done
    exit 0
    ;;
esac

# ─── Docker handling ────────────────────────────────────────────────────────
if [[ "$SERVICE_NAME" == "docker" ]]; then
  CONTAINER="$ACTION"
  DOCKER_ACTION="${3:-status}"
  case "$DOCKER_ACTION" in
    start)   echo "Starting $CONTAINER..." && docker start "$CONTAINER" ;;
    stop)    echo "Stopping $CONTAINER..." && docker stop "$CONTAINER" ;;
    restart) echo "Restarting $CONTAINER..." && docker restart "$CONTAINER" ;;
    status)
      s=$(docker ps --filter "name=$CONTAINER" --format "{{.Status}}" 2>/dev/null || echo "stopped")
      echo "$CONTAINER: $s"
      ;;
    *) echo "Unknown docker action: $DOCKER_ACTION"; exit 1 ;;
  esac
  exit 0
fi

# ─── launchd actions ────────────────────────────────────────────────────────
SERVICE_DATA=$(find_service "$SERVICE_NAME") || {
  echo "Unknown service: $SERVICE_NAME"
  echo "Available: $(list_service_names)"
  exit 1
}

IFS='|' read -r _ LABEL PORT WORKDIR <<< "$SERVICE_DATA"

case "$ACTION" in
  status)
    out=$(launchctl list "$LABEL" 2>/dev/null || echo "not found")
    pid=$(echo "$out" | grep -o '"PID" = [0-9]*' | awk '{print $3}' || true)
    exit_code=$(echo "$out" | grep -o '"LastExitStatus" = [0-9]*' | awk '{print $3}' || true)
    if [[ -n "$pid" && "$pid" != "0" ]]; then
      echo "✅ $SERVICE_NAME: running (PID $pid)"
      [[ "$PORT" != "—" ]] && echo "   Port $PORT: $(lsof -iTCP:$PORT -sTCP:LISTEN -P 2>/dev/null | grep -q LISTEN && echo 'listening' || echo 'closed' || true)"
    elif [[ "$exit_code" == "0" ]]; then
      echo "⏸  $SERVICE_NAME: idle (loaded, not running)"
    else
      echo "❌ $SERVICE_NAME: failed (exit=$exit_code)"
    fi
    ;;
  start)
    echo "Starting $SERVICE_NAME..."
    launchctl kickstart -kp "gui/$(id -u)/$LABEL" 2>/dev/null || true
    launchctl start "$LABEL" 2>/dev/null || true
    sleep 1
    pid=$(launchctl list "$LABEL" 2>/dev/null | grep -o '"PID" = [0-9]*' | awk '{print $3}' || true)
    if [[ -n "$pid" && "$pid" != "0" ]]; then
      echo "✅ $SERVICE_NAME started (PID $pid)"
    else
      echo "❌ $SERVICE_NAME failed to start — check launchctl list $LABEL"
    fi
    ;;
  stop)
    echo "Stopping $SERVICE_NAME..."
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || launchctl stop "$LABEL" 2>/dev/null || true
    echo "✅ $SERVICE_NAME stopped"
    ;;
  restart)
    echo "Restarting $SERVICE_NAME..."
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
    sleep 1
    launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$LABEL.plist" 2>/dev/null || \
      launchctl start "$LABEL" 2>/dev/null || true
    sleep 2
    pid=$(launchctl list "$LABEL" 2>/dev/null | grep -o '"PID" = [0-9]*' | awk '{print $3}' || true)
    [[ -n "$pid" && "$pid" != "0" ]] && echo "✅ $SERVICE_NAME restarted (PID $pid)" || echo "❌ $SERVICE_NAME restart failed"
    ;;
  *)
    echo "Unknown action: $ACTION"
    show_usage
    ;;
esac
