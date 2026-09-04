---
title: Hermes 治理边界声明 (OPS-INFRA 任务 3)
type: contract
owner: xiamingxing + governance-team
created: 2026-08-17
last_updated: 2026-08-17
related:
  - docs/OPS-INFRA-GOVERNANCE-LONGTERM-BLUEPRINT-2026-08.md
lifecycle: contract
---

# Hermes 治理边界声明

> 实测基础：`~/.hermes/cron/jobs.json` 12 任务在册（2026-08-17 直读）。

## Q1 谁维护 Hermes？

**夏明星本人 + 本机 Agent 协作维护，无专职 owner。** Hermes 是本机安装的调度器
（`~/.hermes/`），其 12 个内置任务（omo-cleanup / omo-drift-detection / omo-self-evolve /
omo-governance-audit / omo-lint-metrics / omo-healing-check / omo-gov-heartbeat /
workspace-health-scan / arc-conv-gate-verification / arcnode-validate / m1-model-sync /
gateway日志轮转）由装机时的 agent 批量注册，此后**无人系统性复核**。这是真实状态，如实记录。

## Q2 失败有无告警？

**没有主动告警。** 现状只有被动痕迹：
- `~/.hermes/cron/ticker_heartbeat` / `ticker_last_success`（ticker 级，任务级无独立心跳文件）
- `~/.hermes/cron/governance.jsonl`（仅 governance 任务自记）
- `executions.db`（执行历史 SQLite，无人查询）

**实证**：同机 crontab 的 dashboard 任务静默失败 11 天无人知晓（见
`.omo/_knowledge/audits/2026-08-17-scheduling-overlap-verification.md` §③）——
Hermes 任务若同样失败，可预期同样长的静默窗口。**建议**（供排期，非本轮）：
`omo-gov-heartbeat`（10:00）扩展为读 executions.db 近 24h 失败计数，非零时写
`.omo/_delivery/alerts/` 并由 signal-poller 感知——用已有任务承载告警，零新调度。

## Q3 新增/修改 Hermes 任务是否走审批？

**约定如下（即日生效）**：

| 变更类型 | 要求 |
|---|---|
| 会写 Workspace 仓库文件的任务（如 omo-* 系列） | 变更前过一次 grill 或在会话中知会夏明星；变更本身走 ADR-0203 workflow |
| 纯本机运维（日志轮转、cache 清理） | 不强制审批，但 jobs.json 变更需在本文件 `last-reviewed` 追记一行 |
| 删除任务 | 同第一类（防止静默禁用无人知） |

**红线**：任何 agent 不得因"Hermes 不在台账"而视其为无主之地擅自增删——
Hermes 12 任务是 Workspace 治理面的事实组件，本声明即其边界契约。
