#!/usr/bin/env bash
# Launch Runtime MCP Server
# Usage: bash start-mcp-server.sh                (stdio mode)
#        bash start-mcp-server.sh --port 8420    (HTTP SSE mode)
set -euo pipefail

HERMES_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python"
export RUNTIME_HOME="${RUNTIME_HOME:-$HOME/runtime}"
export PYTHONPATH="$HOME/Workspace/projects/runtime/src${PYTHONPATH:+:$PYTHONPATH}"

exec "$HERMES_PYTHON" "$HOME/Workspace/projects/runtime/src/runtime/mcp_server.py" "$@"
