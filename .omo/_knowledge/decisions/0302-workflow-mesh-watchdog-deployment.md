---
id: ADR-0302
title: Workflow Mesh watchdog 真实 cadence 与运行账本
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
created: 2026-08-02
last_updated: 2026-08-02
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../standards/agent-cli-worker-collaboration.md
  - ../../_knowledge/decisions/0301-workflow-mesh-watchdog.md
---

# ADR-0302: Workflow Mesh watchdog 真实 cadence 与运行账本

## 背景

ADR-0301 已定义租约过期扫描和只写 `WorkerLeaseExpired` 的边界，但还需要把扫描接入既有
运行 cadence，并留下可审计的每次运行摘要。若再在 OMO 内新增 scheduler，会形成第二套时间
驱动和竞态；若只输出终端文本，则无法判断扫描是否持续运行、是否重叠或是否因账本失败而丢失证据。

## 决策

1. 复用现有 `omo daemon`、cron 或 launchd 的 cadence；OMO 只提供
   `mesh_watchdog_runner.run_once()` 和 `omo worker mesh-watchdog-run` 单次适配器，不新增 scheduler。
2. runner 使用跨进程非阻塞锁，同一时刻最多一个扫描；锁竞争返回 `skipped/already_running`，不等待、不修改 Mesh。
3. 默认模式为 `dry_run`；只有显式 `--apply` 或 daemon 的显式 apply 配置才允许追加 `WorkerLeaseExpired`。
4. 每次运行将隐私安全摘要追加到 `.omo/_log/workflow-mesh-watchdog-runs.jsonl`，并更新
   `.omo/_log/workflow-mesh-watchdog-latest.json`；摘要只保留统计、WorkflowRun 标识、状态和错误摘要，禁止 prompt、模型输出和外部原文。
5. 扫描、账本或输入校验失败均 fail-closed；runner 不选择 successor、不追加 `WorkerReclaimed`、不执行 worker。

## 不变量

- 既有 Mesh 事件日志和投影仍是状态真相，runner 日志只是运行证据。
- 重复 apply 继续由既有 Mesh 幂等合同去重，不产生重复过期事件。
- dry-run 不修改 Mesh；锁竞争不修改 Mesh。
- cadence 可以被停用或降级，不会绕过 admission、StepRun、worker 身份和权限合同。

## 验收

- `omo daemon start` 默认每个 tick 运行 watchdog dry-run，`--no-mesh-watchdog` 可显式停用。
- `omo worker mesh-watchdog-run --json` 返回结构化状态，并在 `_log` 留下运行摘要。
- 并发运行中只有一个扫描，其余返回 `skipped`；扫描错误返回 `degraded/failed` 和非零 CLI 状态。
- 显式 apply 只追加过期事件，重复执行保持幂等，且不会自动 reclaim。
