# MECH-04: 三层知识分离架构

> **来源**: `.omo/KNOWLEDGE_ARCH.md`
> **状态**: ✅ 跨 5 项目落地（Eidos/KOS/OntoDerive/Minerva/Agora），~965 tests
> **层映射**: L1 契约层 (Eidos) + L2 能力层 (KOS/OntoDerive)

---

## 一、定义

三层知识分离是 Workspace 中知识管理的**架构模式**：将知识处理分为 Schema 定义层、存取消阶层、推导推理层，层之间零硬依赖。

### 解决的问题

- 知识类型繁多（研究结果/实体/事实/规则/事件），每个项目定义自己的类型
- 类型不一致导致跨项目数据不可互操作
- 知识 Schema 和知识存储/推理耦合在一起，替换任意层都很困难

## 二、三层结构

```
┌──────────────────────────────────┐
│   应用层 (Consume)               │
│   Gateway / Agora / Minerva     │
└──────────────┬───────────────────┘
               │ MCP / CLI
┌──────────────┼───────────────────┐
│   知识服务层 (Knowledge)          │
│  ┌──────────┐  ┌──────────────┐  │
│  │  KOS     │  │  OntoDerive  │  │
│  │  (存取)  │←┤  (推导)      │  │
│  │  索引    │  │  事实推导    │  │
│  │  检索    │  │  本体推理    │  │
│  │  图谱    │  │  规则引擎    │  │
│  └────┬─────┘  └──────┬───────┘  │
└───────┼────────────────┼──────────┘
        │  JSON Schema   │
┌───────┼────────────────┼──────────┐
│  ┌────┴────────────────┴────┐     │
│  │  知识定义层 (Schema)      │     │
│  │  Eidos (知识类型系统)     │     │
│  │  ├ KnowledgeCard Schema  │     │
│  │  ├ OntologyNode Schema   │     │
│  │  ├ Fact Schema          │     │
│  │  ├ DerivationRule        │     │
│  │  ├ validator.py          │     │
│  │  └ registry.json         │     │
│  └──────────────────────────┘     │
└──────────────────────────────────┘
```

## 三、职责边界

| 层 | 项目 | 职责 | 不做 |
|----|------|------|------|
| Schema | Eidos | 定义知识类型、校验、版本 | 不存储数据、不推理 |
| 存取 | KOS | 文档索引、RAG 检索、SQLite | 不 Schema、不推理 |
| 推导 | OntoDerive | 事实推理、规则引擎、MOF | 不存储、不 Schema 定义 |

**零硬依赖原则**: Eidos/KOS/OntoDerive 之间通过 try/except 适配器桥接，不 import 对方包。

## 四、Schema 契约

Eidos 定义的核心 Schema 类型（契约）：

```
KnowledgeCard   — 通用知识卡片
OntologyNode    — 本体节点（实体/概念）
Fact            — 事实断言
DerivationRule  — 推导规则
ResearchFinding — 研究发现
ParadigmSpec    — 范式规格
CognitiveEvent  — 认知事件
Relation        — 关系
InferenceRule   — 推理规则
StateMachine    — 状态机
```

## 五、跨项目 Schema 桥接

OntoDerive 和 Minerva 等地不需要直接导入 Eidos 包，通过 Schema Bridge 适配：

```
Eidos OntologyNode → OntoDerive foundation.Entity → Schema Bridge
Eidos Fact         → OntoDerive FormalFact       → Schema Bridge
Eidos KnowledgeCard ← Minerva ResearchResult     → Schema Bridge
```

每个工具 CL 支持 `--eidos` 标志输出 Eidos-compatible 格式。

## 六、基础路径执行

```bash
1. eidos define KnowledgeCard          # Schema 定义
2. minerva research --eidos-output     # 知识抽取（Eidos 格式）
3. kos ingest ./data/ --schema KCard   # 知识存储（Eidos 校验）
4. ontoderive derive --eidos           # 知识推导
5. eidos viz web                       # 可视化
```

## 七、与 4+1+3 的映射

```
4+1+3 层      三层知识分离
─────────────────────────
L1 契约层     = Eidos (Schema 定义层)
L2 能力层     = KOS (存取) + OntoDerive (推导)
L3 协作层     = Minerva/Agora 引用知识
X3 价值堆栈   = KOS ontology: value_tier/half_life/consensus
```
