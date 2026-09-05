#!/usr/bin/env bash
# droid-batch.sh — Squad A T1 批量编辑 wrapper (direct-cli 通道)
#
# 焊死了 2026-09-05 实测踩坑的正确参数：
#   - 默认模型 gpt-5.6-sol 在当前账号/地区策略下 400(Provider not available)，
#     必须显式 --model custom:DeepSeek-V4-Flash---Anthropic-6
#   - 只允许 --auto low|medium；high/skip-permissions-unsafe 是 R3 executor 的地盘，
#     不归这条 direct-cli 通道管
#
# 用法: droid-batch.sh <low|medium> "<编辑指令>" [额外 droid exec 参数...]
set -euo pipefail

AUTO_LEVEL="${1:?用法: droid-batch.sh <low|medium> \"<编辑指令>\"}"
PROMPT="${2:?缺少编辑指令}"
shift 2 || true

case "$AUTO_LEVEL" in
  low|medium) ;;
  *)
    echo "拒绝: --auto 只允许 low 或 medium（本次传入: $AUTO_LEVEL）" >&2
    echo "high/skip-permissions-unsafe 属于 R3 executor(Mika)的地盘，不归 direct-cli 通道管" >&2
    exit 1
    ;;
esac

exec droid exec --auto "$AUTO_LEVEL" --model "custom:DeepSeek-V4-Flash---Anthropic-6" "$PROMPT" "$@"
