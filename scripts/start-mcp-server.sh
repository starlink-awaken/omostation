#!/usr/bin/env bash
# Launch Runtime MCP Server
# Usage: bash start-mcp-server.sh                (stdio mode)
#        bash start-mcp-server.sh --port 8420    (HTTP SSE mode)
set -euo pipefail

HERMES_PYTHON="$HOME/.hermes/hermes-agent/venv/bin/python"
export RUNTIME_HOME="${RUNTIME_HOME:-$HOME/runtime}"
export AUDIT_FILE_PATH="${AUDIT_FILE_PATH:-$HOME/runtime/data/kei_audit.jsonl}"
export PYTHONPATH="$HOME/Workspace/projects/runtime/src${PYTHONPATH:+:$PYTHONPATH}"

cd "$HOME/Workspace/projects/runtime"
exec "$HERMES_PYTHON" "$HOME/Workspace/projects/runtime/src/runtime/mcp_server.py" "$@"
