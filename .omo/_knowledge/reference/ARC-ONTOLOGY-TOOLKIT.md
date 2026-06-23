---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史能力/过程/治理/参考/愿景文档批量归档, 当前活跃文档以各面 INDEX/SSOT 为准"
---
# 本体建模全生命周期工具集 — 细化设计方案

## 一、架构总图

```
┌──────────────────────────────────────────────────────────────────────┐
│                         L3: 场景组合                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ 知识库构建    │  │ 推理链路     │  │ 一致性检查   │  ...           │
│  │ E→I→S→K→D→V │  │ S→K→D→R→V  │  │ M→C→V       │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
├──────────────────────────────────────────────────────────────────────┤
│  L2: Pipeline 层 (管线编排)                                          │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐             │
│  │建模  │ │抽取  │ │存储  │ │搜索  │ │推导  │ │可视化│             │
│  │Model │ │Extract│ │Store │ │Search│ │Reason│ │Viz   │             │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘             │
│     └────────┴────────┴────────┴────────┴────────┘                   │
│              Pipeline Protocol (schema_type + JSON)                  │
├──────────────────────────────────────────────────────────────────────┤
│  L1: 工具层 (单体工具, 独立可执行)                                    │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │
│  │ eidos  │ │minerva │ │  kos   │ │  kos   │ │ontoder.│ │ new    │  │
│  │ CLI    │ │pipeline│ │ ingest │ │ search │ │ derive │ │ viz    │  │
│  │建模工具│ │抽取工具│ │存/取   │ │搜索工具│ │推理工具│ │可视化  │  │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │
├──────────────────────────────────────────────────────────────────────┤
│  L0: 元模型层 (Eidos META)                                           │
│  ┌─────────────────────────────────────────────────────────────┐     │
│  │ MetaModel  (SSOT 8 MET-Type × 4 MET-Relation × 4 约束)     │     │
│  │ MetaType(DOMAIN|FACT|INFERENCE|RELATION|STATE|DOCUMENT|... )│     │
│  │ MetaRelation(STRUCT|DERIVE|BEHAVIOR|JUSTIFY)                │     │
│  │ ConcreteType(KCard|Fact|Node|Relation|StateMachine|... )    │     │
│  └─────────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 二、L0 元模型层: 设计（增量实现）

### 2.1 元模型体系

SSOT 的 8 MET-Type × 4 MET-Relation 体系直接映射为 Eidos 中的 `MetaModel` 类体系。

```python
# eidos/src/eidos/meta/__init__.py
# 新增模块：元模型定义

from enum import Enum

class MetaType(Enum):
    """SSOT 8-type meta-entity system"""
    DOMAIN = "domain"       # 领域实体 (→ OntologyNode)
    FACT = "fact"           # 事实断言 (→ Fact)
    INFERENCE = "inference" # 推导规则 (→ InferenceRule)
    RELATION = "relation"   # 关系类型 (→ Relation)
    STATE = "state"         # 状态机 (→ StateMachine)
    DOCUMENT = "document"   # 文档知识 (→ KnowledgeCard)
    CONSTRAINT = "constraint" # 约束/规约 (→ Schema)
    PROCESSOR = "processor" # 处理器 (→ Pipeline节点)

class MetaRelationType(Enum):
    """SSOT 4-type meta-relation"""
    STRUCT = "struct"     # 结构组成 (type hierarchy, extends)
    DERIVE = "derive"     # 推导派生 (inference chain)
    BEHAVIOR = "behavior" # 行为状态 (state transition)
    JUSTIFY = "justify"   # 归因溯源 (provenance)
```

### 2.2 映射表

| SSOT MetaType | Eidos 类型 | 工具消费方 | 
|--------------|-----------|-----------|
| DOMAIN | `OntologyNode` | 建模/可视化 |
| FACT | `Fact` | 推导工具 |
| INFERENCE | (new) `InferenceRule` | 推导工具 |
| RELATION | (new) `Relation` | 可视化/搜索 |
| STATE | (new) `StateMachine` | 推导/建模 |
| DOCUMENT | `KnowledgeCard` | 抽取/存储/搜索 |
| CONSTRAINT | `Schema` | 建模/校验 |
| PROCESSOR | (new) `ProcessorDef` | 管线编排 |

### 2.3 新增类型

```python
# eidos/src/eidos/types/inference_rule.py
@dataclass
class InferenceRule:
    """推理规则 — 对应 MET-INFERENCE"""
    id: str
    name: str
    rule_type: str              # forward | backward | abductive
    premises: list[str]         # 前提
    conclusion: str             # 结论
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

# eidos/src/eidos/types/state_machine.py
@dataclass
class StateMachine:
    """状态机 — 对应 MET-STATE"""
    id: str
    name: str
    states: list[str]
    transitions: list[StateTransition]
    initial_state: str

