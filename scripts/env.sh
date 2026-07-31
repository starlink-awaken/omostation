#!/usr/bin/env bash
# =============================================================================
# Runtime Layer — Environment Configuration
# Source this file before using runtime tools: source ~/runtime/config/env.sh
# =============================================================================

# ─── Runtime Home ────────────────────────────────────────────────────────────
export RUNTIME_HOME="${RUNTIME_HOME:-$HOME/runtime}"

# ─── Core Paths ──────────────────────────────────────────────────────────────
export RUNTIME_MATRIX="${RUNTIME_MATRIX:-$RUNTIME_HOME/matrix.yaml}"
export RUNTIME_CONFIG="${RUNTIME_CONFIG:-$RUNTIME_HOME/config/env.sh}"
export RUNTIME_SCRIPTS="${RUNTIME_SCRIPTS:-$RUNTIME_HOME/scripts}"
export RUNTIME_LOGS="${RUNTIME_LOGS:-$RUNTIME_HOME/logs}"
export RUNTIME_AGENTS="${RUNTIME_AGENTS:-$RUNTIME_HOME/agents}"

# ─── Deployment Paths ────────────────────────────────────────────────────────
# Projects workspace root
export WORKSPACE_HOME="${WORKSPACE_HOME:-$HOME/Workspace}"

# Kairon monorepo
export KAIRON_HOME="${KAIRON_HOME:-$WORKSPACE_HOME/projects/kairon}"

# Archived projects
export ARCHIVE_HOME="${ARCHIVE_HOME:-$WORKSPACE_HOME/projects/_archived}"

# ─── Launchd ──────────────────────────────────────────────────────────────────
export LAUNCHCTL_DIR="${LAUNCHCTL_DIR:-$HOME/Library/LaunchAgents}"


# ─── Cron Service ─────────────────────────────────────────────────────────────
export CRON_SERVICE_PORT="${CRON_SERVICE_PORT:-7450}"
export CRON_SERVICE_HOME="${CRON_SERVICE_HOME:-$HOME/.cron-service}"
export CRON_SERVICE_LOG="${CRON_SERVICE_LOG:-$CRON_SERVICE_HOME/logs/}"

# ─── Docker Services ─────────────────────────────────────────────────────────
export GBRAIN_DB_PORT="${GBRAIN_DB_PORT:-5433}"
export GBRAIN_HOME="${GBRAIN_HOME:-$HOME/.gbrain}"

# ─── Ollama ───────────────────────────────────────────────────────────────────
export OLLAMA_BIN="${OLLAMA_BIN:-ollama}"
export OLLAMA_PORT="${OLLAMA_PORT:-11434}"

# ─── Agent (轻量 Runtime 管理 Agent) ───────────────────────────────────────
export RUNTIME_AGENT_TYPE="${RUNTIME_AGENT_TYPE:-}"  # pi | omp | none
export RUNTIME_AGENT_CONFIG="${RUNTIME_AGENT_CONFIG:-$RUNTIME_HOME/agents/config.yaml}"

echo "[runtime] RUNTIME_HOME=$RUNTIME_HOME"
echo "[runtime] MATRIX=$RUNTIME_MATRIX"
