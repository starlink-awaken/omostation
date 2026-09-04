---
id: ADR-0301
title: Workflow Mesh Watchdog 只写过期事件
status: archived
type: decision
owner: architecture-governance
lifecycle: spec
last_updated: 2026-08-02
related:
  - ../../standards/agent-cli-worker-collaboration.md
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - ../../_truth/registry/agent-workflows.yaml
---

# ADR-0301: Workflow Mesh Watchdog 只写过期事件

## 背景

Workflow Mesh 已经持久化 worker ACK、heartbeat、lease expiry 和 reclaim，但此前过期检测仍主要依赖人工调用 `mesh-expire` 或读取旧 dispatch YAML。这样会让运行态证据与实际 worker 失联，影响恢复时间和 Cockpit 对运行状态的可信度。

## 决策

OMO 新增 `scan_worker_leases()` 以及 `omo worker mesh-watchdog`：

1. 直接读取 Workflow Mesh append-only 事件日志及其投影，不把 dispatch YAML 当事实来源；
2. 默认 `dry_run`，供调度器、人或 Cockpit 安全预览；
3. 只有显式 `--apply` 才追加 `WorkerLeaseExpired`，并复用既有 admission、StepRun、worker context 和幂等键；
4. watchdog 不选择 successor、不写 `WorkerReclaimed`、不执行 worker；reclaim 仍由 coordinator 按独立审批和恢复上下文决定；
5. cadence 复用现有 cron/launchd/daemon，不在 OMO 内新增第二套 scheduler。

## 不变量

- 未到期 lease 不得改变状态；
- 同一过期 lease 重复扫描不得产生重复事件；
- 过期事件缺少 admission、StepRun 或 worker 身份时 fail-closed 并返回错误；
- watchdog 的输出只包含运行标识、时间、状态和错误摘要，不包含 prompt、模型输出或外部原文。

## 验收

- dry-run 不增加 Mesh 事件；
- apply 将 live worker 投影为 `lease_expired`，重复 apply 保持幂等；
- apply 不自动生成 `WorkerReclaimed`；
- 未到期 lease 保持原状态；
- CLI 支持 JSON 输出，适合已有调度基础设施调用。
