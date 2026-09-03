---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last-reviewed: 2026-08-27
bet_id: BET-Y1Q3-T10-21
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# L4 / Documents / Agora 单实例收敛设计

## 1. 目标

建立一个 canonical L4 Kernel，消除 Workspace 主 L4 与 Agora nested L4 的身份、版本、域模型和运行路径分裂；将 Documents 收敛为内容、声明、人工决策和证据平面，将执行、状态、缓存、调度、知识运行时和任务审批归入既有 Workspace owners。

## 2. 事实基线

- canonical Workspace L4: `projects/l4-kernel`，当前审计基线为 `f3d6979`。
- Agora nested L4: `projects/agora/projects/l4-kernel`，当前审计基线为 `cdab5c6`。
- 两个目录来自同一远程仓库，但 nested 版本早于 canonical 版本；Agora MCP bootstrap 与 BOS fallback 会按相对 `projects/l4-kernel` 路径启动 nested 实现。
- canonical L4 的职责是 ManifestRegistry、Domain Contract、Content Plane Audit 和 T0-T8 Harness；Documents registry 将域身份声明指向 L4，Cockpit 提供 Workspace 人机入口，OMO/Runtime/Kairon-KOS 分别负责决策执行、运行 owner 和知识运行时。

## 3. 不可违反的边界

Documents 保留 Markdown、Office/PDF 内容、`DOMAIN.yaml`、`CONTENT_ARCHIVE.yaml`、方法规则、人工决策和最终证据；不得新增 runtime、cache、daemon、数据库、workflow execution 或本地 KEMS runtime。

Workspace 承载能力实现、任务与审批、调度与运行状态、缓存与索引、owner jobs、审计 receipt 和服务路由。L4 不承载 KEMS ingest/eval/graph，也不成为第二 workflow engine。

本轮只设计和固化控制面，不删除 nested L4，不更新 root/Agora gitlink，不移动或删除用户 Documents 内容，不切换生产调度、客户端 MCP 或运行时路由。

## 4. Canonical identity and route

每次 L4 调用必须可复算并返回：`l4_instance_id`、`source_repository`、`commit_sha`、`registry_digest`、`interface_profile`、`documents_root` 和 `runtime_state_root`。

Agora 必须优先通过 `bos://governance/l4-kernel/domains` 解析 canonical L4；本地 fallback 只能使用显式 `L4_KERNEL_COMMAND` / `L4_DOMAIN_REGISTRY`，禁止从 Agora 代码位置推断 nested 路径。相同 BOS URI、服务名或 profile 不得映射多个 L4 commit。

## 5. 迁移波次

1. 身份冻结：登记两个实例、版本、工具面、Registry 和全部消费者，建立双实例差异 receipt。
2. 路由切换设计：Agora 改为 canonical BOS/显式命令，保留 nested 实例作为可回滚材料；切换前完成 source/consumer/cutover/rollback 证据。
3. Documents owner migration：按 runtime、cache、bridge、projection、content archive 分类，把执行代码迁至 L4/Runtime/Cockpit/OMO/Kairon-KOS。
4. 双实例 canary：对 registry、domain context、content audit、harness、health 和 MCP profile 做同输入对比。
5. nested retirement：consumer=0、schedule=0、route 唯一、canary 通过且 rollback 可用后，才另行授权删除 nested submodule。

## 6. Governance and operations

Blocking checks must cover nested-L4 presence, route uniqueness, instance identity, registry digest drift, Documents T8 violations, Runtime/Contents root overlap, owner-job timeout/non-zero propagation, legacy consumer count and evidence freshness. Every physical migration records before/after SHA-256, file/byte counts, tree digest, consumer scan and rollback package.

Operational SLOs are canonical route availability, owner-job freshness, truthful failure rate, T8 violation reduction, legacy consumer reduction and human-accepted real outcomes. Tool count, domain count and governance score are not value proxies.

## 7. Acceptance

- Design and spec are committed with the exact BET binding.
- The existing Documents convergence plan includes the nested-L4 wave without authorizing deletion or client cutover.
- Root/Agora/L4 paths and current commit differences are recorded in an inventory receipt.
- All control paths are fail-closed on route ambiguity, identity mismatch, root overlap or missing rollback evidence.
- Verification is limited to static/document SSOT checks in this design wave; runtime route cutover and physical Documents migration require separate waves and evidence.
