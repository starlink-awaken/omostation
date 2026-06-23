---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# 建模全链路修复 — 执行计划

## 目标
让 Eidos 的元模型（8 MetaType × 4 MetaRelationType）成为所有建模工具的真实约束，
实现 `定义 → 注入 → 校验 → 推导 → 可视化` 的全链路闭环。

## 差距分析

### 现状 vs 目标

| 环节 | 当前 | 目标 |
|------|------|------|
| 定义 Schema | `eidos define` 无交互式建模 | 交互式建模 + 元模型约束 |
| 注入数据 | KOS ingest 不校验 schema_type | ingest 优先校验 Eidos Schema |
| 校验 | `eidos validate` 独立运行 | 注入时自动校验 |
| 推导 | OntoDerive 用自有 MOF 系统 | MOF type 关联 MetaType |
| 可视化 | eidos-viz 展示类型结构 | 展示真实知识图 |

## 执行步骤

### Step 1: KOS ingest 接入 Eidos 校验
- `kos ingest` 的 JSON 文件先用 `eidos.validate()` 校验
- 未通过的文件标记为 `raw` 而非直接拒绝
- 加上 `--schema <name>` 指定 Schema

### Step 2: OntoDerive MOF 关联 MetaType
- OntoDerive 的 entity.type 接受 Eidos MetaType 值
- `derive --eidos` 输出带 `meta_type` 标签

### Step 3: 端到端验证
- 定义一个 Document Schema
- 注入一批测试文件
- 校验 → 推导 → 可视化

### Step 4: 更新 KNOWLEDGE_ARCH.md
