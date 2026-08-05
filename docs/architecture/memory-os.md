---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-08-04
related:
  - ../../.omo/_knowledge/decisions/0372-memory-os-control-plane.md
  - ../../.omo/_truth/registry/memory-os.yaml
  - ./gbrain-three-stack-split.md
  - ../operations/memory-os-adapter-audit.md
  - ../operations/knowledge-foundry-sop.md
---

# Memory OS（MOS）— 架构导航

> **SSOT 决策**: ADR-0372  
> **机器注册表**: `.omo/_truth/registry/memory-os.yaml`  
> **本文职责**: 导航与契约指针，不硬编码运行时计数。

## 1. 一句话

MOS 是 eCOS 的**统一记忆控制面**：类型化写读、双轨审计、intent 召回编排、异步巩固与可关停适配器——**不**替换 Vault / KOS / gbrain / OMO。

## 2. 分层位置

```text
L3  cockpit / agent skills     →  默认走 mos.recall / write（网络 BOS）
I0  agora                      →  bos://memory/mos/*
L2  kairon/packages/mos (P1)   →  控制面实现
L2  kos / gbrain / eidos       →  后端与契约
L2  omo                        →  raw track + knowledge_ref（ADR-0315）
L4  Vault / ADR                →  权威源（不搬家）
```

## 3. 记忆类型 × 权威后端

| Type | 含义 | 权威/主后端 |
|------|------|-------------|
| working | 当前上下文 | session / run 上下文 |
| episodic | 发生过的回合/事件 | OMO raw 元数据 + gbrain/可选 Mem0 |
| semantic | 稳定事实/偏好 | gbrain facts（Theta） |
| procedural | 怎么做 | skills / workflows（弱反馈 P2+） |
| institutional | 机构/笔记/文档 | Vault 源 + KOS 索引 |
| governance_ref | 可审计引用 | OMO evidence / ADR-0315 |

## 4. BOS 面

| URI | 阶段 | 说明 |
|-----|------|------|
| `bos://memory/mos/write` | P1 | 统一写入 |
| `bos://memory/mos/recall` | P1 | 统一召回 |
| `bos://memory/mos/status` | P1 | 健康与积压 |
| `bos://memory/mos/forget` | P2 | 遗忘传播 |
| `bos://memory/mos/consolidate` | P3 | 编排 gbrain dream 子集 |
| `bos://memory/mos/knowledge-ref` | P4 | ADR-0315 引用元数据 |
| `bos://memory/events/card_updated` | P1 迁移 | 替代 `bos://brain/events/*` |
| `bos://memory/kos/*` 等 | 既有 | 后端直达，保留 |

入口（与 registry `entry_points` 对齐）：`cockpit memory …` · `/api/memory/*` · Agora MCP via `bos://memory/mos/*`。

路由表与 adapter 开关见 registry，勿在本文复制易漂移默认值。

## 5. 双轨

```text
write
  ├─ Raw  → OMO memory.* 事件（元数据 + hash，无高 PII 正文）
  └─ Theta → gbrain facts/pages 与/或 KOS 索引任务
```

Theta 失败保留 Raw 并入重试队列。详见 ADR-0372 §D3 与 adapter audit。

## 6. 召回编排（逻辑）

```text
query + scope + intent?
  → route_table[intent]
  → parallel backends (timeout budget)
  → scope/ACL/forgotten filter
  → RRF / weighted merge
  → citations（可挂 knowledge_ref）
```

**硬分流**：`code_structure` → codebase-memory；`task_debt` → governance——禁止与笔记混 RRF。

## 7. 巩固（Sleep-time）

- **引擎**: 既有 `gbrain dream` / `runCycle()`（含 extract_facts、consolidate 等 phase）
- **控制面**: `mos.consolidate` 只做编排与指标，**禁止**第二套 consolidate 守护进程
- **调度**: Foundry / cron（P3）

## 8. 与知识网关关系

卡片路径仍走 cockpit PUT → EventBus → KnowledgeIndexer（ADR-0294）。  
MOS 增加：统一 agent 默认召回、对话记忆、巩固与遗忘；事件 URI 迁 `memory` 域。

运维 SOP 指针: [`../operations/knowledge-foundry-sop.md`](../operations/knowledge-foundry-sop.md) §5。

## 9. 市面能力映射

| 外来 | 采用方式 |
|------|----------|
| Mem0 | 可选 adapter：对话/偏好抽取 |
| Graphiti/Zep | 可选 adapter：bi-temporal 场景 |
| Letta sleep-time | 语义对齐 dream/consolidate job |
| Cognee | 不引入（与机构知识栈重叠） |

## 10. 阶段指针

| Phase | 交付 |
|-------|------|
| 0 | 本文 + ADR-0372 + registry + audit + skill — **done** |
| 1 | `packages/mos` MVP + BOS + dual-track + card dual-accept — **done** |
| 2 | Mem0 shadow + forget bus + eval v0 + BOS forget — **done** |
| 3 | consolidate + Foundry deck + BOS — **done** |
| 4 | temporal shadow + scope ACL + knowledge_ref — **done** |
| 5 | fine ACL + Graphiti bridge flag + cockpit `/api/memory` — **done** |
| 6 | Neo4j FACT 写路径 + 策略表 RBAC + cockpit `/memory` 面板 — **done** |
| 7 | Neo4j recall 挂入 `temporal_fact`/`entity_relation` 检索闭环 + 本机 docker/brew 启动脚本 — **done** |
| 8 | 进程 env 注入 + 端口登记 + 运维契约 + surface check — **done** |
| 9+ | 完整 graphiti-core 引擎、as_of 图侧 bi-temporal、Mem0 真集群 |

实现入口：`projects/kairon/packages/mos` · CLI `python -m mos` / `cockpit memory`  
本机图：`bash bin/memory-os-neo4j-up.sh` · 环境：`source bin/memory-os-env.sh`  
史诗复盘：`docs/operations/memory-os-epic-retro.md`  

运维契约：`.omo/standards/memory-os-ops.md` · 检查：`make memory-os-check`

## 11. 相关入口

- Agent skill: `.agents/skills/memory-recall/SKILL.md`
- 适配器审计: `docs/operations/memory-os-adapter-audit.md`
- 知识→行动: ADR-0315
- gbrain 拆分草案: `docs/architecture/gbrain-three-stack-split.md`
