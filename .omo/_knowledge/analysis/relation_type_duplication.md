---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# eidos/core-models Relation 类型分析

> 审计发现: eidos 内有 4 个 Relation 类，core-models 另有 1 个，各自独立无继承

## 现状

| 位置 | 类名 | 字段 | 特性 |
|------|------|------|------|
| `eidos/types/relation.py` | `Relation` | id, source_id, target_id, relation_type, meta_relation, cardinality, weight, provenance, properties | 完整: validate(), to_dict(), from_dict(), MetaRelationType |
| `eidos/graph_store.py` | `Relation` | (简化版) | 图存储内部使用 |
| `eidos/knowledge_graph_engine.py` | `Relation` | (简化版) | 知识图引擎内部使用 |
| `eidos/types/knowledge_card.py` | `Relation` | (简化版) | Knowledge Card 专用 |
| `core-models/models.py` | `Relation` | source_id, target_id, type, confidence, weight, provenance, metadata | to_dict(), to_json_ld(), RELATION_TYPES |

## 分析

### 1. eidos/types/relation.py — 规范版本
最完整的 Relation，包含验证/序列化/反序列化/meta-classification。应作为唯一规范。

### 2. eidos 内部重复
- `graph_store.py` / `knowledge_graph_engine.py`: 简单的关系记录，可以替换为 `from eidos.types.relation import Relation`
- `knowledge_card.py`: 卡片专用包装，可以在规范 Relation 上加一层 CardRelation

### 3. core-models vs eidos
- **core-models**: 知识图谱关系，侧重 provenance + JSON-LD
- **eidos**: Schema 约束关系，侧重 meta-classification + 验证
- **差异**: 字段名不同 (type vs relation_type)，目的不同

## 建议方案

### Phase 1: eidos 内部统一 (0.5h)
```
保留: eidos/types/relation.py  (规范版本)
废弃: eidos/graph_store.py:Relation → import from types.relation
废弃: eidos/knowledge_graph_engine.py:Relation → import from types.relation  
废弃: eidos/types/knowledge_card.py:Relation → 改为 CardRelation
```

### Phase 2: core-models 桥接 (1h)
```
core-models Relation 添加 from_eidos / to_eidos 方法
或: 在 eidos 侧提供 core-models → eidos 适配器
```

### Phase 3: 统一基类 (长期)
```
core-models 定义 BaseRelation (最小接口)
eidos Relation 继承 BaseRelation
```
