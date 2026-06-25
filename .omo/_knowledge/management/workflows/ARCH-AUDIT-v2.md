---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: ARCH-AUDIT-v2.md
deprecated-since: 2026-06-23

---

# Workspace 架构审计报告 v2

**时间**: 2026-05-21  
**范围**: 全部 19 个项目的依赖/健康/模型统一度

---

## 一、项目清单

| 项目 | Type | Python LOC | Files | Git状态 | 活跃度 |
|------|------|-----------|-------|---------|-------|
| **eidos** | Python | 1,367 | 16 | 22 uncommitted | 🟢 活跃 |
| **ontoderive** | Python | 10,006 | 59 | 94 uncommitted | 🟢 活跃 |
| **minerva** | Python | 8,880 | 53 | 78 uncommitted | 🟢 活跃 |
| **agora** | Python | 4,892 | 23 | 9 uncommitted | 🟢 活跃 |
| **kos** | Python | 369 | 2 | 58 uncommitted | 🟡 低活性 |
| **sophia** | Python | 1,255 | 9 | 12 uncommitted | 🟡 维持 |
| **eCOS** | Python | 0* | 0* | 61 uncommitted | 🟡 维持 |
| **pallas** | Python | 300 | 2 | 5 uncommitted | 🟡 维持 |
| **bos-skill-cli** | Python | 1,211 | 5 | 7 uncommitted | 🟡 完成MVP |
| **Forge** | Python | 1,762 | 7 | 52 uncommitted | 🔴 不明用途 |
| **SharedBrain** | Python | 0* | 0* | 61 uncommitted | 🔴 210万行零测试 |
| **agent-toolkit** | Node | — | — | 0 | ⚪ npm project |
| **agentmesh** | TS | — | — | 1 | ⚪ TS project |
| **AggreResearch** | TS | — | — | 0 | ⚪ TS project |
| **gateway** | Shell | — | — | 1 | ⚪ MCP wrappers |
| **honeycomb** | TS | — | — | 1502 | 🔴 海量未提交 |
| **wps-skills** | Node | — | — | 1 | ⚪ MCP plugin |

*注: eCOS/SharedBrain 的 Python 代码不在 src/ 或 engine/ 下，在项目根目录

---

## 二、三层架构依赖现状

```
                          Try/Except (optional)
Eidos ────────────┬─────────────────┬─────────────────┐
                   │                 │                 │
                   ▼                 ▼                 ▼
              OntoDerive          Minerva            KOS
              (foundation/        (knowledge/        (ingest.py
               models.py)          store.py +          --schema)
                                   eidos_adapter.py)
```

**关键指标**:
- Eidos → 其他项目: **4 处 import，全部 optional** ✅
- KOS → 其他项目: **0 处 import** — 存储层无人直接依赖
- Agora → OntoDerive: 12+ 处 HARD import ⚠️
- 跨项目硬依赖总数: **12+ (均在 Agora→OntoDerive)**

---

## 三、模型统一度

| 项目 | 模型名 | 字段名 | MetaType归一化 | 状态 |
|------|--------|--------|---------------|------|
| Eidos | OntologyNode | node_type | ✅ 原生 MetaType | 已统一 |
| Eidos | Fact | — | ✅ 已通过relation间接 | 已统一 |
| Eidos | KnowledgeCard | schema_type | ✅ 字符串可映射 | 可增强 |
| OntoDerive | Entity | entity_type | ✅ __post_init__归一化 | 2026-05完成 |
| OntoDerive | Fact | type | ✅ __post_init__归一化 | 2026-05完成 |
| Minerva | Entity | type | ✅ __post_init__归一化 | 2026-05完成 |

**未统一**:
| 项目 | 模型 | 字段 | 问题 |
|------|------|------|------|
| OntoDerive | Inference/Scheme | 无 type 字段 | 还未映射 |
| Minerva | Relation | 无 meta_relation | 无 MetaRelationType |
| KOS | 存储格式 | schema_type | 字符串，无 MetaType 标定 |

---

## 四、代码健康

| 项目 | Ruff | Test | 重要问题 |
|------|------|------|---------|
| **agora** | 0 ✅ | 238 | 状态最好 |
| **eidos** | 0 ✅ | 57 | 建模核心，稳定 |
| **kos** | 5,263 | ~58 | ❌ KOS 代码质量差——5000+ lint violations 是因为自动生成的参考代码 |
| **ontoderive** | 1,307 | 204 | ⚠️ 大量 lint 问题但测试覆盖好 |
| **minerva** | 955 | 258 | ⚠️ 需要清理 .venv 数据 |
| **sophia** | 121 | 87 | 中等 |
| **eCOS** | 65 | 98 | 中等 |

---

## 五、建议优先级

### P0 必须做
1. **Agora→OntoDerive 解耦** — 12+ hard import 改 optional adapter
2. **KOS 质量** — 5k+ ruff violations 需要治理（虽然部分是自动生成的）

### P1 建议做
3. **OntoDerive Inference/Scheme** 接 MetaType — 扩展已建立的模式
4. **Minerva Relation** 接 MetaRelationType
5. **KOS 存储格式** 标定 MetaType

### P2 按需做
6. Forge 用途确认（52 uncommitted, 0 tests）
7. honeycomb 清理（1502 uncommitted）
8. SharedBrain 测试引进
