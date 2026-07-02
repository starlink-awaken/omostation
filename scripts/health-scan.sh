#!/usr/bin/env bash
# =============================================================================
# eCOS Health Scan — One-shot service health check
# Usage: bash ~/runtime/scripts/health-scan.sh [--json]
# Source: $RUNTIME_SCRIPTS/health-scan.sh
# Data:   reads service list from $RUNTIME_MATRIX
# =============================================================================

set -euo pipefail

# ─── Bootstrap — find our home ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_HOME="${RUNTIME_HOME:-$HOME/runtime}"
source "$RUNTIME_HOME/config/env.sh" 2>/dev/null || true

# ─── Utils ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

output_json="false"
[[ "${1:-}" == "--json" ]] && output_json="true"

# Read matrix.yaml (simple key=value parser for our inline config)
# We define services inline here; the matrix.yaml is SSOT for descriptions.
# In future, could parse with yq (brew install yq).

check_launchd() {
  local label="$1"
  local out
  out=$(launchctl list "$label" 2>/dev/null) || {
    echo "failed:unregistered"
    return 0
  }
  local pid exit_code
  pid=$(echo "$out" | grep -o '"PID" = [0-9]*' | awk '{print $3}' || true)
  exit_code=$(echo "$out" | grep -o '"LastExitStatus" = [0-9]*' | awk '{print $3}' || true)
  if [[ -n "$pid" && "$pid" != "0" ]]; then
    echo "running:$pid"
  elif [[ "$exit_code" == "0" ]]; then
    echo "idle"
  else
    echo "failed:$exit_code"
  fi
}

check_port() {
  local port="$1"
  lsof -iTCP:"$port" -sTCP:LISTEN -P 2>/dev/null | grep -q LISTEN && echo "listening" || echo "closed"
}

check_url() {
  local url="$1"
  curl -sf -o /dev/null --max-time 2 "$url" 2>/dev/null && echo "healthy" || echo "unreachable"
}

check_docker() {
  local name="$1"
  local status
  status=$(docker ps --filter "name=$name" --format "{{.Status}}" 2>/dev/null || echo "")
  if [[ -n "$status" ]]; then
    echo "running:$status"
  else
    echo "stopped"
  fi
}

# ─── Service Definitions ────────────────────────────────────────────────────
# name|type|launchd_label_or_docker|port_or_—|health_url_or_—
SERVICES=(
  "Hermes Gateway|l|ai.hermes.gateway|—|—"
  "Agent Runtime|l|com.agent-runtime|$AGENT_RUNTIME_PORT|http://127.0.0.1:$AGENT_RUNTIME_PORT/health"
  "Cron Service|l|com.user.cron-service|$CRON_SERVICE_PORT|http://127.0.0.1:$CRON_SERVICE_PORT/health"
  "Ollama|o|—|$OLLAMA_PORT|http://localhost:$OLLAMA_PORT/api/tags"
)

DOCKER_SERVICES=(
  "gbrain-postgres"
  "integration-sharedbrain-1"
)

# ─── JSON mode ──────────────────────────────────────────────────────────────
if [[ "$output_json" == "true" ]]; then
  echo "{"
  echo "  \"scan_time\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"runtime_home\": \"$RUNTIME_HOME\","
  echo "  \"services\": {"
  first=true
  for entry in "${SERVICES[@]}"; do
    IFS='|' read -r name type label_or_note <<< "$entry"
    IFS='|' read -r _ _ _ port url <<< "$entry"
    status=$(check_launchd "$label_or_note")
    port_status=""; [[ "$port" != "—" ]] && port_status=$(check_port "$port")
    url_status=""; [[ "$url" != "—" ]] && url_status=$(check_url "$url")
    $first || echo ","
    first=false
    echo -n "    \"$label_or_note\": {"
    echo -n "\"name\":\"$name\",\"status\":\"$status\""
    [[ -n "$port_status" ]] && echo -n ",\"port_${port}\":\"$port_status\""
    [[ -n "$url_status" ]] && echo -n ",\"health\":\"$url_status\""
    echo -n "}"
  done
  echo ""
  echo "  },"
  echo "  \"docker\": {"
  first=true
  for container in "${DOCKER_SERVICES[@]}"; do
    status=$(check_docker "$container")
    $first || echo ","
    first=false
    echo -n "    \"$container\": \"$status\""
  done
  echo ""
  echo "  }"
  echo "}"
  exit 0
fi

# ─── Terminal mode ──────────────────────────────────────────────────────────
echo "╔════════════════════════════════════════════════════════╗"
echo "║              eCOS Runtime — Health Scan               ║"
echo "║  $(date '+%Y-%m-%d %H:%M:%S')                         ║"
echo "║  MATRIX: $RUNTIME_MATRIX"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

echo "── Launchd Services ──"
printf "%-30s %-20s %-12s %s\n" "SERVICE" "STATUS" "PORT" "HEALTH"
echo "──────────────────────────────────────────────────────────────"
for entry in "${SERVICES[@]}"; do
  IFS='|' read -r name type label port url <<< "$entry"
  status=$(check_launchd "$label")
  port_status=""; [[ "$port" != "—" ]] && port_status=$(check_port "$port")
  url_status=""; [[ "$url" != "—" && "$url_status" != "healthy" ]] && url_status=$(check_url "$url")

  status_str=""
  color="$GREEN"
  if [[ "$status" == running:* ]]; then
    status_str="✅ ${status#running:}"
  elif [[ "$status" == "idle" ]]; then
    status_str="⏸  idle"
    color="$YELLOW"
  else
    status_str="❌ exit=${status#failed:}"
    color="$RED"
  fi

  port_str=""
  if [[ -n "$port_status" && "$port_status" == "listening" ]]; then
    port_str=":${port}✅"
  elif [[ -n "$port_status" ]]; then
    port_str=":${port}❌"
  fi

  health_str=""
  if [[ -n "$url_status" ]]; then
    [[ "$url_status" == "healthy" ]] && health_str="✅" || health_str="❌"
  fi

  printf "${color}%-30s${NC} %-20s %-12s %s\n" "$name" "$status_str" "$port_str" "$health_str"
done

echo ""
echo "── Docker Containers ──"
printf "%-35s %s\n" "CONTAINER" "STATUS"
echo "──────────────────────────────────────────────────────────────"
for container in "${DOCKER_SERVICES[@]}"; do
  status=$(check_docker "$container")
  if [[ "$status" == running:* ]]; then
    printf "${GREEN}%-35s${NC} %s\n" "$container" "✅ ${status#running:}"
  else
    printf "${RED}%-35s${NC} %s\n" "$container" "❌ stopped"
  fi
done

echo ""
echo "── Summary ──"
running_ct=0; failed_ct=0
for entry in "${SERVICES[@]}"; do
  IFS='|' read -r n t l <<< "$entry"
  s=$(check_launchd "$l")
  [[ "$s" == running:* ]] && ((running_ct++))
  [[ "$s" == failed:* ]] && ((failed_ct++))
done
echo "Launchd: $running_ct running, $failed_ct failed"
docker_ok=$(for c in "${DOCKER_SERVICES[@]}"; do check_docker "$c"; done | grep -c "running" || true)
echo "Docker:  $docker_ok/${#DOCKER_SERVICES[@]} running"
echo ""
echo "📁 $RUNTIME_MATRIX"
