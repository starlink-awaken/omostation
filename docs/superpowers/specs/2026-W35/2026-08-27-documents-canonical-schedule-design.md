---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last-reviewed: 2026-08-27
bet_id: BET-Y1Q3-T10-25
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Documents canonical schedule candidate

## Objective

把已经完成 Workspace owner 对等验证的两项 Documents 观察任务编译成一份
可审计、可回滚的 canonical schedule candidate。文件只作为安装输入，不执行
宿主机 crontab/LaunchAgent 修改。

## Contract

- candidate schedule 位于 `.omo/cron/documents-content-plane-crontab`。
- 只替换两项：每日 06:25 consumer audit、每周一 06:35 freshness audit；
  两者与现有分钟/星期保持一致。
- 新命令从 Workspace 调用既有 owner 入口，所有 evidence/log 写入
  Workspace runtime/evidence；Documents 只读。
- 未完成 parity 的其余 Documents consumers 保持原 schedule，不得在本文件
  中假装已迁移。
- candidate 明确标记 `NOT INSTALLED`；安装前必须备份 crontab，安装后验证
  `crontab -l`、exit semantics、evidence 路径和至少一个触发周期。

## Acceptance

1. old/new schedule matrix contains exact cadence, owner, read/write roots,
   timeout and failure semantics for the two jobs.
2. candidate has no Documents-local executable path and passes static path audit.
3. dry-run commands resolve against a real Workspace checkout; no host schedule
   or Documents file changes occur.
4. rollback is restoring the pre-install crontab snapshot; no deletion occurs in
   this BET.
