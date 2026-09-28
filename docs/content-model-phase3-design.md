---
schema: md/v1
status: active
lifecycle: planning
owner: governance-team
type: plan
last-reviewed: 2026-09-28
---

# Phase 3 统一内容 Schema 注册中心设计

## 目标

合并 4 处分散 Schema 到统一注册中心，带版本管理和引用完整性。

## 现状

Schema 分散在 4 处：
1. `projects/knowledge/kairon/packages/eidos/schemas/` — 25 个 JSON Schema
2. `docs/contracts/` — 3 个 JSON Schema
3. `projects/omo/src/omo/omo_io_schemas.py` — 7 个 Pydantic 模型
4. `projects/ecos/src/ecos/ssot/compiler/fact_inspector.py` — 硬编码字段列表

## 设计

### 1. Schema 注册中心

```
.omo/standards/content-schemas/
├── index.yaml                   # Schema 索引
├── kairon/                      # kairon eidos schemas（25 个）
├── contracts/                   # docs/contracts schemas（3 个）
├── omo/                         # omo_io_schemas Pydantic 模型（7 个）
└── core/                        # 核心 schema（新增）
```

### 2. 引用完整性检查

`bin/ssot/schema-ref-check.py`：
- Schema 之间 $ref 必须可解析
- 内容实体 $schema 指向必须存在
- 无悬空 $ref

### 3. MOF M2 对齐

内容 Schema 与 MOF M2 类型建立映射：
- Document → M2.Component
- Task → M2.Component
- Debt → M2.Component
- Decision → M2.Entity

## 实施步骤

1. 设计 Schema 注册中心结构（1 天）
2. 实现引用完整性检查（1-2 天）
3. 迁移 kairon eidos schemas（1-2 天）
4. 迁移 docs/contracts schemas（0.5 天）
5. 迁移 omo_io_schemas Pydantic 模型（1 天）
6. 建立 MOF M2 映射（1 天）

## 风险

- Schema 合并冲突：按内容域分批合并
- 引用完整性：需要完整的 $ref 图
- MOF M2 对齐：需要理解 M2 类型体系

## 成功标准

- 统一 Schema 注册中心覆盖全仓 Schema
- 无悬空 $ref
- 内容实例可映射到 M1
