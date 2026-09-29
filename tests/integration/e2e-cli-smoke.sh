#!/usr/bin/env bash
# e2e-cli-smoke.sh — e2e-smoke 的「CLI 入口」子集 (CI 纳入版)
#
# 为什么需要这个文件: `tests/run-shell-suites.sh` 的纳入/排除粒度是**整文件** ——
# e2e-smoke.sh 整份需要 agora SSE :7431 / cron-service :7450 在线, CI 无此环境, 只能整份排除。
# 这个包装只跑「不需要外部服务」的检查 (cockpit / agora / runtime 的 --help 可达),
# **逻辑不复制** —— 由 e2e-smoke.sh 的 --no-services / --no-imports 开关提供, 避免两处漂移。
#
# 纳入范围与理由 (2026-09-29 实测):
#   · CLI 入口 (e2e-smoke 段 2): **纳入**。三个项目都有 uv.lock ⇒ `uv run --frozen` 跳过依赖解析;
#     本机冷启(建 venv) 18s / 热启 2s。
#   · 服务在线 (段 1): 排除 —— 需 :7431 / :7450 正在运行。
#   · kairon 导入 (段 3): 排除 —— `kairon-ci.yml` 的 `make test-fast`(16 包循环 pytest) 覆盖面更强,
#     这里再跑一遍只是重复; 且它要先 `uv sync` 整个 kairon monorepo, 成本远高于本子集的价值。
#
# 用法: bash tests/integration/e2e-cli-smoke.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec bash "$ROOT/tests/integration/e2e-smoke.sh" --no-services --no-imports
