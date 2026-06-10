#!/usr/bin/env bash
# omostation dashboard 卸载脚本 (优雅停止) — P40-W2
# 卸 launchd job + 删 plist 文件
set -uo pipefail

PLIST_NAME="com.omo.dashboard"
PLIST_DST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "=== omo dashboard 卸载 ==="

if [ ! -f "${PLIST_DST}" ]; then
    echo "[skip] Dashboard 未装 (plist 不存在: ${PLIST_DST})"
    exit 0
fi

# 1. 卸 launchd job
if launchctl list | grep -q "${PLIST_NAME}"; then
    launchctl unload -w "${PLIST_DST}" 2>/dev/null || true
    echo "[ok] launchd job unloaded"
else
    echo "[skip] launchd job 未在跑"
fi

# 2. 删除 plist 文件
rm -f "${PLIST_DST}"
echo "[ok] plist 文件已清理"

# 3. 最终确认
if launchctl list | grep -q "${PLIST_NAME}"; then
    echo "[warn] launchd 仍在跑: $(launchctl list | grep ${PLIST_NAME})"
    exit 1
fi
echo "=== Dashboard 卸载完成 ==="
exit 0
