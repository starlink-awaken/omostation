#!/bin/bash
# sync-dashboard.sh — 定时同步 MBP Panorama 驾驶舱数据到 Mac-mini
# 通过 Tailscale SSH 拉取 runtime/dashboard/ 下的采集产物
# 用法: bash bin/panorama/sync-dashboard.sh

set -uo pipefail

MBP_HOST="100.68.80.44"
MBP_USER="xiamingxing"
MBP_WORKSPACE="~/Workspace"
LOCAL_WORKSPACE="$(cd "$(dirname "$0")/../.." && pwd)"
DASHBOARD_DIR="${LOCAL_WORKSPACE}/runtime/dashboard"
LOG_DIR="${LOCAL_WORKSPACE}/runtime/cron"
LOG_FILE="${LOG_DIR}/sync-dashboard.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
ERROR=0

mkdir -p "$DASHBOARD_DIR" "$LOG_DIR"

log() { echo "[$TIMESTAMP] $*" >> "$LOG_FILE"; }

# 1) 拉取 dashboard 静态产物（scp 更稳定）
if scp -o ConnectTimeout=15 -o StrictHostKeyChecking=no -q \
    "${MBP_USER}@${MBP_HOST}:${MBP_WORKSPACE}/runtime/dashboard/index.html" \
    "${DASHBOARD_DIR}/index.html" 2>>"$LOG_FILE"; then
    log "OK dashboard synced ($(stat -f%z "${DASHBOARD_DIR}/index.html" 2>/dev/null || echo 0) bytes)"
else
    log "FAIL dashboard sync (scp exit $?)"
    ERROR=1
fi

# 2) 拉取 panorama 原始 JSON 数据（可选）
if scp -o ConnectTimeout=15 -o StrictHostKeyChecking=no -q \
    "${MBP_USER}@${MBP_HOST}:${MBP_WORKSPACE}/runtime/dashboard/data.json" \
    "${DASHBOARD_DIR}/data.json" 2>>"$LOG_FILE"; then
    log "OK data.json synced"
else
    log "SKIP data.json (可能尚未生成)"
fi

# 3) 清理超过 7 天的日志
find "$LOG_DIR" -name 'sync-dashboard.log.*' -mtime +7 -delete 2>/dev/null || true

# 4) 日志轮转（超 1MB 时）
if [ -f "$LOG_FILE" ] && [ "$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)" -gt 1048576 ]; then
    mv "$LOG_FILE" "${LOG_FILE}.$(date '+%Y%m%d%H%M%S')"
fi

exit $ERROR
