#!/usr/bin/env bash
# omostation dashboard 监控 + 健康检查 — P40-W2
# Round 14 P0 升级: 写合规 OmoHistoryRecord (补 4 必填字段占位值)
# Round 20 P0 升级: 拆到独立 omo-health.jsonl (新 .jsonl), 治理历史不再被健康监控污染
#  - HISTORY_PATH 默认 = $WORKSPACE/.omo/_knowledge/omo-health.jsonl
#  - 旧 governance-history.jsonl 不再被 dashboard_monitor 写入 (历史 1500+ drift 锁在 baseline)
# 用法:
#   bash scripts/dashboard_monitor.sh
# 可配 crontab 每 5min 跑.
# 测试 override (Round 14 P0): 设 LAUNCHD_STATE_OVERRIDE / HTTP_CODE_OVERRIDE / PID_OVERRIDE 跳过真 launchd/curl
set -uo pipefail

WORKSPACE="${WORKSPACE:-/Users/xiamingxing/Workspace}"
# Round 20 P0: 默认路径 = omo-health.jsonl (新), 旧 governance-history.jsonl 不再被本脚本写入
HISTORY="${HISTORY:-$WORKSPACE/.omo/_knowledge/omo-health.jsonl}"
PLIST_NAME="com.omo.dashboard"
PORT="${PORT:-9090}"
DASHBOARD_URL="http://localhost:${PORT}/"

# 1. launchd 状态 (可 override 便于测试)
if [ -n "${LAUNCHD_STATE_OVERRIDE:-}" ]; then
    LAUNCHD_STATE="${LAUNCHD_STATE_OVERRIDE}"
else
    # Round 20 P0 修: grep -m1 只取第一行匹配 (旧版拿到多行导致 PID 变量含 \n, JSON 字符串硬换行 → 6/7 raw)
    LAUNCHD_LINE=$(launchctl list | grep -m1 "${PLIST_NAME}" || true)
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
    # Round 20 P0 修: tr -d 删 \n, 防 PID 变量含字面 newline 让 JSON 字符串硬换行
    PID=$(echo "${LAUNCHD_LINE}" | tr -d '\n' | awk '{print $1}')
    [ -z "${PID}" ] && PID="-"
fi

# 4. 写健康监控 JSONL (一行 = 一条合规 OmoHealthRecord, Round 20 P0)
# Round 20 P0 关键变更: 写到独立 omo-health.jsonl, 字段集 7 个:
#   - source: "dashboard_monitor" (写方标识)
#   - launchd_state: "running" / "down"
#   - http_code: "200" / "000" (兜底)
#   - pid: launchd PID (或 "-" 当 down)
#   - port: 9090
#   - timestamp: ISO8601 Z 结尾
# 不再写 governance-history.jsonl (治理历史), 避免"健康监控点 grade=F 污染评分面板"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
JSON_ENTRY="{\"source\":\"dashboard_monitor\",\"launchd_state\":\"${LAUNCHD_STATE}\",\"http_code\":\"${HTTP_CODE}\",\"pid\":\"${PID}\",\"port\":${PORT},\"timestamp\":\"${TIMESTAMP}\"}"
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

