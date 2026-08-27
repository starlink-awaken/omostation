---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# 本体建模统一架构建议

## 核心思路：Eidos 作为 Schema 契约层，不下沉到项目内部

不合并模型，不迁移代码。Eidos 作为**契约定义**，各项目用自己的内部表示，通过 **Schema Bridge** 在跨项目边界处转换。

```
┌────────────────────────────────────────────────────────────────┐
│                        Eidos Schema Contract                    │
│  定义: KnowledgeCard, Fact, OntologyNode, Schema, Relation      │
│  存储: eidos/types/, eidos/schema.py, eidos/registry.py        │
│  校验: eidos/validator.py, eidos/cli.py                        │
└──────────┬────────────────────────┬────────────────────────────┘
           │  Schema Bridge         │  Schema Bridge
           ▼                        ▼
┌──────────────────┐    ┌─────────────────────┐    ┌──────────────────┐
│  OntoDerive       │    │      KOS            │    │  Minerva          │
│  foundation.Entity│    │  知识存储/检索      │    │  knowledge.Entity │
│  → eidos_adapter  │    │  → ingest 标记类型  │    │  → eidos_adapter  │
│  derive --eidos   │    │  → search 返回契约  │    │  research --output│
└──────────────────┘    └─────────────────────┘    └──────────────────┘
```

### 三个具体行动

#### 行动 1：KOS 接入 Eidos 契约链
当前 KOS ingest 的文件分类是自包含的（不经过 Eidos）。
改进：KOS ingest 的 `.json` 文件先用 Eidos 校验 schema_type，无效的标为 `raw`。
收益：KOS 存储的每条记录都有可验证的 schema_type。

#### 行动 2：统一 Entity 字段映射
建立标准映射表（记录在 KNOWLEDGE_ARCH.md）：

```
Eidos OntologyNode          OntoDerive Entity        Minerva Entity
─────────────────          ──────────────────       ────────────────
id                          id                       id
name                        name                     name
node_type ───────────────►  type ◄────────────────── type
description ─────────────► desc ◄────────────────── description
properties ──────────────► properties                (缺失)
aliases  ◄──────────────── (从 tags 转)               aliases
parent                      (缺失)                    (缺失)
```

#### 行动 3：OntoDerive MOF 元模型暴露到 Eidos
OntoDerive 的 10-type MOF 系统是当前最有价值的本体能力。
方案：新增 `eidos/types/derived.py`，从 OntoDerive 的 MOF type 系统派生具体 schema 类型：
```python
ONTOLOGY_TYPE_MAP = {
    "entity": OntologyNode,
    "relation": Fact,  
    "concept": OntologyNode,
    "rule": None,  # OntoDerive Scheme
    "event": None,
    "process": None,
    "state": None,
    "property": None,
    "type": None,
}
```

### 优先级
P0: KOS ingest 过 Eidos 校验（改 ingest.py ~20行）
P1: 实体映射表标准化（文档 + 适配器对齐）
P2: MOF 元模型暴露（新增 eidos/types/derived.py）
P3: 闭环管线 Eidos → KOS → OntoDerive (新增 eidos-derive CLI 链接)

### 非做不可 / 不做
做: 标准映射表 + KOS 校验 + 管线连接
不做: 合并项目、迁移模型、重构内核
