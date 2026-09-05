#!/usr/bin/env bash
# crush-review.sh — Squad A/B T2 跨厂商复核 wrapper (direct-cli 通道)
#
# 焊死了 2026-09-05 实测踩坑的正确参数：
#   - 模型必须是 provider/model 格式，裸名如 "glm" 会报
#     `Failed to override models: large model "glm" not found`
#   - --yolo/-y 在已装 v0.92.0 上实测不可用(Unknown flag)；本脚本不依赖它，
#     只用于"只读复核不改文件"的 prompt，靠任务边界而非技术层拦截
#
# 用法: crush-review.sh "<复核内容，脚本会自动加只读约束前缀>"
set -euo pipefail

REVIEW_CONTENT="${1:?用法: crush-review.sh \"<要复核的内容/diff摘要>\"}"

exec crush run --model "zai/glm-5.3" --quiet \
  "只复核以下改动是否有问题，不要修改任何文件，只给出结论：${REVIEW_CONTENT}"
