# OPC-P2-T1 memory-boundary 5 仓设计文档

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P2 (Memory spine) T1 — 5 仓记忆边界设计
> **目的**: 给后续 T2 memory-uri + T3 recall-flow + T4 source-map 提供边界基线
> **链接**: OPC-PHASE-PLAN.yaml OPC-P2-T1 / §19 治理 / M1.5 Gate B2 收口
> **属性**: 历史 OPC 设计输入 / reference only。本文记录 OPC-P2-T1 当时的 5 仓边界设计，不是当前记忆边界实现状态、当前 owner 分配或当前系统事实 SSOT。
> **当前事实**: 请回看 `/.omo/PROJECTS.yaml`、`/docs/PANORAMA.md`、当前 OPC 审计/交付证据与治理检查结果。

---

## §1.0 一句话总结

**OPC-P2-T1 划定 5 仓记忆边界：gbrain / kairon-KOS / cockpit / metaos / .omo，每个边界单一 owner，边界间仅通过源指针引用，canonical memory 物理层 SSOT。**

## §1.1 5 仓记忆层对账

| 仓 | 物理存储 | Owner | 主存数据类型 | 边界 | 当前状态 |
|----|---------|-------|-------------|------|---------|
| **gbrain** | PGlite (默认) / Postgres | gbrain | pages, content_chunks, embeddings, facts, takes | **Canonical memory** (主) | 🟢 167 tests + 163K TS |
| **kairon-KOS** | 散在 16 packages (kronos/minerva/sophia) | kairon | ontology, research, code analysis | **领域知识图谱** (专用) | 🟢 16 live packages |
| **cockpit** | SQLite (local DB) | cockpit | contracts, status, work snapshots, decision audit | **会话/工作状态** (短期) | 🟢 13 CLI + 37 MCP |
| **metaos** | SQLite (per-user ~/.metaos) + JSON 文件 | metaos | D Layer 数字资产, A2A 任务, 决策门控 | **数字资产 / 决策日志** | 🟢 163 tests |
| **.omo** | YAML + JSONL (workspace 根) | omo | goals, tasks, debt, audit, knowledge, plans | **治理债 + 计划** (元层) | 🟢 治理平面 4-Plane |

## §1.2 边界原则

### §1.2.1 单一 owner
每个数据类型**只能有一个 owner**。其他仓**不复制**数据，只通过**源指针**引用。

| 数据类型 | 唯一 Owner | 引用方式 |
|----------|-----------|----------|
| 个人笔记 (page/fact) | gbrain | `bos://gbrain/page/<slug>` |
| 领域 ontology | kairon-KOS | `bos://kairon/kos/<concept>` |
| 工作快照 / 任务 | cockpit | `bos://cockpit/work/<id>` |
| 决策门控 / 数字资产 | metaos | `bos://metaos/asset/<id>` |
| 治理债 / 计划 / 状态 | .omo | `bos://omo/task/<id>` |

### §1.2.2 边界间引用
- 跨边界引用**只通过源指针**（URI 引用，不复制内容）
- §19 治理平面已用 `bos://...` URI 统一（`protocols/port-registry.yaml` + `INTERFACE.yaml`）
- 引用不持久化**值**（避免双写漂移）

### §1.2.3 SSOT 物理层
**canonical memory 物理层 = gbrain**（pages/facts/takes/chunks），其他 4 层都通过 bos:// URI 引用 gbrain。

**理由**:
- gbrain 有最完整 schema + PGlite WASM 默认 + Postgres 升级路径
- §18.10 多仓对比表已把 gbrain 列为 §12 跨仓 SSOT 落盘点
- R50/E1 已实质化 gbrain AppendOnlyLog 6 写点（canonical memory 入盘）

## §1.3 路由策略草案 (T2 输入)

```
bos://memory/**     →  gbrain    (canonical: pages/facts/takes)
bos://ontology/**   →  kairon-KOS
bos://work/**       →  cockpit    (working state, snapshot)
bos://asset/**      →  metaos    (D Layer digital assets)
bos://governance/** →  .omo      (tasks/debt/plans)
```

## §1.4 关键决策（需 owner 配合）

| # | 决策项 | 推荐方案 | 涉及仓 |
|---|--------|---------|--------|
| 1 | cockpit 当前 local DB 数据（contracts/status/decision）**是否迁 gbrain？** | **保留 local DB，bos:// 引用** | cockpit, gbrain |
| 2 | metaos D Layer 资产**是否同步到 gbrain page？** | **不复制，bos:// 引用** | metaos, gbrain |
| 3 | kairon-KOS ontology **是否与 gbrain page 类型融合？** | **不融合，bos:// 跨边界** | kairon, gbrain |
| 4 | .omo 治理债**是否暴露为 bos:// URI？** | **T2 实施，统一 URI** | omo, agora |
| 5 | 跨边界搜索（recall-flow）走 Agora 代理 | **T3 实施** | agora, all 5 |

## §1.5 不变量 (来自 §19 + M1.5)

1. **SSOT 物理**: 同一数据**只 1 处物理**（其他处为指针引用）
2. **DRY**: 5 仓各自不维护其他仓数据的副本
3. **边界清晰**: 跨边界调用**只通过 bos:// URI**（不直接 import）
4. **§12.6 跨仓债**: E1-E4 已收口 (AppendOnlyLog 4/4 落盘)
5. **持久化风险**: 5 仓 0 风险 (OPC-P2-T0 已实质化)

## §1.6 推进路径 (T1 → T2-T5)

| 任务 | 内容 | 工作量 |
|------|------|--------|
| **OPC-P2-T1** (本任务) | 5 仓记忆边界设计 | ✅ done (本 doc) |
| **OPC-P2-T2** | memory-uri 路由策略实施 (`bos://memory/**` 配置 + Agora 路由表) | 1 Round |
| **OPC-P2-T3** | recall-flow (collect→ingest→search→output→archive) | 2 Round |
| **OPC-P2-T4** | source-map (source/timestamp/owner/freshness) | 1 Round |
| **OPC-P2-T5** | memory-metrics (recall precision/attribution coverage) | 1 Round |

**Gate C acceptance** (T1+T2+T3+T4+T5 全部完成):
- ✅ kairon/gbrain/metaos persistence risks resolved (T0 完成)
- 🔄 search surfaces declare scope (T3)
- 🔄 outputs include source metadata (T4)
- 🔄 one real question flows collect→ingest→search→output→archive (T3)

---

**OPC-P2-T1 设计完成。** 5 仓记忆边界 + 单一 owner + bos:// 路由草案就位。R57+ 推进 T2 memory-uri 实施（bos://memory/** 路由表）候选已列。