@dataclass
class StateTransition:
    from_state: str
    to_state: str
    trigger: str
    guard: str = ""

# eidos/src/eidos/types/relation.py
@dataclass
class Relation:
    """关系 — 对应 MET-RELATION"""
    id: str
    source_id: str
    target_id: str
    relation_type: str
    meta_relation: MetaRelationType  # STRUCT | DERIVE | BEHAVIOR | JUSTIFY
    weight: float = 1.0
    properties: dict = field(default_factory=dict)
```

---

## 三、L1 工具层详细设计

### 3.1 建模工具 (Eidos CLI — 已存在，需扩展)

**当前能力**:
- `eidos list` → 列出注册的 Schema
- `eidos validate --type X <file>` → 校验 JSON

**需扩展**:

```bash
eidos meta                             # 显示元模型定义 (8 MET-Type)
eidos meta --export                    # 导出元模型为 JSON Schema
eidos define <name> --type <metatype>  # 交互式定义新类型
eidos derive --from-kos --to-ontoderive # 管线：KOS → OntoDerive
eidos graph <type>                     # 可视化类型的关系图 (→ viz 工具)
```

**管线 CLI 约定**:
每个工具的 CLI 支持 `--pipeline` 模式：
- `--pipeline`: 输出精简 JSON（不打印人类可读信息）
- `--pipeline-input <file>`: 从文件读取前一个工具的输出
- `--pipeline-output <file>`: 写入文件供后一个工具消费

### 3.2 抽取工具 (Minerva pipeline + KOS ingest)

**当前**: Minerva 管道产生 ResearchResult，ingest 扫描文件。
**改进**: 统一抽取管线的输出格式为 Eidos 类型。

```python
# 抽取管线协议
class ExtractionResult:
    """统一的抽取工具输出"""
    source: str                       # 源标识
    entities: list[OntologyNode]      # 抽取的实体
    facts: list[Fact]                 # 抽取的事实
    cards: list[KnowledgeCard]        # 生成的卡片
    relations: list[Relation]         # 抽取的关系
    confidence: float                 # 抽取质量
```

### 3.3 存储搜索工具 (KOS — 已存在)

**当前**: KOS 有 ingest/search/query/list，但与元模型无关联。
**改进**: KOS 搜索支持按 MetaType 过滤。

```bash
kos search "量子" --meta-type DOMAIN    # 只搜领域实体
kos search "专利" --meta-type DOCUMENT   # 只搜文档
kos list --meta-type FACT                # 列出所有事实
kos stats                                # 按 MetaType 统计存量
```

### 3.4 推导工具 (OntoDerive — 已存在)

**当前**: OntoDerive 有 MOF 10-type 系统 + FormalPipeline。
**改进**: 推导输入/输出对接 Eidos 类型。

```bash
ontoderive derive --eidos          # 输出 Eidos Fact (已有)
ontoderive derive --pipeline       # 管线模式 (纯净 JSON 输出)
ontoderive derive --rules <file>   # 指定推理规则集 (InferenceRule JSON)
```

### 3.5 可视化工具 (新增)

**缺失组件**。可视化本体网络/关系/状态机的工具。

```bash
eidos-viz schema <name>            # 展示 Schema 字段关系图
eidos-viz graph <type>             # 展示类型实例网络
eidos-viz state <machine>          # 展示状态机状态图
eidos-viz pipeline <pipeline>      # 展示管线流向图
```

实现方案：
- 使用 Mermaid 输出（文本图表，零依赖）
- `eidos-viz` 作为 Eidos 的子命令或独立脚本
- 输出到 stdout 或文件，可被 Markdown renderer 渲染

```python
# eidos-viz 核心逻辑
def render_schema_graph(schema: Schema) -> str:
    """输出 Mermaid classDiagram"""
    lines = ["classDiagram"]
    lines.append(f"  class {schema.name} {{")
    for f in schema.fields:
        lines.append(f"    +{f.field_type.value} {f.name}")
    lines.append("  }")
    return "\n".join(lines)

def render_ontology_graph(nodes: list[OntologyNode], rels: list[Relation]) -> str:
    """输出 Mermaid graph"""
    lines = ["graph TD"]
    for n in nodes:
        lines.append(f"  {n.id}[\"{n.name}\"]")
    for r in rels:
        lines.append(f"  {r.source_id} -->|{r.relation_type}| {r.target_id}")
    return "\n".join(lines)
