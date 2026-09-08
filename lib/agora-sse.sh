#!/usr/bin/env bash
# agora-sse wrapper (ADR-0435 判例第四例修复, 2026-09-08).
# 坏形态: uv <agora-dir> agora-mcp --sse (缺 run 动词, exit 2 死循环).
# 正确形态: uv run --project <agora> agora-mcp --sse
set -euo pipefail
exec /opt/homebrew/bin/uv run --project /Users/xiamingxing/Workspace/projects/agora \
  agora-mcp --sse
