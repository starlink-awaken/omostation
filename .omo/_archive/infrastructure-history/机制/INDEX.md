# 机制体系索引

> v1.0.0 | 从 `.omo/` 和 `GOVERNANCE_PLAN.md` 提取的工程治理机制
> 本目录记录项目演进过程中沉淀的**可复用机制**，非架构设计而是**执行方法**

---

## 机制清单

| ID | 名称 | 来源 | 成熟度 | 应用于 |
|----|------|------|--------|--------|
| M1 | [Boulder 工作跟踪](./MECH-01-Boulder工作跟踪.md) | `.omo/boulder.json` | ✅ 稳定运行 | 跨 session 任务跟踪 |
| M2 | [治理计划系统](./MECH-02-治理计划系统.md) | `.omo/GOVERNANCE_PLAN.md` | ✅ 13 Phases 验证 | 产品级执行治理 |
| M3 | [管线编排 Pipeline](./MECH-03-管线编排.md) | `.omo/ARC-ONTOLOGY-TOOLKIT.md` | ✅ 2 预设管线 | Eidos/KOS/OntoDerive 交互 |
| M4 | [三层知识分离](./MECH-04-三层知识分离.md) | `.omo/KNOWLEDGE_ARCH.md` | ✅ 跨 5 项目落地 | 知识 Schema→存取→推导 |
| M5 | [任务分解 Wave](./MECH-05-任务分解Wave模型.md) | `.omo/GOVERNANCE_PLAN.md` + TASK_POOL | ✅ 12+ Phases 验证 | 大任务拆解执行 |

---

## 机制的SSOT定义链

```
机制定义本体（本文件）
  ├→ M1 Boulder:  boulder.json schema + session_id 链
  ├→ M2 治理计划: Phase/Sprint/Wave/Task + P10→P7 角色通信
  ├→ M3 管线编排: Pipeline Protocol + L0-L3 分层
  ├→ M4 知识分离: Schema/Access/Reason 三层 + 零硬依赖
  └→ M5 Wave 模型: Plan → Prompt → Execute → Verify
```

每个机制包含:
- **定义**: 机制是什么、解决什么
- **规范**: 必须遵守的规则
- **文件清单**: 涉及哪些物理文件
- **状态**: 当前成熟度
- **与架构层的关系**: 映射到 4+1+3 的哪层

---

## 快速导航

```
🔧 M1 Boulder     → 跨 session 恢复、work 追踪
📋 M2 治理计划    → 工程治理、Phase 边界
⛓️ M3 管线编排    → Eidos→KOS→OntoDerive 数据流
📚 M4 知识分离    → Schema 契约、知识生命周期
🧩 M5 Wave 模型   → 任务拆解、agent 分配、验证
```
