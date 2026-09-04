---
schema_version: architecture/v1
status: proposed
owner: governance-team
last_updated: 2026-08-27
bet_id: BET-Y1Q3-T10-21
title: L4 / Documents / Agora 单实例收敛架构 v1
type: doc
lifecycle: history
---

# L4 / Documents / Agora 单实例收敛架构 v1

## 1. 战略结论

Workspace 只保留一个 canonical L4 Kernel。Documents 是内容、声明、人工决策和证据平面；Workspace 承载能力、执行、状态、缓存、调度、知识运行时和任务审批；Agora 只负责 BOS/MCP 注册、发现和路由，不再携带第二份 L4 源码。

本设计不授权删除、物理迁移、客户端切换或生产路由切换；这些动作必须在后续独立波次中以 consumer、canary、rollback 和人类确认作为前置条件。

## 2. 目标形态

```text
Documents
  ├─ Markdown / Office / PDF 内容
  ├─ DOMAIN.yaml / CONTENT_ARCHIVE.yaml
  ├─ 方法、规则、人工决策
  └─ 最终报告与 evidence
        │ read-only
        ▼
Workspace L4 (唯一实例)
  ├─ ManifestRegistry
  ├─ Domain Contract Loader
  ├─ Content Plane Audit
  ├─ T0-T8 Harness
  └─ instance identity / receipts
        │
        ├─ Cockpit：唯一人机入口
        ├─ OMO：任务、审批、CARDS、委托
        ├─ Runtime：owner jobs、状态、调度、缓存
        ├─ Kairon/KOS：ingest、检索、知识图
        └─ Agora：BOS/MCP 路由
```

## 3. 唯一职责

| 层 | 唯一职责 | 明确不拥有 |
|---|---|---|
| Documents | 内容、声明、证据、人工决策 | daemon、数据库、cache、workflow execution |
| L4 | 域身份、契约解析、内容分类、T0-T8 | KEMS runtime、任务审批、worker execution |
| Cockpit | 人机入口、只读投影、人工确认 | 业务内核、独立 runtime |
| OMO | 任务、审批、CARDS、委托 | 文档索引、域内脚本执行 |
| Runtime | owner jobs、调度、状态、缓存、运行证据 | 域身份和业务语义 |
| Kairon/KOS | ingest、eval、graph、search | 任务审批、外发决策 |
| Agora | BOS registry、发现、路由、断路器 | L4 源码副本、第二 Registry |

## 4. L4 实例身份

每次 L4 调用必须绑定并可复算：

```text
l4_instance_id
source_repository
commit_sha
registry_digest
interface_profile
documents_root
runtime_state_root
```

同一 BOS URI、服务名或 MCP profile 不得解析到多个 L4 commit。任何 instance、registry 或 profile 不一致都必须 fail closed。

## 5. Agora 路由与 nested L4

`projects/agora/projects/l4-kernel` 是历史 nested submodule，不是新的长期 owner。Agora 生产启动顺序必须是：

1. 通过 `bos://governance/l4-kernel/domains` 解析 canonical L4；
2. 本地开发才允许使用显式 `L4_KERNEL_COMMAND` 与 `L4_DOMAIN_REGISTRY`；
3. 禁止根据 `__file__`、父目录或相对 `projects/l4-kernel` 推断实现路径；
4. nested L4 保留为回滚材料，直到 consumer scan、双实例 canary 和 rollback drill 完成；
5. 单独的退役波次才可以删除 nested submodule。

## 6. Documents / Workspace 隔离

Documents 允许 `DOMAIN.yaml`、`CONTENT_ARCHIVE.yaml` 和可审计文档，但禁止新增执行代码、数据库、缓存、调度器和可变运行状态。Runtime state 必须位于 Workspace 的独立根，且通过路径策略保证与 Documents root 不重叠。

历史代码不直接删除：先建立合法 `CONTENT_ARCHIVE.yaml`、树指纹、消费者扫描和回滚包；有 active consumer 的资产不得归档或退役。

## 7. 控制面

### 7.1 默认接口

L4 默认生产 MCP profile 只暴露契约、Registry 只读和 Harness；旧 KEMS、文件写入、域生命周期、插件执行和 workflow 入口只能进入显式 legacy profile，不能进入普通 Agent discovery。

### 7.2 迁移控制

每个迁移族必须记录：

```text
source
owner
consumer_refs
replacement
before_sha256
after_sha256
file_count / byte_count
tree_digest
rollback
cutover_receipt
```

迁移顺序固定为：owner 实现 → parity 验证 → consumer 切换 → 观测 → 旧面退役。

### 7.3 失败闭环

以下任一情况停止切换：canonical route 不唯一、instance mismatch、registry digest drift、Documents/Runtime root overlap、owner job timeout/非零传播不一致、rollback evidence 缺失或 T8 违规增加。

## 8. 应用场景

### 卫健委材料

```text
官方通知/平台导出
  → Documents 保存原件
  → L4 校验域与内容契约
  → Runtime 抽取事实
  → OMO 生成任务与问题卡
  → Cockpit 人工确认
  → Runtime 生成报告
  → Documents 保存最终报告与证据
```

### 个人知识

```text
Documents 原文 → L4 域/权限判断 → Kairon/KOS 检索
  → Cockpit 展示引用 → OMO 形成后续行动
```

### 架构治理

```text
Documents 规范/ADR → L4 Harness → OMO workflow
  → Runtime owner check → Cockpit receipt → Documents evidence
```

## 9. 运维模型

持续观测：

```text
L4 instance identity drift
Registry digest drift
duplicate BOS route
nested L4 presence
Documents T8 violation count
Runtime/cache residual count
owner job freshness
legacy consumer count
false-green count
human-accepted real outcomes
```

工具数、域数量、规则数量和治理分数不作为价值指标。长期北极星是每周被本人接受的、具备证据链的真实结果数量。

## 10. 验收门

设计波次：

- 两个 L4 实例的路径、commit、域模型、工具面和消费者差异可复算；
- canonical identity 和 route contract 已定义；
- Documents/Runtime 根隔离和 fail-closed 规则已定义；
- nested L4 退役条件和 rollback 条件已定义；
- 既有 Documents convergence plan 已纳入 nested-L4 波次；
- 本波次不声称已完成生产切换、物理迁移或 nested L4 删除。

## 11. Documents 能力下沉决策（T10-41）

可以下沉，但必须按“能力边界”而不是按“文件后缀”下沉：

- Documents 只保留原始材料、最终报告、证据、DOMAIN/CONTENT 声明、方法规则和人工决策；
- Workspace 统一承载 owner job、cron/LaunchAgent、运行状态、缓存、索引、数据库和结构化 evidence；
- L4 负责域身份与内容契约，不能变成第二个脚本运行时；
- Kairon/KOS 负责知识 ingest/search/graph，不能把数据库或索引重新落回 Documents；
- 仍被 Workspace 只读消费的 Documents 文件不是“执行器”，不能误删；
- 未知消费者、语义不等价或无法回滚的文件保持 unresolved，不做物理动作。

迁移采用两阶段闸门：先迁消费者和 owner，再对 `Documents/_runtime`、`.kems`
中的生成物做可恢复 quarantine；永久删除必须由独立人类确认的 BET 承担。这样既能
让 Documents 变成真正的内容平面，也不会把历史证据、业务报告和可恢复性一起清掉。
