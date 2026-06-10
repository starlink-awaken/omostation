#!/usr/bin/env bash
# omostation dashboard health check — P39-W2
# 1. launchd 状态 / 2. HTTP 探活 / 3. 进程 / 4. 日志尾部
set -uo pipefail

PLIST_NAME="com.omo.dashboard"
PORT=9090
DASHBOARD_URL="http://localhost:${PORT}/"

echo "=== Dashboard Health Check ==="
echo ""

# 1. launchd 状态
echo "1. launchd 状态:"
if launchctl list | grep -q "${PLIST_NAME}"; then
    launchctl list | grep "${PLIST_NAME}" | sed 's/^/   /'
    echo "   [ok] launchd 在跑"
else
    echo "   [info] launchd 未跑 (POC 阶段已 unload)"
fi
echo ""

# 2. HTTP 探活
echo "2. HTTP 测 ${DASHBOARD_URL}:"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "${DASHBOARD_URL}" 2>/dev/null || echo "000")
if [ "${HTTP_CODE}" = "200" ]; then
    echo "   [ok] HTTP 200 (dashboard 实时响应)"
else
    echo "   [info] HTTP ${HTTP_CODE} (dashboard 未在跑 / 已停止)"
fi
echo ""

# 3. 进程
echo "3. dashboard 进程:"
if ps aux | grep -E "omo dashboard|omo_observability_dashboard" | grep -v grep >/dev/null 2>&1; then
    ps aux | grep -E "omo dashboard|omo_observability_dashboard" | grep -v grep | sed 's/^/   /'
    echo "   [ok] dashboard 进程在跑"
else
    echo "   [info] dashboard 进程未跑 (POC 阶段已停)"
fi
echo ""

# 4. 日志尾部 (如存在)
STDOUT_LOG="/Users/xiamingxing/Workspace/.omo/_delivery/dashboard-stdout.log"
STDERR_LOG="/Users/xiamingxing/Workspace/.omo/_delivery/dashboard-stderr.log"
echo "4. 日志尾部:"
if [ -f "${STDOUT_LOG}" ]; then
    echo "   stdout (last 3):"
    tail -3 "${STDOUT_LOG}" 2>/dev/null | sed 's/^/     /'
fi
if [ -f "${STDERR_LOG}" ]; then
    echo "   stderr (last 3):"
    tail -3 "${STDERR_LOG}" 2>/dev/null | sed 's/^/     /'
fi
echo ""

echo "=== 检查完成 ==="
