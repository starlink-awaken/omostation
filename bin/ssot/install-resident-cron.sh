#!/usr/bin/env bash
# install-resident-cron.sh — 常驻 resident agent 调度 (M1.3)
#
# 安装 crontab 条目使 resident 体系持续运行:
#   - 每 2min: omo resident daemon --once(守护式 tick, 防重复; checkpoint 断点续传)
#   - 每 5min: omo resident signals(personal-signals 轮询)
#   - 每 5min: omo resident alert(告警转发)
#   - 每天 02:10: system-health-check --emit(体系健康探针)
#
# 幂等: 重复执行不重复添加。

set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PYTHONPATH="${WORKSPACE}/projects/omo/src:${PYTHONPATH:-}"

CRON_MARKER="# resident-agent-schedule (managed by install-resident-cron.sh)"

# 构造 cron 条目
CRON_DAEMON="*/2 * * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} -m omo.cli resident daemon --once --ledger ${WORKSPACE}/runtime/omo/event-ledger.sqlite3 >> ${WORKSPACE}/.omo/_delivery/resident-orchestrator/cron.log 2>&1"
CRON_SIGNALS="*/5 * * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} -m omo.cli resident signals --dry-run >> ${WORKSPACE}/.omo/_delivery/personal-signals/cron.log 2>&1"
CRON_ALERT="*/5 * * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} -m omo.cli resident alert --dry-run >> ${WORKSPACE}/.omo/_delivery/alert-forwarder/cron.log 2>&1"
CRON_HEALTH="10 2 * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} bin/ssot/system-health-check.py --emit >> ${WORKSPACE}/.omo/_delivery/resident-orchestrator/health.log 2>&1"

# 移除旧 marker 块(幂等),再追加新块
CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
CLEANED_CRON="$(printf '%s\n' "${CURRENT_CRON}" | grep -v -F "${CRON_MARKER}" | sed '/^$/N;/^\n$/D' || true)"

cat << EOF | crontab -
${CLEANED_CRON}
${CRON_MARKER}
${CRON_DAEMON}
${CRON_SIGNALS}
${CRON_ALERT}
${CRON_HEALTH}
EOF

echo "resident cron installed:"
crontab -l | grep -A5 "${CRON_MARKER}" | sed 's/^/  /'
