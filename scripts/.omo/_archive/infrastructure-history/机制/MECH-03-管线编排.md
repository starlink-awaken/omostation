# MECH-03: 管线编排 Pipeline System

> **来源**: `.omo/ARC-ONTOLOGY-TOOLKIT.md`
> **状态**: ✅ 2 个预设管线，Pipeline Protocol v1.0 定义完成
> **层映射**: L1+L2 — Pipeline 协议介于契约层和能力层之间

---

## 一、定义

管线编排是一个 **4 层（L0→L3）工具组合协议**，通过统一 JSON 契约将独立的 CLI 工具串联为可编排的知识流水线。

### 解决的问题

- 独立工具（Eidos/KOS/OntoDerive/Minerva/Agora）如何组合使用
- 每次全链路操作需要手动执行 4-5 条命令、手动传参
- 如何定义、执行和复用知识处理流程

## 二、四层架构

```
L3: 场景组合 (Scene Layer)
  ┌─────────┐ ┌─────────┐ ┌──────────┐
  │知识库构建│ │推理链路  │ │一致性检查 │
  │E→I→S→D→V│ │S→D→R→V │ │M→C→V   │
  └────┬────┘ └────┬────┘ └────┬─────┘
       │           │           │
L2: Pipeline 层 ──┘───────────┘─── 管线编排器
   Pipeline Protocol (JSON schema_type + JSON data)
       │           │           │
L1: 工具层 (独立可执行)
  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐ ┌──────┐
  │ Eidos│ │Minerva│ │ KOS  │ │ KOS  │ │OntDeriv│ │Viz   │
  │ CLI  │ │Pipeline│ │ingest│ │search│ │derive │ │工具  │
  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └───┬────┘ └──┬───┘
     └────────┴────────┴────────┴─────────┴──────────┘
                     JSON 接口交换
                        │
L0: 元模型层 (Eidos META)
   SSOT 8 MET-Type × 4 MET-Relation
   MetaType(DOMAIN|FACT|INFERENCE|RELATION|STATE|DOCUMENT|CONSTRAINT|PROCESSOR)
   MetaRelation(STRUCT|DERIVE|BEHAVIOR|JUSTIFY)
```

## 三、Pipeline Protocol

所有工具之间的数据交换使用统一 JSON 格式：

```json
{
  "pipeline": {
    "version": "1.0",
    "tool": "minerva",
    "action": "extract",
    "timestamp": "2026-05-21T10:00:00Z"
  },
  "meta_type": "document",
  "eidos_type": "KnowledgeCard",
  "data": { /* 工具具体输出 */ },
  "provenance": {
    "source": "file:///path/to/src",
    "confidence": 0.95
  }
}
```

### CLI 管线模式

每个工具支持 `--pipeline` 系列标志：

```
--pipeline             输出纯 JSON（无人类可读信息）
--pipeline-input FILE  从文件读取前一个工具的输出
--pipeline-output FILE 写入文件供后一个工具消费
```

## 四、L0 元模型层

8 MetaType × 4 MetaRelation 是**单一事实源**：

| MetaType | Eidos 类型 | 消费工具 |
|----------|-----------|---------|
| DOMAIN | OntologyNode | 建模/可视化 |
| FACT | Fact | 推导工具 |
| INFERENCE | InferenceRule | 推导工具 |
| RELATION | Relation | 可视化/搜索 |
| STATE | StateMachine | 推导/建模 |
| DOCUMENT | KnowledgeCard | 抽取/存储/搜索 |
| CONSTRAINT | Schema | 建模/校验 |
| PROCESSOR | ProcessorDef | 管线编排 |

## 五、各工具管线能力

| 工具 | 角色 | 管线命令 |
|------|------|---------|
| **Eidos CLI** | 编排器 | `eidos pipeline --name X --steps ...` |
| **Minerva** | 抽取 | `minerva research --pipeline-output X` |
| **KOS** | 存取 | `kos ingest --pipeline-input X --schema Y` |
| **OntoDerive** | 推导 | `ontoderive derive --eidos --pipeline-output X` |
| **Viz** | 可视化 | `eidos viz graph --pipeline-input X` |

## 六、典型管线

### 知识库构建

```
eidos define KnowledgeCard
→ minerva extract (抽取)
→ kos ingest (存储)
→ eidos validate --pipeline (校验)
→ eidos-viz graph (可视化)
```

### 推理链路

```
kos search "量子" --meta-type DOMAIN
→ ontoderive derive --pipeline
→ eidos-viz graph
```

### 一键执行

```bash
eidos pipeline --name knowledge-base
# 或
eidos pipeline --file my-pipeline.yaml
```

## 七、核心原则

1. **增量式** — 不重构现有项目，只新增模块和适配器
2. **元模型是文档变代码** — SSOT 的 Markdown 设计变成可执行的 Python
3. **Pipeline 是可选层** — 每个工具独立可用，pipeline 只是串联方式
4. **JSON 是通用接口** — 工具间通过 JSON 交换，不共享内存/对象
5. **可视化是文本优先** — Mermaid 在终端即可查看
