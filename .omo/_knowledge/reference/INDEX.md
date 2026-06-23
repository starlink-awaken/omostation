---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# 参考文档 — `_knowledge/reference/`

> 术语表、经验教训、基准测试、架构图。回答"参考信息在哪？"

---

## 架构图

| 文件 | 用途 |
|------|------|
| [diagrams/INDEX.md](../../diagrams/INDEX.md) | 架构图索引 |
| [diagrams/4-plus-1-3-architecture.md](../../diagrams/4-plus-1-3-architecture.md) | 4+1+3 架构图 (Mermaid) |
| [diagrams/control-plane-state-flow.md](../../diagrams/control-plane-state-flow.md) | 控制面状态流转图 (Mermaid) |
| [diagrams/architecture.html](../../diagrams/architecture.html) | 架构 HTML 图 |

## 经验与基准

| 文件 | 用途 | 位置 |
|------|------|------|
| [LESSONS.md](LESSONS.md) | 经验教训总结 | 顶层 |
| [MODEL-BENCHMARK.md](MODEL-BENCHMARK.md) | 模型基准测试 | 顶层 |
| [PRODUCT-ARCH-JOURNEY.md](PRODUCT-ARCH-JOURNEY.md) | 产品架构演进史 | 顶层 |

## 本体论与方法论

| 文件 | 用途 | 位置 |
|------|------|------|
| [ARC-ONTOLOGY-RECOMMEND.md](ARC-ONTOLOGY-RECOMMEND.md) | 本体论推荐 | 顶层 |
| [ARC-ONTOLOGY-TOOLKIT.md](ARC-ONTOLOGY-TOOLKIT.md) | 本体论工具包 | 顶层 |
| [OMO-METHODOLOGY-CANON.md](../../_knowledge/reference/OMO-METHODOLOGY-CANON.md) | 外部 OMO 方法系统 canonical home 与 Workspace `.omo` 的边界说明 | `_knowledge/reference/` |

## Agent 提示词库

| 文件 | 用途 |
|------|------|
| [task-prompts/](../../task-prompts/) | 历史 Agent 任务提示词（wave-* 系列） |
| [task-prompts/handoffs/pipeline-contract.md](../../task-prompts/handoffs/pipeline-contract.md) | Pipeline 契约文档 |

## SSOT 7 域 Schema

| 文件 | 用途 |
|------|------|
| [standards/ssot-7-domain-schema.md](../../standards/ssot-7-domain-schema.md) | SSOT 7 域 Schema 标准 |

---

## 参考文档规范

- 参考文档保持只读，不随执行进展修改（除非参考内容本身过时需更新）
- 经验教训应标注来源和验证状态（confirmed/tentative/refuted）
- 基准测试应标注测试环境、日期、配置
- 引用事实面数据时使用指针（相对路径）

## 跨平面引用

| 引用目标 | 位置 | 用途 |
|---------|------|------|
| [控制面:状态](../../_control/INDEX.md) | `_control/` | 参考信息对应的系统上下文 |
| [事实面:标准 SSOT](../../_truth/INDEX.md) | `_truth/` | 参考涉及的标准定义 |
| [知识面:设计文档](../design/INDEX.md) | `_knowledge/design/` | 参考信息关联的设计方案 |

---

*维护: 2026-05-31 · 参考文档需标注 freshness 日期，超过 90 天标记 stale*
