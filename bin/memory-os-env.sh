#!/usr/bin/env bash
# Load Memory OS env into current shell (or print exports).
# Usage:
#   source bin/memory-os-env.sh
#   eval "$(bin/memory-os-env.sh --export)"
#   bin/memory-os-env.sh --check
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXAMPLE="${ROOT}/docs/operations/memory-os.env.example"
LOCAL="${ROOT}/config/memory-os.env"
COCKPIT_ENV="${ROOT}/projects/cockpit/.env"

_load_file() {
  local f="$1"
  local allow_override="${2:-0}"
  [[ -f "$f" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      local k="${BASH_REMATCH[1]}"
      local v="${BASH_REMATCH[2]}"
      v="${v%\"}"
      v="${v#\"}"
      # process env always wins when already non-empty and not file-override chain
      if [[ -n "${!k:-}" && "$allow_override" != "1" ]]; then
        continue
      fi
      if [[ -z "${!k:-}" || "$allow_override" == "1" ]]; then
        # only override if still defaulting (not pre-set in parent shell)
        if [[ -z "${!k:-}" ]]; then
          export "$k=$v"
        elif [[ "$allow_override" == "1" && -z "${MOS_ENV_LOCKED:-}" ]]; then
          export "$k=$v"
        fi
      fi
    fi
  done <"$f"
}

# Snapshot which keys parent shell already set (non-empty) — never clobber those
_PRESET_URI="${NEO4J_URI-}"
_PRESET_USER="${NEO4J_USER-}"
_PRESET_PASS="${NEO4J_PASSWORD-}"

# File order: example → cockpit .env → local config (later fills empties only; local can set if empty)
_load_file "$EXAMPLE" 0
_load_file "$COCKPIT_ENV" 0
_load_file "$LOCAL" 0

# Code defaults for anything still empty
: "${NEO4J_URI:=bolt://localhost:7687}"
: "${NEO4J_USER:=neo4j}"
: "${NEO4J_PASSWORD:=changeme}"
: "${MOS_TEMPORAL:=1}"
: "${MOS_RBAC:=1}"
: "${MOS_MEM0:=0}"
: "${MOS_GRAPHITI:=0}"
: "${NEO4J_HTTP_PORT:=7474}"
: "${NEO4J_BOLT_PORT:=7687}"

# Restore parent presets if they were non-empty
[[ -n "$_PRESET_URI" ]] && NEO4J_URI="$_PRESET_URI"
[[ -n "$_PRESET_USER" ]] && NEO4J_USER="$_PRESET_USER"
[[ -n "$_PRESET_PASS" ]] && NEO4J_PASSWORD="$_PRESET_PASS"

export NEO4J_URI NEO4J_USER NEO4J_PASSWORD
export MOS_TEMPORAL MOS_RBAC MOS_MEM0 MOS_GRAPHITI
export NEO4J_HTTP_PORT NEO4J_BOLT_PORT

cmd_export() {
  printf 'export NEO4J_URI=%q\n' "$NEO4J_URI"
  printf 'export NEO4J_USER=%q\n' "$NEO4J_USER"
  printf 'export NEO4J_PASSWORD=%q\n' "$NEO4J_PASSWORD"
  printf 'export NEO4J_HTTP_PORT=%q\n' "$NEO4J_HTTP_PORT"
  printf 'export NEO4J_BOLT_PORT=%q\n' "$NEO4J_BOLT_PORT"
  printf 'export MOS_TEMPORAL=%q\n' "$MOS_TEMPORAL"
  printf 'export MOS_RBAC=%q\n' "$MOS_RBAC"
  printf 'export MOS_MEM0=%q\n' "$MOS_MEM0"
  printf 'export MOS_GRAPHITI=%q\n' "$MOS_GRAPHITI"
}

cmd_check() {
  echo "NEO4J_URI=$NEO4J_URI"
  echo "NEO4J_USER=$NEO4J_USER"
  echo "MOS_TEMPORAL=$MOS_TEMPORAL MOS_RBAC=$MOS_RBAC"
  if [[ -f "$LOCAL" ]]; then
    echo "local_env=config/memory-os.env"
  elif [[ -f "$COCKPIT_ENV" ]]; then
    echo "local_env=projects/cockpit/.env"
  else
    echo "local_env=docs/operations/memory-os.env.example (defaults)"
  fi
  if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 "${NEO4J_BOLT_PORT}" 2>/dev/null; then
    echo "bolt: UP :${NEO4J_BOLT_PORT}"
  else
    echo "bolt: DOWN (run: bash bin/memory-os-neo4j-up.sh)"
  fi
}

case "${1:-}" in
  --export) cmd_export ;;
  --check) cmd_check ;;
  "")
    # When sourced, exports already applied; when executed, print check
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
      cmd_check
    fi
    ;;
  *)
    echo "usage: source $0 | $0 --export | $0 --check" >&2
    exit 2
    ;;
esac
