#!/usr/bin/env bash
# install-resident-cron.sh — 常驻 resident agent 调度 (M1.3 + M4.3 角色化)
#
# 安装 crontab 条目使 resident 体系持续运行 (M4.3: 五类角色独立 projector 并行):
#   - 每 2min: 五类角色 daemon --once (sediment/decision/execute/monitor/heartbeat,
#     各自独立 checkpoint + topic_filter 分片消费, 互不干扰)
#   - 每 5min: omo resident ingest(event-ingest-adapter: workflow-mesh 事件 →
#     bus_foundation 主题发布 + event-ledger 灌入, T10-12 事件源自动化)
#   - 每 5min: omo resident signals(personal-signals 轮询, 实际发布到事件流)
#   - 每 5min: omo resident inbox(感知文件夹 @感知信号 轮询, 实际发布到事件流, T10-15)
#   - 告警外发唯一路径 = daemon monitor 角色 (T10-16): monitor 每 2min publish
#     observability 严重事件 → alert 事件流 → alert handler 外发, 不再单独 CRON_ALERT
#   - 每 10min: omo resident promote(sediment 草稿 → 主题 retro 候选, 阶段2 知识晋升)
#   - 每天 02:10: system-health-check --emit(体系健康探针)
#
# 幂等: 重复执行不重复添加。

set -euo pipefail

WORKSPACE="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
# signals 发布依赖 bus-foundation (bus_foundation.facade.event)
PYTHONPATH="${WORKSPACE}/projects/omo/src:${WORKSPACE}/projects/bus-foundation/src:${PYTHONPATH:-}"

# cron 环境 PATH 受限, /usr/bin/python3 (3.9) 无 datetime.UTC → omo ledger
# import 失败。探测支持 datetime.UTC 的 python3 (3.11+), 优先 homebrew。
if ! "${PYTHON_BIN}" -c "from datetime import UTC" 2>/dev/null; then
  for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3.13 python3.12 python3.11; do
    if command -v "${cand}" >/dev/null 2>&1 && "${cand}" -c "from datetime import UTC" 2>/dev/null; then
      PYTHON_BIN="${cand}"
      break
    fi
  done
fi

CRON_MARKER="# resident-agent-schedule (managed by install-resident-cron.sh)"

# M4.3: 五类角色独立 projector 并行调度 (替换单一 daemon, 分片覆盖全部规则事件)
_ROLE_CRON=""
for role in sediment decision execute monitor heartbeat; do
  _ROLE_CRON="${_ROLE_CRON}
*/2 * * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} -m omo.cli resident daemon --once --role ${role} --ledger ${WORKSPACE}/runtime/omo/event-ledger.sqlite3 >> ${WORKSPACE}/.omo/_delivery/resident-orchestrator/cron-${role}.log 2>&1"
done

# 构造 cron 条目 (signals 实际发布, 不 dry-run)
CRON_INGEST="*/5 * * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} -m omo.cli resident ingest --ledger ${WORKSPACE}/runtime/omo/event-ledger.sqlite3 >> ${WORKSPACE}/.omo/_delivery/event-ingest/cron.log 2>&1"
CRON_SIGNALS="*/5 * * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} -m omo.cli resident signals >> ${WORKSPACE}/.omo/_delivery/personal-signals/cron.log 2>&1"
# inbox: 感知文件夹轮询(实际发布, 与 signals 并列, T10-15)
CRON_INBOX="*/5 * * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} -m omo.cli resident inbox >> ${WORKSPACE}/.omo/_delivery/perception-inbox/cron.log 2>&1"
# promote: 沉淀聚合→主题 retro 候选(实际落盘, 10min 节奏足够)
CRON_PROMOTE="*/10 * * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} -m omo.cli resident promote >> ${WORKSPACE}/.omo/_delivery/resident-orchestrator/promote.log 2>&1"
# proposal-to-adr: 决策提案 → ADR 草稿 (每天 01:00, 只生成草稿不自动采纳, BET-Y1Q3-T10-19)
CRON_PROPOSAL_ADR="0 1 * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} bin/ssot/proposal-to-adr.py >> ${WORKSPACE}/.omo/_delivery/resident-orchestrator/proposal-to-adr.log 2>&1"
CRON_HEALTH="10 2 * * * cd ${WORKSPACE} && PYTHONPATH=${PYTHONPATH} ${PYTHON_BIN} bin/ssot/system-health-check.py --emit >> ${WORKSPACE}/.omo/_delivery/resident-orchestrator/health.log 2>&1"

# 移除旧 marker 块(幂等),再追加新块
CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
CLEANED_CRON="$(printf '%s\n' "${CURRENT_CRON}" | grep -v -F "${CRON_MARKER}" | sed '/^$/N;/^\n$/D' || true)"

cat << EOF | crontab -
${CLEANED_CRON}
${CRON_MARKER}
${_ROLE_CRON}
${CRON_INGEST}
${CRON_SIGNALS}
${CRON_INBOX}
${CRON_PROMOTE}
${CRON_PROPOSAL_ADR}
${CRON_HEALTH}
EOF

echo "resident cron installed:"
crontab -l | grep -A9 "${CRON_MARKER}" | sed 's/^/  /'
