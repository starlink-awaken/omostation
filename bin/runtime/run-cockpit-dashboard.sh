#!/bin/bash
# Foreground entrypoint for the Cockpit LaunchAgent.
# launchd owns this process and receives uvicorn's exit status for KeepAlive.
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
COCKPIT_PROJECT="$WORKSPACE_ROOT/projects/cockpit"

if [[ ! -f "$COCKPIT_PROJECT/pyproject.toml" ]]; then
  echo "Cockpit project manifest not found: $COCKPIT_PROJECT/pyproject.toml" >&2
  exit 1
fi

UV_BIN="${UV_BIN:-/opt/homebrew/bin/uv}"
if [[ ! -x "$UV_BIN" ]]; then
  echo "uv executable not found: $UV_BIN" >&2
  exit 1
fi

export WORKSPACE="$WORKSPACE_ROOT"
export COCKPIT_DASHBOARD_PORT="${COCKPIT_DASHBOARD_PORT:-8090}"
export COCKPIT_UI_ROOT="${COCKPIT_UI_ROOT:-$WORKSPACE_ROOT/projects/cockpit-ui}"
cd "$COCKPIT_PROJECT"
exec "$UV_BIN" --project "$COCKPIT_PROJECT" run python -m cockpit.dashboard_server
