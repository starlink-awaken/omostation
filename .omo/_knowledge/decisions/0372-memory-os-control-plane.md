---
id: ADR-0372
title: Memory OS 控制面 — 统一记忆写读巩固与适配器边界
status: ACCEPTED
date: 2026-08-04
owner: governance-team
lifecycle: spec
last-reviewed: 2026-08-04
workflow_run: 20260804T115206Z-project-doc-change-7e6535ab
session: memory-os-p0
related:
  - 0294-knowledge-gateway-decoupling-and-event-pipeline.md
  - 0315-knowledge-to-action-loop.md
  - 0156-p76-phase2-call-direction.md
type: ssot
---

# ADR-0372: Memory OS 控制面

## Context and Problem Statement

eCOS 已具备多套记忆与知识基质（L4 Vault、`.omo/_knowledge`、KOS 索引、gbrain 混合 RAG/事实/dream 周期、cockpit cards 事件索引、KEMS 图谱、OMO 证据），以及半成品适配器（KOS `Mem0Adapter`、`MemThetaAdapter`）。

问题不是「没有记忆」，而是：

1. **无统一控制面**：Agent 必须自行选择 `bos://memory/kos/*` vs `gbrain/*` vs `inbox/*`；
2. **对话/偏好跨 session 写入契约缺失**；
3. **双轨（Raw/Theta）声明存在但 Theta 侧多为模拟**；
4. **巩固能力已在 gbrain dream/cycle，却未产品化为 workspace 级 job**；
5. **`bos://brain/events/card_updated` 越域债未清**（ADR-0294 已登记迁 `memory`）。

若直接引入 Mem0/Zep/Cognee 替换主存，将破坏 Vault 权威、BOS 分层与 OMO 审计模型。

## Decision Drivers

- 保持源与索引分离（Vault/ADR 权威，索引可重建）
- LAYER-CALL-DIRECTION：L3 不硬 import L2/I0 内核
- ADR-0315：检索 ≠ 行动成功；OMO 只存引用元数据
- 市面能力可插拔（Mem0 抽取、Graphiti 时序、Letta sleep-time 语义），不可做主存替换
- 诚实验收：禁止把半成品 adapter 当生产闭环

## Considered Options

| 选项 | 结论 |
|------|------|
| A. 用 Mem0 替换 gbrain/KOS | 拒绝 — 丢失 hybrid/图/dream 与 Vault 索引模型 |
| B. 用 Cognee 替换机构知识栈 | 拒绝 — 与 kronos→gbrain→kos 重叠 |
| C. 用 Letta 替换 agent runtime | 拒绝 — 与 OMO/Workflow Mesh 冲突 |
| D. **新增 Memory OS 控制面 + 多后端 + 可选 adapter** | **采纳** |
| E. 仅写文档不建控制面 | 拒绝 — 无法改变 agent 默认行为 |

## Decision Outcome

### D1. 引入 Memory OS（MOS）控制面

在 L2（优先 `projects/kairon/packages/mos`）实现统一 API，经 Agora 暴露：

| BOS URI | 职责 |
|---------|------|
| `bos://memory/mos/write` | 分类写入 + 双轨 |
| `bos://memory/mos/recall` | intent 路由 + 多后端融合 |
| `bos://memory/mos/consolidate` | 异步巩固（编排 gbrain dream，不重写 cycle） |
| `bos://memory/mos/forget` | 遗忘传播 |
| `bos://memory/mos/status` | 健康、积压、adapter 开关 |

专用后端 URI（`memory/kos/*`、`memory/gbrain/*`、`memory/kems/*`、`memory/inbox/*`）保留为直达后端。

### D2. MemoryEnvelope 为统一契约

由 eidos 托管 schema/validate。字段覆盖：`type`、`scope`、`content`/`content_ref`、`graph`、`temporal`、`provenance`、`lifecycle`、`governance`（含 PII）。长文优先 `content_ref`，禁止高 PII 正文写入 OMO raw。

### D3. 双轨硬化

- **Raw track**：可审计事件/元数据（OMO broker，不经脆弱 subprocess 拼 CLI 作为最终形态）
- **Theta track**：可检索节点（gbrain facts/pages 与/或 KOS 索引任务）
- Theta 失败不得抹掉 Raw；confidence 阈值进 SSOT（继承 MemTheta 0.6 思想）
- 现有 `MemThetaAdapter` 中 Theta 模拟路径不得标为生产完成

### D4. 适配器策略

| Adapter | 角色 | 默认 |
|---------|------|------|
| Mem0 | 对话/偏好抽取与 user-scope 个性化 | off/shadow → 硬化后可 on |
| Graphiti | bi-temporal 场景事实 | off；仅场景 enable |
| gbrain dream | sleep-time 巩固引擎 | 通过 mos.consolidate 编排 |

禁止：Mem0 on 时关闭 KOS；全局双图真相（gbrain + Graphiti 无单一 current-state 出口）。

### D5. 事件域

`bos://brain/events/card_updated` → `bos://memory/events/card_updated`。迁移 release 须 **双 pattern 兼容**（生产 emit 新 URI，consumer 同时接受新旧），再删旧。

### D6. 行动出口

MOS recall 的 citation 可挂 ADR-0315 knowledge_ref → OMO task；不得将 recall 成功解释为业务成功。

### D7. 分阶段

- **Phase 0**：文档、ADR、registry、审计、skill 默认路由（本 ADR 落地）
- **Phase 1**：mos 包 + Envelope + write/recall/status + 事件兼容迁移
- **Phase 2**：Mem0 硬化 + 真 Theta + 可选 closeout write + forget
- **Phase 3**：consolidate job + Foundry deck
- **Phase 4+**：Graphiti 场景、ACL、cockpit 面板

SSOT 注册表：`.omo/_truth/registry/memory-os.yaml`  
架构导航：`docs/architecture/memory-os.md`  
适配器审计：`docs/operations/memory-os-adapter-audit.md`

## Consequences

### Positive

- Agent 默认召回路径单一；机构知识与对话记忆分流
- 巩固复用 gbrain cycle，避免第二套引擎
- 市面能力以 adapter 进入，可关停、可 eval

### Negative / Risk

- 新增一层编排延迟（用超时预算与降级缓解）
- 多后端 RRF 有检索污染风险（intent 硬分流 + S8 测试）
- Phase 1 前 skill 只能文档引导，代码默认仍多 URI

### Neutral

- 不改变 Vault 路径 SSOT；不改变 ADR-0315 行动语义

## Confirmation

| 检查 | 方法 |
|------|------|
| ADR 入库 | INDEX 含 ADR-0372 ACCEPTED |
| Registry 存在 | `memory-os.yaml` 可被 safe_load |
| 审计诚实 | adapter audit 标明 MemTheta Theta 模拟、Mem0 可选 |
| Skill 默认入口 | `memory-recall` 指向 mos（P1 前文档降级 kos+gbrain） |
| 实施门 | Phase 1 起 `bos://memory/mos/recall` resolve 成功 |

## 不做

- 不替换 gbrain/KOS 主存
- 不把 Letta 作为 agent 运行时
- 不在本 ADR 启用 Graphiti 全局写
- 不宣称生产记忆准确率（须 eval 集）
