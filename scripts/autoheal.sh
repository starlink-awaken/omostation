#!/usr/bin/env bash
# =============================================================================
# eCOS Auto-Heal — Detect offline services and attempt restart
# Usage: bash ~/runtime/scripts/autoheal.sh
# Source: $RUNTIME_SCRIPTS/autoheal.sh
# Data:   reads start_command from $RUNTIME_MATRIX for offline services
# Logs:   $RUNTIME_LOGS/autoheal.log
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_HOME="${RUNTIME_HOME:-$HOME/runtime}"
source "$RUNTIME_HOME/config/env.sh" 2>/dev/null || true

# ─── Paths ───────────────────────────────────────────────────────────────────
LOG_DIR="${RUNTIME_LOGS:-$RUNTIME_HOME/logs}"
LOG_FILE="$LOG_DIR/autoheal.log"
MATRIX="${RUNTIME_MATRIX:-$RUNTIME_HOME/matrix.yaml}"
NOW=$(date '+%Y-%m-%d %H:%M:%S')
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

mkdir -p "$LOG_DIR"

log() {
    local level="$1"
    local msg="$2"
    echo "[$NOW] [$level] $msg" | tee -a "$LOG_FILE"
}

# ─── Matrix field reader (lightweight, no yq dependency) ────────────────────
get_field() {
    local service="$1"
    local field="$2"
    # Services in matrix.yaml are indented at 4 spaces:
    #     - name: "service-name"
    #       start_command: "cmd"
    sed -n "/    - name: \"$service\"/,/^    - name:/p" "$MATRIX" | \
        grep "^      $field:" | \
        sed "s/^      $field: //;s/\"//g; s/^> *//" | \
        head -1
}

# ─── Get offline services via i0 probe ──────────────────────────────────────
log "INFO" "Auto-heal scan starting (matrix=$MATRIX)"

OFFLINE=$(PYTHONPATH="$PROJECT_ROOT/src" python3 "$SCRIPT_DIR/check_services_down.py" 2>/dev/null || true)

if [ -z "$OFFLINE" ]; then
    log "INFO" "All services healthy — no action needed"
    exit 0
fi

log "INFO" "Offline services detected:"
echo "$OFFLINE" | while IFS= read -r line; do
    [ -z "$line" ] && continue
    log "INFO" "  $line"
done

# ─── Attempt restart for each offline service ───────────────────────────────
HEALED=0
FAILED=0
SKIPPED=0

while IFS= read -r line; do
    [ -z "$line" ] && continue

    # Parse: "service_name:port - not listening (status)"
    svc_name=$(echo "$line" | cut -d: -f1)

    start_cmd=$(get_field "$svc_name" "start_command" 2>/dev/null || echo "")

    if [ -z "$start_cmd" ]; then
        log "SKIP" "$svc_name: offline but no start_command defined — skipping"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    log "INFO" "$svc_name: restarting via: $start_cmd"

    # Expand $VAR references in the command
    expanded_cmd=$(eval "echo \"$start_cmd\"" 2>/dev/null)

    # Run the restart command; capture both stdout/stderr
    if eval "$expanded_cmd" >> "$LOG_FILE" 2>&1; then
        log "OK" "$svc_name: restart command succeeded"
        HEALED=$((HEALED + 1))
    else
        local_rc=$?
        log "ERROR" "$svc_name: restart FAILED (exit code $local_rc)"
        FAILED=$((FAILED + 1))
    fi
done <<< "$OFFLINE"

# ─── Summary ─────────────────────────────────────────────────────────────────
log "INFO" "Auto-heal complete: $HEALED healed, $FAILED failed, $SKIPPED skipped"

if [ "$FAILED" -gt 0 ]; then
    echo "[$NOW] [ALERT] Auto-heal: $FAILED service(s) could not be restarted" | tee -a "$LOG_FILE"
    exit 1
fi

exit 0
