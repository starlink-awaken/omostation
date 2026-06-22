#!/usr/bin/env bash
# 启动 aetherforge llm-gateway, 连 LM Studio (1234, OpenAI 兼容).
# task#1 解 (产品走查 v3 2026-06-19): gateway /v1/generate 500 根因 = ollama(11434) 无 model,
# 改连 LM Studio(1234, 23 现成模型含 glm-4.7-flash), OPENAI_BASE_URL 让 detect_backends 走 openai provider.
#
# 用法: bash bin/start-gateway.sh   (前台跑; 后台加 nohup ... &)
# 前置: LM Studio 已启动 + 加载至少一个 model (curl localhost:1234/v1/models 看)
set -euo pipefail
export OPENAI_BASE_URL="http://localhost:1234/v1"
export OPENAI_API_KEY="lm-studio"   # LM Studio 本地不校验, 占位即可
cd /Users/xiamingxing/Workspace/projects/aetherforge/packages/gateway
exec uv run gateway serve --port 9290
