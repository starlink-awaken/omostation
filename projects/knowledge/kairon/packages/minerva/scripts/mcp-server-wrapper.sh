#!/bin/bash
# Minerva MCP Server Wrapper
# Sources the parent environment so MCP client's env filtering doesn't break us.
# Called by Hermes native MCP client via config.yaml.

set -euo pipefail

# Source env vars from ~/.hermes/.env (Hermes API keys)
if [ -f "$HOME/.hermes/.env" ]; then
  set -a
  source "$HOME/.hermes/.env"
  set +a
fi

# Also try .zshrc for keys that might be there
if [ -f "$HOME/.zshrc" ]; then
  # Extract known API key exports
  for var in DEEPSEEK_API_KEY EXA_API_KEY METASO_API_KEY GLM_API_KEY OPENAI_API_KEY; do
    if [ -z "${!var:-}" ]; then
      val=$(grep "export $var=" "$HOME/.zshrc" 2>/dev/null | head -1 | sed 's/export //;s/"//g')
      if [ -n "$val" ]; then
        eval "$val"
      fi
    fi
  done
fi

# Ensure MINERVA_HOME is set
export MINERVA_HOME="${MINERVA_HOME:-$HOME/Workspace/minerva}"

# Start the actual MCP server
cd "$MINERVA_HOME"
exec "$MINERVA_HOME/.venv/bin/python3" -m minerva.mcp_server.server
