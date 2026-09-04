---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-23
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Documents consumer audit and cutover gate

## Objective

建立一个只读的 Workspace 审计能力，通过既有 Documents owner job 入口扫描当前宿主机和仓库中仍执行
Documents 内脚本、数据库、缓存或控制面文件的消费者，并将每个消费者绑定
到既有 `documents-content-plane-migrations.yaml` family。审计结果只写
Workspace evidence，不修改 Documents、crontab、LaunchAgent 或客户端配置。

## Contract

- 输入：`DOCUMENTS_CONTENT_ROOT`（默认 `~/Documents`）、可选 `--crontab`、
  `--launch-agents-root`、`--scheduled-root` 和 Workspace migration registry。
- 输出：稳定 JSON `documents.consumer-audit.v1`，包含 source、consumer kind、
  command fragment、matched migration family、active/commented 判定和 summary。
- 默认来源为当前用户 crontab、`~/Library/LaunchAgents`、Documents
  `Claude/Scheduled`，并扫描域 `CLAUDE.md`/`AGENTS.md` 中的执行片段。
- 只报告，不执行发现的命令；文件读取不越出显式 root；无法读取的来源
  fail closed 为 `unavailable`，不伪造零消费者。
- registry family 只能来自既有 migration SSOT；未匹配消费者是错误。
- 入口必须复用 `bin/gac/documents-domain-owner-job.py consumer-audit`；实现位于
  `lib/documents_consumer_audit.py`，不得新增第二个 `bin/` 顶层入口。

## Non-goals

- 不执行或替换任何定时任务。
- 不移动、删除、chmod 或重写用户 Documents 数据。
- 不创建第二份迁移 registry、调度器或能力 owner。

## Acceptance

1. fixture 覆盖 active cron、comment-only cron、LaunchAgent argv、scheduled
   skill、domain gateway、unknown consumer、missing source。
2. 同一消费者重复扫描时输出稳定排序和稳定 consumer id。
3. 文本中被注释掉的命令不算 active；shell 行续接和引号路径保持完整。
4. live scan 能明确证明当前仍存在的 Documents consumers，并把结果写入
   Workspace state/evidence root，而不是 Documents。
