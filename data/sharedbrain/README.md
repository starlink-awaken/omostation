# SharedBrain — 数据持久层

> 状态: **轻量化保留**（Phase 17 决策，详见 `.omo/_knowledge/design/debt-cleanup-plan.md`）

---

## 架构说明

SharedBrain **不再包含业务代码**。所有能力已迁移至 [kairon](../projects/kairon/)：

| 原 SharedBrain 能力 | 迁移位置 | 状态 |
|---------------------|---------|------|
| 核心数据模型 (Entity/Relation/Provenance/KnowledgeGraph) | `kairon/packages/core-models/` | ✅ 已完成 |
| EU 计价桥接 | `kairon/packages/sharedbrain-bridge/` | ✅ 已完成 |
| Immune 审计桥接 | `kairon/packages/sharedbrain-bridge/` | ✅ 已完成 |
| Sync 同步桥接 | `kairon/packages/sharedbrain-bridge/` | ✅ 已完成 |
| 共享工具库 | `kairon/packages/shared-lib/` | ✅ 已完成 |

## 当前职责

SharedBrain 目前作为 **数据持久层**，仅保留：

```
SharedBrain/
└── data/db/
    ├── core/         ← event_store.db, registry.db（核心事件和注册表）
    └── organs/
        ├── economy/  ← tasks.db（经济任务数据）
        └── execution/ ← （预留执行数据）
```

## 相关文档

- 债务清理方案: `.omo/_knowledge/design/debt-cleanup-plan.md`
- SharedBrain 去留决策任务: `.omo/tasks/active/SHAREDBRAIN-FORMAL-DECISION.yaml`
- core-models 包: `projects/kairon/packages/core-models/`
- sharedbrain-bridge 包: `projects/kairon/packages/sharedbrain-bridge/`

---

*更新: 2026-06-01 · Phase 17 架构收敛*
