#!/usr/bin/env bash
# agora-sse wrapper (ADR-0435 判例第四例修复, 2026-09-08).
# 坏形态: uv <agora-dir> agora-mcp --sse (缺 run 动词, exit 2 死循环).
# 正确形态: uv run --project <agora> agora-mcp --sse
set -euo pipefail
# 仓库根 = 本脚本所在 lib/ 的上一级 (安装位与检出根各自自推, 互不引用)
_SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_SELF_DIR/.." && pwd)"
exec /opt/homebrew/bin/uv run --project "$_REPO_ROOT/projects/agora" \
  agora-mcp --sse
