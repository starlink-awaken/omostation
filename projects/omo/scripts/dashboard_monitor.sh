#!/usr/bin/env bash
# omostation dashboard 监控 + 健康检查 + 异常治理历史 append — P40-W2
# 用法:
#   bash scripts/dashboard_monitor.sh
# 可配 crontab 每 5min 跑.
set -uo pipefail

WORKSPACE="${WORKSPACE:-/Users/xiamingxing/Workspace}"
HISTORY="$WORKSPACE/.omo/_knowledge/governance-history.jsonl"
PLIST_NAME="com.omo.dashboard"
PORT="${PORT:-9090}"
DASHBOARD_URL="http://localhost:${PORT}/"

# 1. launchd 状态
LAUNCHD_LINE=$(launchctl list | grep "${PLIST_NAME}" || true)
if [ -z "${LAUNCHD_LINE}" ]; then
    LAUNCHD_STATE="down"
else
    LAUNCHD_STATE="running"
fi

# 2. HTTP 探活
# 注: dashboard 每次请求会重生成 HTML (10+s), 故 --max-time 15.
# %{http_code} 由 curl 在收到响应头时写入, 即使 body 还在传输也已可用;
# curl 因超时返回非零退出码时, "%{http_code}" 仍是有效的 HTTP 数字.
# 故不能用 `$(... || echo 000)` 模式 (会把 curl 输出的 "200" 和 fallback "000" 拼成 "200000"),
# 也不能用 `... || HTTP_CODE=""` (会丢弃 curl 已捕获的有效 HTTP 码).
# 正解: 直接接受 curl 退出码, 只在 HTTP_CODE 为空时兜底为 "000".
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "${DASHBOARD_URL}" 2>/dev/null)
[ -z "${HTTP_CODE}" ] && HTTP_CODE="000"

# 3. PID
PID=$(echo "${LAUNCHD_LINE}" | awk '{print $1}')
[ -z "${PID}" ] && PID="-"

# 4. 写治理历史 JSONL (一行 = 一条记录)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
JSON_ENTRY="{\"source\":\"dashboard_monitor\",\"timestamp\":\"${TIMESTAMP}\",\"launchd_state\":\"${LAUNCHD_STATE}\",\"http_code\":\"${HTTP_CODE}\",\"pid\":\"${PID}\",\"port\":${PORT}}"
echo "${JSON_ENTRY}" >> "${HISTORY}"

# 5. 决策 + 退出码
if [ "${LAUNCHD_STATE}" = "down" ]; then
    echo "[FAIL] Dashboard DOWN (launchd 未跑), HTTP=${HTTP_CODE}, history appended"
    exit 2
elif [ "${HTTP_CODE}" != "200" ]; then
    echo "[WARN] Dashboard launchd 跑但 HTTP=${HTTP_CODE}, PID=${PID}, history appended"
    exit 1
else
    echo "[OK] Dashboard running, HTTP=200, PID=${PID}, history appended"
    exit 0
fi
