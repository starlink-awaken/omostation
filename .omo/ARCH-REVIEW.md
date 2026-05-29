# 知识架构综合分析与方案设计

> 分析日期: 2026-05-20
> 分析输入: KOS SPEC-v0.1 (6阶段路线) + `/knowledge/` 知识库 + 工作区项目 + 现有类型系统

---

## 一、现状全景

### 当前碎片问题

| 组件 | 什么问题 |
|------|----------|
| **kos** | 15 个单文件脚本，无包结构；知识索引功能有，但和其后三阶段无连接 |
| **ontoderive** | 5 层推理引擎，有 ontology_map 但和 kos 不互通 |
| **starlink-types** | 空壳项目，本应是共享类型包但废弃了 |
| **knowledge/** | 46,000+ 文件，大部分在 `ingested/`，缺乏结构化访问 |
| **SPEC-v0.1** | 6 阶段蓝图，从简单索引到分布式 PKM，但三个项目各自为政 |

### SPEC-v0.1 核心要点

```
L0 (已做): 文档索引 + 基础 RAG
L1: 卡片知识系统 + 双链 + 主动推荐
L2: 结构化知识图谱 (本体)
L3: 多层知识组织 + 形式化推理
L4: 语义索引 + 概念导航
L5: 分布式 PKM 网络
```

每个阶段设计都有完整的领域模型、API 路径、MCP 工具定义。

---

## 二、架构问题诊断

### 问题 1: 知识资产散落四地

```
knowledge/        → 46k raw ingested files (非结构化)
kos/knowledge/    → KOS 自己的知识数据 
ontoderive/       → 推理引擎，有自己的 ontology
minerva/          → 研究系统，有自己的知识图谱 (LanceDB)
```

**后果**: 同一个内容在 kos 被索引、在 minerva 被研究、在 ontoderive 被推理，但三者之间没有统一的知识访问层。

### 问题 2: kOS 的 SPEC 和实现脱节

SPEC 设计了 6 个阶段的完整 API 和领域模型，但实现还停留在 L0: `kos-cli.py` 等 15 个单文件脚本，没有按阶段组织。SPEC 里的 `L1KnowledgeCard`, `L2OntologyConcept`, `L3FormalTheorem` 等核心领域类型没有任何 Python 实现。

### 问题 3: starlink-types 位置尴尬

starlink-types 被设为共享类型包，但 0 代码引用它——说明当前架构缺一个真正的"类型总线"。

### 问题 4: knowledge/ 和 kos 的关系

`knowledge/ingested/` 有 `46,075` 个文件（大量是已经被 ingester 处理的原始数据），但 kos 没有指向它们。SPEC 的 L0-L5 逐步深化，但缺少一步"连接 knowledge/ 到 kos"的实际操作。

---

## 三、目标架构设计

### 核心理念: 三层知识架构

```
┌─────────────────────────────────────────────────┐
│             应用层 (Consume)                     │
│  Agora (路由)  gateway (入口)  minerva (研究)    │
│  eCOS (认知)  Sophia (范式)                    │
├─────────────────────────────────────────────────┤
│          逻辑层 (Knowledge Service)              │
│  kos v2                      ontoderive          │
│  ┌─────────────────┐       ┌──────────────┐     │
│  │ KnowledgeService │◄────►│ Reasoning     │     │
│  │ - ingest        │       │ Engine        │     │
│  │ - search        │       │ - infer       │     │
│  │ - graph         │       │ - derive      │     │
│  │ - recommend     │       └──────────────┘     │
│  └──────┬──────────┘                            │
├─────────┼───────────────────────────────────────┤
│         底层 (Knowledge Store)                   │
│  ┌──────┴──────────────────────────────┐        │
│  │  统一知识存储                         │        │
│  │  - knowledge/ (raw ingested)         │        │
│  │  - kos/knowledge/ (卡片/图谱/语义)    │        │
│  │  - 统一索引层 (lancedb/sqlite)        │        │
│  └─────────────────────────────────────┘        │
└─────────────────────────────────────────────────┘
```

### 关键架构决策

#### 决策 1: starlink-types 复活为 `gateway-schema`

不是作为传统的"类型定义包"，而是作为 **JSON Schema 契约定义**（当前 `CONTRACTS.md` 的代码形式）。每个项目提供自己的 Schema，gateway-schema 做注册和校验。

```
gateway-schema/
├── contracts/
│   ├── kos-card.json           # L1 知识卡片 Schema
│   ├── kos-ontology.json       # L2 本体概念 Schema
│   ├── ontoderive-fact.json    # 推理事实 Schema
│   ├── minerva-research.json   # 研究成果 Schema
│   └── ...                     # 项目自注册
├── validator.py                # 运行时校验器
└── registry.json               # 所有 Schema 索引
```

#### 决策 2: kos 重构为阶段式包结构

按 SPEC 的阶段组织，而不全是零散的 15 个脚本：

```
kos/
├── stages/
│   ├── l0/              # 文档索引 + 基础 RAG (当前)
│   │   ├── indexer.py
│   │   └── ...
│   ├── l1/              # 卡片知识系统
│   │   ├── card.py      # L1KnowledgeCard
│   │   └── ...
│   └── ...
├── knowledge/           # 知识数据目录 (指向 knowledge/ 的索引)
├── kos-mcp-server.py    # MCP 入口
└── ...
```

但**不**把 6 个阶段全实现——而是**先做 L0 精化 + L1 基础**，让 kos 从工具升级为知识服务。

#### 决策 3: knowledge/ 接入 kos

`knowledge/ingested/` 下的 46k 文件应该被 kos 索引而不是被无视。加一个 `kos ingest` 命令，扫描 knowledge/ 并建立索引：

```bash
kos ingest knowledge/          # 扫描并索引所有文件
kos ingest --watch             # 持续监控新文件
```

#### 决策 4: Agora 成为知识路由层

Agora 不应该只做 MCP 服务注册——它应该知道"哪个服务能回答什么类型的问题":

```
Agora Registry:
  kos:          "文档检索、知识卡片、图谱查询"
  ontoderive:   "事实推导、本体推理"
  minerva:      "深度研究、多源综合"
  minerva/kb:   "知识图谱问答"
```

---

## 四、实施路线

### Phase 1 (1-2 天) — 连接

1. `kos ingest` 命令 — 扫描 `knowledge/` 建立索引
2. `gateway-schema` 项目复活 — 先注册 kos 和 ontoderive 的 Schema
3. gateway 增加 `sharedbrain-mcp` wrapper

### Phase 2 (3-5 天) — 结构化

4. kos 按 SPEC stages 重组 (L0 精化 + L1 卡片系统)
5. Agora 知识路由注册 — kos 的 MCP 工具注册语义元信息
6. ontoderive 的推理结果回写到统一知识存储

### Phase 3 (远期) — 推理

7. KOS SPEC L2-L5 逐步实现
8. ontoderive + kos 深度集成 (推理直接基于统一知识层)
9. 分布式 PKM 网络

---

## 五、核心问题

你觉得这个方向对吗？几个关键选择点：

1. **starlink-types 复活为 `gateway-schema`** — 还是直接合并到 gateway 里？
2. **kos 按阶段重构** — 还是先把 gateway-schema 做起来，kos 维持现有结构不动？
3. **knowledge/ 接入 kos** — 优先级高吗？还是先做别的？

说说你的想法再细化方案。