```

---

## 四、L2 Pipeline 层: 管线连接协议

### 4.1 Pipeline Protocol

所有工具之间的数据交换使用统一协议：

```json
{
  "pipeline": {
    "version": "1.0",
    "tool": "minerva",
    "action": "extract",
    "timestamp": "2026-05-21T10:00:00Z"
  },
  "meta_type": "document",      // SSOT MetaType
  "eidos_type": "KnowledgeCard", // Eidos ConcreteType  
  "data": { /* 工具具体输出 */ },
  "provenance": {
    "source": "file:///path/to/src",
    "confidence": 0.95
  }
}
```

### 4.2 一键管线 CLI

```bash
eidos pipeline --name "知识库构建"    \
  --steps "model:define my_schema"    \
  --steps "extract:minerva research"  \
  --steps "store:kos ingest"          \
  --steps "reason:ontoderive derive"  \
  --steps "viz:eidos-viz graph"
```

等价于链式调用：
```bash
eidos define my_schema --pipeline-output /tmp/s.json
minerva research --pipeline-input /tmp/s.json --pipeline-output /tmp/cards.json
kos ingest --pipeline-input /tmp/cards.json
ontoderive derive --eidos --pipeline-output /tmp/facts.json
eidos-viz graph --pipeline-input /tmp/facts.json
```

### 4.3 Pipeline 编排器

```bash
eidos pipeline --file pipeline.yaml
```

```yaml
# pipeline.yaml
name: "专利知识库全量建库"
steps:
  - tool: "eidos"
    action: "define"
    args: { schema: "patent_schema", type: "DOCUMENT" }
  - tool: "minerva"
    action: "research"
    args: { query: "量子计算专利", output: "/tmp/cards.json" }
  - tool: "kos"
    action: "ingest"
    args: { path: "/tmp/cards.json" }
  - tool: "ontoderive"
    action: "derive"
    args: { eidos: true }
```

---

## 五、L3 场景层: 典型管线

### 5.1 知识库构建管线

```
eidos define KnowledgeCard         # 1. 建模
→ minerva extract                   # 2. 抽取
→ kos ingest                        # 3. 存储
→ eidos validate --pipeline         # 4. 校验
→ eidos-viz graph --type document   # 5. 可视化
```

### 5.2 推理链路管线

```
kos search "量子" --meta-type DOMAIN  # 1. 搜索实体
→ ontoderive derive --pipeline        # 2. 推导
→ eidos-viz graph --input fact        # 3. 可视化推导结果
```

### 5.3 一致性检查管线

```
eidos define schema --strict           # 1. 定义约束
→ kos stats --meta-type DOCUMENT       # 2. 检查现有数据
→ eidos validate --all --pipeline      # 3. 批量校验
```

---

## 六、增量实现路线

### Phase 3A (当前): 元模型层 + 可视化工具

| 任务 | 文件 | 预估 |
|------|------|------|
| `eidos/meta/__init__.py` — MetaModel + MetaType 枚举 | `eidos/src/eidos/meta/` | 1h |
| `eidos/types/inference_rule.py` — InferenceRule | `eidos/src/eidos/types/` | 30m |
| `eidos/types/state_machine.py` — StateMachine | `eidos/src/eidos/types/` | 30m |
| `eidos/types/relation.py` — Relation (w/ MetaRelationType) | `eidos/src/eidos/types/` | 30m |
| `eidos-viz` — Mermaid 可视化 | `eidos/src/eidos/viz.py` | 1h |
| `eidos meta` CLI 命令 | `eidos/src/eidos/cli.py` (扩展) | 30m |
| 测试: meta/, viz/, 新增 types | `eidos/tests/` | 1h |

### Phase 3B (后续): Pipeline 编排

| 任务 | 文件 | 预估 |
|------|------|------|
| Pipeline protocol 定义 | `eidos/src/eidos/pipeline/` | 30m |
| `eidos pipeline` CLI 命令 | `eidos/src/eidos/cli.py` | 1h |
| Tool adapter: minerva → pipeline | `minerva/src/minerva/knowledge/` | 1h |
| Tool adapter: kos → pipeline | `kos/commands/pipeline.py` | 1h |
| Tool adapter: ontoderive → pipeline | `ontoderive/engine/ecosystem/` | 1h |

### Phase 3C (远期): 场景模板

| 任务 | 描述 |
|------|------|
| 知识库构建场景模板 | 预设 pipeline.yaml |
| 推理链路场景模板 | 预设 pipeline.yaml |
| Agora pipeline 集成 | 通过 Agora MCP 调度管线 |

---

## 七、核心原则

1. **增量式** — 不重构现有项目，只新增模块和适配器
2. **元模型是文档 → 代码** — SSOT 的 Markdown 设计变成可执行的 Python
3. **Pipeline 是可选层** — 每个工具独立可用，pipeline 只是串联方式
4. **JSON 是通用接口** — 工具间通过 JSON 交换，不共享内存/对象
5. **可视化是文本优先** — Mermaid 在终端即可查看，不依赖前端
