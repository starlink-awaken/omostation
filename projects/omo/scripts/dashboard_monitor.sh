#!/usr/bin/env bash
# omostation dashboard 监控 + 健康检查 + 异常治理历史 append — P40-W2
# Round 14 P0 升级: 写合规 OmoHistoryRecord (补 date/total_score/grade/watchlist_count 4 必填字段)
# 之前 record 缺 4 必填字段 → 每次写都增加 audit drift → baseline 持续 stale
# 用法:
#   bash scripts/dashboard_monitor.sh
# 可配 crontab 每 5min 跑.
# 测试 override (Round 14 P0): 设 LAUNCHD_STATE_OVERRIDE / HTTP_CODE_OVERRIDE / PID_OVERRIDE 跳过真 launchd/curl
set -uo pipefail

WORKSPACE="${WORKSPACE:-/Users/xiamingxing/Workspace}"
HISTORY="$WORKSPACE/.omo/_knowledge/governance-history.jsonl"
PLIST_NAME="com.omo.dashboard"
PORT="${PORT:-9090}"
DASHBOARD_URL="http://localhost:${PORT}/"

# 1. launchd 状态 (可 override 便于测试)
if [ -n "${LAUNCHD_STATE_OVERRIDE:-}" ]; then
    LAUNCHD_STATE="${LAUNCHD_STATE_OVERRIDE}"
else
    LAUNCHD_LINE=$(launchctl list | grep "${PLIST_NAME}" || true)
    if [ -z "${LAUNCHD_LINE}" ]; then
        LAUNCHD_STATE="down"
    else
        LAUNCHD_STATE="running"
    fi
fi

# 2. HTTP 探活 (可 override 便于测试)
# 注: dashboard 每次请求会重生成 HTML (10+s), 故 --max-time 15.
# %{http_code} 由 curl 在收到响应头时写入, 即使 body 还在传输也已可用;
# curl 因超时返回非零退出码时, "%{http_code}" 仍是有效的 HTTP 数字.
# 故不能用 `$(... || echo 000)` 模式 (会把 curl 输出的 "200" 和 fallback "000" 拼成 "200000"),
# 也不能用 `... || HTTP_CODE=""` (会丢弃 curl 已捕获的有效 HTTP 码).
# 正解: 直接接受 curl 退出码, 只在 HTTP_CODE 为空时兜底为 "000".
if [ -n "${HTTP_CODE_OVERRIDE:-}" ]; then
    HTTP_CODE="${HTTP_CODE_OVERRIDE}"
else
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 "${DASHBOARD_URL}" 2>/dev/null)
    [ -z "${HTTP_CODE}" ] && HTTP_CODE="000"
fi

# 3. PID (可 override 便于测试)
if [ -n "${PID_OVERRIDE:-}" ]; then
    PID="${PID_OVERRIDE}"
else
    PID=$(echo "${LAUNCHD_LINE}" | awk '{print $1}')
    [ -z "${PID}" ] && PID="-"
fi

# 4. 写治理历史 JSONL (一行 = 一条合规 OmoHistoryRecord)
# Round 14 P0 关键变更: 补 date/total_score/grade/watchlist_count 4 必填字段
# 语义说明: dashboard_monitor 是健康监控点, 不参与治理评分; 4 字段用占位值:
#   - date: 当天 UTC 日期 (供按日聚合, 真实可观察)
#   - total_score: 0.0 (健康监控点不评分)
#   - grade: "F" (语义: 不参与评分, 不是真"差")
#   - watchlist_count: 0 (健康监控点不入 watchlist)
# 替代方案见 §11.6 P0-2 (audit source 白名单) — 那是治标, 这是治本
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DATE=$(date -u +%Y-%m-%d)
JSON_ENTRY="{\"source\":\"dashboard_monitor\",\"date\":\"${DATE}\",\"timestamp\":\"${TIMESTAMP}\",\"total_score\":0.0,\"grade\":\"F\",\"watchlist_count\":0,\"launchd_state\":\"${LAUNCHD_STATE}\",\"http_code\":\"${HTTP_CODE}\",\"pid\":\"${PID}\",\"port\":${PORT}}"
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

