---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-13
type: ssot
last_updated: 2026-09-03
---

# 编排器无关交付合同 MVP 设计

## 目标

把已存在的 ECOS `WorkPacket`、`CompletionManifest` 与
`VerificationReceipt` 接入 OMO 的 Agent Workflow / Workflow Mesh 运行真相，
形成可被 Orca、Kandev、Multica、Ruflo 或任意 CLI 复用的最小交付闭环。

本设计不创建新的任务台账、工作流状态机或调度器。外部编排器只负责运输；
BET、Agent Workflow run、claim、Workflow Mesh 事件与独立验证仍由 Workspace
拥有。

## 采用方案

采用“恢复既有合同 + OMO 薄协调器 + 离线 adapter conformance”方案。

- ECOS 继续拥有 `WorkPacket`、`CompletionManifest`、`VerificationReceipt`
  及其规范哈希与平台 envelope。
- OMO 新增一个窄协调器，验证身份链、候选清单、外部 evidence 与独立验证
  回执，并按既有 Workflow Mesh 合法顺序追加事件。
- adapter 统一为 `dispatch / observe / interrupt / collect` 四函数协议；本轮只用
  Kandev JSON fixture 证明映射，不启动 Kandev、不联网、不派真实任务。
- `VerificationVerdict` 只是 `VerificationReceipt.verdict` 的领域称谓，不新增
  M2 或第二张状态表。

## 身份与哈希合同

唯一因果链为：

```text
bet_id
→ workflow_run_id (= Workflow Mesh workflow_run_id)
→ packet_id + packet_hash
→ assignment_id
→ external_task_id
→ receipt_id / EvidenceRecorded
→ verification receipt_hash
```

`packet_hash` 只覆盖战略不变量：objective、scope、AC、budget、rollback、
circuit breaker 与 assignment 约束。编排器名称、external task id、时间戳、
轮询状态和 UI 元数据不得改变 packet hash。

同一 `external_task_id` 绑定不同 `packet_hash`、同一 packet 出现内容冲突的
manifest、或收集后 manifest 发生变化时，协调器必须 fail closed。

## 运行顺序

成功候选必须遵循：

```text
WorkflowRequested
→ WorkflowAdmitted
→ StepDispatched / StepStarted
→ WorkflowSucceeded
→ EvidenceRecorded
→ VerificationReceipt.accept
→ WorkflowVerified
→ Agent Workflow closeout / WorkflowClosed
```

`revise` 或 `reject` 不得追加 `WorkflowVerified`。transport failed/unavailable
不得伪造 succeeded external receipt 或 evidence。重复提交同一 receipt 必须幂等。

MVP 只承接 R1：verifier 必须只读、direct measurement、不信任 executor 自报；
确定性 verifier 可不强制不同模型家族。R2/R3 继续遵守不同模型/Agent 与人类门。

## 组件边界

### ECOS

不改既有 M2。只把当前根 gitlink 所含的合同和 105-test 基线视为权威输入。

### OMO

新增单一职责的交付协调模块：

- 验证 WorkPacket / CompletionManifest / VerificationReceipt；
- 校验 changed paths、AC、hash、assignment 与 run identity；
- 调用既有 external receipt broker；
- 在 accept 时追加既有 `WorkflowVerified`；
- 只返回候选/拒绝/阻塞结果，不自行 merge、promote 或 close BET。

### Adapter

定义协议与 Kandev 离线 mapper。adapter 不拥有优先级、Done 定义、写权限、
Gate 决策或 Workspace 状态；live 方法默认 `not_enabled`。

## 错误语义

稳定错误至少区分：

- `packet_hash_mismatch`
- `manifest_scope_violation`
- `manifest_conflict`
- `transport_failed`
- `evidence_missing`
- `verification_revise`
- `verification_rejected`
- `verification_unprovable`

任何解析、存储、状态或身份异常均拒绝晋升，不得 catch 后映射为 accept。

## 验收

1. 同一 WorkPacket 的 adapter 元数据变化不改变规范 hash。
2. 正常 Kandev fixture 经 OMO 形成 `EvidenceRecorded` 和 `WorkflowVerified`，
   且共享同一 workflow run / packet / assignment 因果链。
3. 篡改 packet、越界 changed path 或冲突 manifest 被拒绝，事件流无
   `WorkflowVerified`。
4. transport failure 不生成 succeeded evidence。
5. 同一 receipt 重放不增加事件，冲突重放 fail closed。

验证必须运行既有 ECOS 合同测试、OMO 新增测试以及 Workflow Mesh / external
receipt 回归。只验证 schema 或文件存在不算完成。

## 非目标

- 不安装、启动或联网调用 Kandev；不接其 MCP/API/ACP。
- 不接第二个 adapter；不改 Orca、Multica、Ruflo。
- 不新增 Cockpit/UI/BOS/Agora/MCP 入口。
- 不新增数据库、Ledger DDL、顶级项目、task queue 或 workflow state machine。
- 不做 scheduler、watchdog、自动 retry、自动 merge/promotion。
- 不做 R2/R3、多用户、跨主机、分布式并发或 exactly-once。
- 不执行真实外部副作用。

## 回滚与断路器

回滚为移除 OMO 薄协调器与 fixture adapter；ECOS 合同、Agent Workflow 与
Workflow Mesh 均不变。若实现需要修改 Workflow Mesh 状态机、Ledger DDL、
外部服务或超过两个生产模块，立即停止并拆包，不得扩大本 BET。
