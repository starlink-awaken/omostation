#!/usr/bin/env bash
# omlx-node-setup.sh —— 在「从节点」(如 mac-mini) 上运行：
#   1) 把本机 omlx 绑定到 tailnet IP（默认只绑 127.0.0.1，外部连不上）
#   2) 启动 coding + embedding 两个服务
#   3) 打印可直接粘到 MBP 网关的 LiteLLM 路由块
#
# 前提：本机已装好 omlx（omlx 在 PATH）、Tailscale 已登录。
# 用法：  OMLX_ROOT=/你的/omlx ./omlx-node-setup.sh
#         （OMLX_ROOT 不设则用默认 /Volumes/Model/omlx）

set -u
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
ROOT="${OMLX_ROOT:-/Volumes/Model/omlx}"
export OMLX_ROOT="$ROOT"

TS=$(tailscale ip -4 2>/dev/null | head -1)
[ -z "$TS" ] && { echo "✗ 拿不到 tailnet IP，确认 Tailscale 已登录"; exit 1; }
command -v omlx >/dev/null || { echo "✗ 本机没装 omlx（PATH 里找不到）"; exit 1; }

echo "================ omlx 节点接入 ================"
echo "tailnet IP : $TS"
echo "OMLX_ROOT  : $ROOT"
echo "本机模型:"; omlxc list 2>/dev/null | sed -n '1,40p'
echo

echo ">> 启动 coding + embedding，绑定 $TS ..."
omlxc servecoding    --host "$TS" 2>&1 | tail -2
omlxc serveembedding --host "$TS" 2>&1 | tail -2
echo
echo ">> 等待加载，几十秒后用  omlxc status  / omlxc health coding  确认"

# 计算 coder 真实路径（mlx_lm 需要完整路径）
COD=$(readlink -f "$ROOT/models-active/coding/current" 2>/dev/null || python3 -c "import os;print(os.path.realpath('$ROOT/models-active/coding/current'))")

cat <<YAML

================ 把下面粘到 MBP: gateway/litellm-config.yaml ================
  - model_name: mini-omlx-coder            # mac-mini 的 MLX 编码模型
    litellm_params:
      model: openai/$COD
      api_base: http://$TS:8080/v1
      api_key: local
  - model_name: mini-omlx-embed
    litellm_params:
      model: openai/qwen3-embed
      api_base: http://$TS:8093/v1
      api_key: local
============================================================================
加完后在 MBP 上:  omlx gw stop && omlx gw start
首次外部连接，macOS 可能弹防火墙授权 python/mlx，请允许。
YAML
