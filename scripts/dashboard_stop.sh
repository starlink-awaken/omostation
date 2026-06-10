#!/usr/bin/env bash
# omostation dashboard 优雅停止 — P39-W2
# 从 launchd 卸载 + 清理 LaunchAgent
set -euo pipefail

PLIST_NAME="com.omo.dashboard"
PLIST_DST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "=== omo dashboard 优雅停止 ==="

# 1. 卸载 launchd job (忽略未加载错误)
if launchctl list | grep -q "${PLIST_NAME}"; then
    launchctl unload -w "${PLIST_DST}" 2>/dev/null || true
    echo "[ok] launchd job unloaded"
else
    echo "[skip] launchd job 未在跑"
fi

# 2. 删除 plist 文件
if [ -f "${PLIST_DST}" ]; then
    rm "${PLIST_DST}"
    echo "[ok] plist 文件已清理"
else
    echo "[skip] plist 文件不存在"
fi

# 3. 最终确认
if launchctl list | grep -q "${PLIST_NAME}"; then
    echo "[warn] launchd 仍在跑: $(launchctl list | grep ${PLIST_NAME})"
    exit 1
else
    echo "=== Dashboard 停止完成 ==="
    exit 0
fi
