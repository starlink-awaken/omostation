#!/usr/bin/env bash
# =============================================================================
# Runtime Matrix CLI — query and expand the service registry
# Usage: bash ~/runtime/scripts/matrix.sh <command> [args]
#
# Commands:
#   list          — list all services
#   get <name>    — get a specific service entry
#   resolve       — expand all $VAR references to actual values
#   resolve <name> — expand and show a specific service
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_HOME="${RUNTIME_HOME:-$HOME/runtime}"
source "$RUNTIME_HOME/config/env.sh" 2>/dev/null || true

show_usage() {
  echo "Usage: $(basename "$0") <command>"
  echo ""
  echo "Commands:"
  echo "  list              List all registered services"
  echo "  get <name>        Show details for a specific service"
  echo "  resolve           Expand all \$VAR refs + show resolved paths"
  echo "  resolve <name>    Resolve and show one service"
  echo "  groups            Show service groups"
  echo "  version           Show matrix version"
  exit 1
}

# Read YAML fields with sed (lightweight, no yq dependency)
get_services() {
  # Extract service names
  sed -n 's/^  - name: "\(.*\)"/\1/p' "$RUNTIME_MATRIX"
}

get_field() {
  local service="$1"
  local field="$2"
  sed -n "/    - name: \"$service\"/,/^    - name:/p" "$RUNTIME_MATRIX" | \
    grep "^      $field:" | \
    sed "s/^      $field: //;s/\"//g"
}

CMD="${1:-}"
shift 2>/dev/null || true

case "$CMD" in
  list)
    echo "Runtime Matrix: $RUNTIME_MATRIX"
    echo ""
    echo "── Services ──"
    while IFS= read -r svc; do
      [[ -z "$svc" ]] && continue
      status=$(get_field "$svc" "status" || echo "?")
      port=$(get_field "$svc" "port" || echo "—")
      type=$(get_field "$svc" "type" || echo "?")
      printf "  %-25s %-10s %-8s %s\n" "$svc" "[$type]" ":$port" "$status"
    done < <(get_services)
    echo ""
    echo "── Groups ──"
    sed -n '/^  groups:/,$ p' "$RUNTIME_MATRIX" | grep "^    [a-z_]*:" | sed 's/:$//' | while read -r group; do
      echo "  • $group"
    done
    ;;

  get)
    svc="${1:-}"
    [[ -z "$svc" ]] && { echo "Usage: matrix.sh get <service-name>"; exit 1; }
    echo "Service: $svc"
    echo "────────────────"
    # Extract block for this service
    sed -n "/- name: \"$svc\"/,/^  - name:\|^  # ───/p" "$RUNTIME_MATRIX" | \
      grep -v "^  - name:" | \
      sed 's/^      //' | \
      while IFS=': ' read -r key value; do
        [[ -z "$key" ]] && continue
        printf "  %-20s %s\n" "$key" "$value"
      done
    echo ""
    echo "Resolved paths:"
    eval "echo \"  deploy_path: $(get_field "$svc" "deploy_path" 2>/dev/null || echo '-')"\" 2>/dev/null
    eval "echo \"  log_path: $(get_field "$svc" "log_path" 2>/dev/null || echo '-')"\" 2>/dev/null
    ;;

  resolve)
    if [[ $# -ge 1 ]]; then
      svc="$1"
      echo "Resolved: $svc"
      echo "────────────────"
      for field in deploy_path log_path start_command launchd_config; do
        raw=$(get_field "$svc" "$field" 2>/dev/null || echo "")
        [[ -z "$raw" ]] && continue
        resolved=$(eval "echo \"$raw\"" 2>/dev/null)
        printf "  %-20s %s\n" "$field" "$resolved"
      done
    else
      # Resolve all deploy_paths
      echo "Resolved Matrix Paths"
      echo "─────────────────────"
      while IFS= read -r svc; do
        [[ -z "$svc" ]] && continue
        raw=$(get_field "$svc" "deploy_path" 2>/dev/null || echo "")
        [[ -z "$raw" ]] && continue
        resolved=$(eval "echo \"$raw\"" 2>/dev/null)
        printf "  %-25s → %s\n" "$svc" "$resolved"
      done < <(get_services)
    fi
    ;;

  groups)
    echo "Service Groups (from $RUNTIME_MATRIX)"
    echo "────────────────────────────────────────"
    sed -n '/^  groups:/,$ p' "$RUNTIME_MATRIX" | \
      grep -E "^    [a-z_]+:" | \
      sed 's/:$//' | \
      while read -r group; do
        desc=$(sed -n "/^      $group:/,/^    [a-z_]/{/description: /s/.*description: \"\(.*\)\"/\1/p}" "$RUNTIME_MATRIX" 2>/dev/null || echo "")
        [[ -z "$desc" ]] && desc=$(sed -n "/^  groups:/,//{/^    $group:/,/^    [a-z_]/{/description: /p}}" "$RUNTIME_MATRIX" | head -1 | sed 's/.*description: "//;s/"//')
        members=$(sed -n "/^    $group:/,/^    [a-z_]/p" "$RUNTIME_MATRIX" | grep "members:" | sed 's/.*\[//;s/\]//' | tr ',' ' ' || true)
        echo "  • $group"
        echo "    $desc"
        echo "    Members: $members"
        echo ""
      done
    ;;

  version)
    ver=$(grep "version:" "$RUNTIME_MATRIX" | head -1 | sed 's/.*version: //' || true)
    updated=$(grep "updated:" "$RUNTIME_MATRIX" | head -1 | sed 's/.*updated: "//;s/"//' || true)
    echo "Runtime Matrix v$ver"
    echo "Updated: $updated"
    echo "Path:    $RUNTIME_MATRIX"
    ;;

  *)
    show_usage
    ;;
esac
