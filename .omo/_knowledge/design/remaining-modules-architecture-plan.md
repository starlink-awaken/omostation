# 剩余 62 模块深度拆解 · 架构方案

> 2026-06-02 · Phase 17 Wave 5 · 精准适配阶段
> 前四波已迁移 ~284 模块，剩余 62 个需逐文件精确修复

---

## 一、现状分类

### A 类: 已写入但有语法错误 (40 模块)

这些文件已被 Wave 4 批量脚本写入磁盘，但因复杂 BaseMembrane 嵌套导致语法错误。
根因：regex 无法正确处理以下模式：

```
try:
    from nucleus.Z_Microkernel.organs.base_membrane import BaseMembrane
except (ModuleNotFoundError, ImportError):
    class BaseMembrane:
        ...
        def some_method(self):
            try:                    ← 嵌套 try，regex 只匹配到外层
                ...
            except:
                ...
```

| 器官 | 模块数 | 目标包 | 典型问题 |
|------|:-----:|--------|------|
| D_Gateway | 14 | agora | 多层 mixin 继承，api_gateway 5-way mixin |
| D_Logos | 9 | ontoderive | pipeline 步骤类嵌套 try/except |
| D_Memory | 11 | eidos | knowledge_graph 深度继承链 |
| D_Intelligence | 4 | engine-core | 推理引擎内部 try/except |
| D_Governance | 2 | shared-lib | harvest_scheduler 跨器官引用 |

**修复策略**: 读源文件 → 精确替换 BaseMembrane 特定行号范围 → 验证语法

### B 类: 从未提取 (19 模块)

| 子类 | 模块 | 行数 | 目标包 |
|------|------|:--:|--------|
| **Workers** | 12 engine workers | ~73K | engine-core |
| **Core** | execution_scheduler | 37K | engine-core |
| **Core** | worker_dispatcher | 31K | engine-core |
| **Core** | semantic_orchestrator | 35K | engine-core |
| **Core** | intent_digestor | 26K | engine-core |
| **Core** | hybrid_classifier | 16K | engine-core |
| **Core** | ils_engine | 31K | engine-core |
| **Core** | nks_task_planner | 32K | engine-core |

**修复策略**: 逐个读取源文件 → 手动清理 → 写目标文件 → 验证

### C 类: 源文件缺失 (3 模块)

| 模块 | 器官 | 原因 |
|------|------|------|
| weighted_voting | D_Governance | 路径不匹配，需搜索 |
| D_Continuity 6个 | D_Continuity | 目录结构与预期不同，需搜索 |

---

## 二、耦合模式分类与解决方案

### 模式 1: 简单 BaseMembrane 继承 (25 模块: workers + intelligence)

```python
# 原始模式
try:
    from nucleus.Z_Microkernel.organs.base_membrane import BaseMembrane
except (ModuleNotFoundError, ImportError):
    class BaseMembrane:
        def __init__(self, metadata_path="unknown"):
            ...
        ...

class FooWorker(BaseMembrane):
    def __init__(self):
        super().__init__(metadata_path="...")
        ...
```

**解决方案**:
1. 删除整个 try/except 块 (精确匹配行范围)
2. `class FooWorker(BaseMembrane):` → `class FooWorker:`
3. `super().__init__(metadata_path="...")` → 删除或替换为 `self.status = "active"`

**目标包映射**:
- 12 workers → `engine-core/src/engine_core/workers/` (新建子目录)
- 5 intelligence → `engine-core/src/engine_core/` (已有目录)

### 模式 2: 多级 Mixin 继承 (14 模块: D_Gateway API 网关)

```python
# 原始模式 - api_gateway.py 典型结构
class APIGateway(
    OAuth2Mixin,       # 来自 oauth2_server
    RateLimitMixin,    # 来自 rate_limiter
    RoutingMixin,      # 来自 api_routing_mixin
    DocsMixin,         # 来自 api_docs_mixin
    HandlersMixin,     # 来自 api_handlers_mixin
    BaseMembrane        # ← 需要移除
):
```

**解决方案**:
1. 从多继承列表中移除 BaseMembrane
2. 将所有 mixin 导入路径从 `organs.D_Gateway.organs.xxx` 改为 `agora.xxx`
3. 删除 BaseMembrane 导入和 try/except 块

**目标**: `agora/src/agora/`

### 模式 3: 深度跨器官耦合 (10 模块: D_Memory + D_Logos)

```python
# knowledge_graph_engine.py 典型依赖
from organs.D_Memory.organs.triple_store import TripleStore
from organs.D_Memory.organs.fact_graph import FactGraph
from nucleus.Z_Microkernel.organs.base_membrane import BaseMembrane
from nucleus.Z_Microkernel.facades import get_path_resolver
```

**解决方案**:
1. `from organs.D_Memory.organs.xxx` → `from eidos.xxx`
2. `from nucleus.Z_Microkernel.facades` → 删除或用本地路径替代
3. `get_path_resolver()` → `Path("./data/")` 默认值
4. 保留核心业务逻辑不变

**目标**: `eidos/src/eidos/`

### 模式 4: Pipeline 步骤类 (9 模块: D_Logos pipeline)

```python
# pipeline.py / pipeline_steps/*.py 典型结构
class PipelineStep(BaseMembrane):
    def execute(self, context):
        try:
            result = self._run(context)
        except Exception as e:
            self._handle_error(e)
```

**解决方案**:
1. 删除 BaseMembrane 继承，保留 try/except 业务逻辑
2. `from organs.D_Logos.organs.pipeline_models` → `from engine.pipeline_models`
3. `from organs.D_Logos.organs.pipeline_steps.xxx` → `from engine.xxx`

**目标**: `ontoderive/engine/`

---

## 三、执行策略

### 阶段 1: A类精准修复 (40 模块)

对每个已写入但有语法错误的文件：
1. 重新读取对应源文件
2. 识别具体的 BaseMembrane 相关行号
3. 精确删除/替换这些行
4. 编译验证

**专项修复清单（按优先级）**:

#### P0: eidos 核心 (11 模块，最高价值)
```
knowledge_graph_engine.py  - 替换跨器官导入，删除 BaseMembrane + nucleus facades
unified_memory_api.py      - 门面模式，删除 BaseMembrane 继承
cross_domain_analyzer.py   - 替换 ProjectPaths → Path("./data/")
memory_manager.py          - 替换 MemoryMount → 本地接口
emotional_memory.py        - 删除 BaseMembrane
dream_engine.py            - 最小模块，快速修
information_pipeline.py    - 替换导入路径
nks_query_cache.py         - 替换导入路径
nks_semantic_search.py     - 替换导入路径
nks_monitor.py             - 替换导入路径
nks_tree_sitter_extractor.py - 独立模块，替换导入
```

#### P1: agora 网关 (14 模块，API基础设施)
```
api_gateway.py             - 移除 BaseMembrane from mixin list
api_routing_mixin.py       - 删除 BaseMembrane
nks_mcp_bridge.py          - 替换 D_Memory 引用为 lazy import
knowledge_injector.py      - 删除 BaseMembrane
holo_memory_injector.py    - 删除 BaseMembrane
memory_sync.py             - 删除 BaseMembrane
cross_node_extension.py    - 替换跨节点引用
soul_handshake.py          - 删除 BaseMembrane
edge_computing.py          - 删除 BaseMembrane
extension_signature.py     - 删除 BaseMembrane
possession_manager.py      - 替换 Z_Spore.possession
raft_config_manager.py     - 删除 BaseMembrane
plugin_market_api.py       - 删除 BaseMembrane
integrations.py            - 删除 BaseMembrane，保留集成逻辑
```

#### P2: ontoderive pipeline (9 模块)
```
pipeline.py                - 删除 BaseMembrane，保留 pipeline 编排
context_compiler.py        - 删除 BaseMembrane
auto_fix_engine.py         - 删除 BaseMembrane
meta_validate.py           - 组合模式，谨慎处理
meta_evolve.py             - BaseMembrane 子类多，逐个处理
fault_tolerance_policy.py  - 删除 Bosevent 引用或 stub
alignment_engine_core.py   - 替换导入路径
governance_steps.py        - 替换导入路径
validation_steps.py        - 替换导入路径
```

#### P3: 其他 (6 模块)
```
intent_classifier.py (D_Intelligence)  - 删除 InferenceOracle 引用
reasoning_engine.py (D_Intelligence)   - 已OK文件，仅验证
harvest_scheduler.py (D_Governance)    - 删除 D_Harvest 跨器官引用
evolution_metrics.py (D_Governance)    - 删除 BaseMembrane
adr_storage.py (D_Governance)          - 删除 BaseMembrane
federation_hive.py (D_Governance)      - 删除 BaseMembrane
```

### 阶段 2: B类新提取 (19 模块)

#### 2.1: Workers 子目录 (12 模块)
创建 `engine-core/src/engine_core/workers/` 子目录，集中放置所有 engine workers:
- 每个 worker 的耦合模式几乎相同：继承 BaseMembrane + `super().__init__`
- 批量处理：统一的清理脚本

#### 2.2: Core Orchestrators (7 模块)
- 这些是大文件（16K-37K 行），耦合最复杂
- 逐文件手工适配：读源 → 理解结构 → 精确修改 → 验证

### 阶段 3: C类搜索补齐 (3 模块)
- 搜索 D_Governance 中的 weighted_voting 实际路径
- 搜索 D_Continuity 目录的实际结构

---

## 四、关键技术决策

### 决策 1: Worker 子目录
**选择**: 在 engine-core 下创建 `workers/` 子目录
**理由**: 12 个 worker 文件职责相同（引擎工作器），不应平铺在 engine_core 根目录
**结构**:
```
engine-core/src/engine_core/workers/
├── __init__.py
├── claude_worker.py
├── gemini_worker.py
├── copilot_worker.py
├── opencode_worker.py
├── hitl_worker.py
├── internal_llm_worker.py
├── sensor_worker.py
├── cli_avatar_worker.py
├── github_sensor_worker.py
├── web_scraper_worker.py
├── notifier_worker.py
├── synapse_hub.py        (已提取)
└── membrane_gateway.py
```

### 决策 2: 跨器官引用处理
**选择**: 用 Protocol/ABC 接口替代具体类型引用，用 lazy import 包裹
**理由**: 高耦合模块的跨器官引用在 kairon 中无对应包（如 D_Economy）
**实现**: `TYPE_CHECKING` 块 + `importlib.import_module` lazy load

### 决策 3: nucleus 路径替代
**选择**: `ProjectPaths` → `pathlib.Path("./data/")`, `BOSUri` → `str`
**理由**: nucleus 框架概念在 kairon 中无对应物，用标准库替代

### 决策 4: BaseMembrane 状态管理
**选择**: 保留 `self.status = "active"` 作为实例属性，删除 `super().__init__(metadata_path=...)`
**理由**: 大量代码依赖 `self.status` 属性进行状态检查

---

## 五、验收标准

```
[ ] A类 40 个文件全部编译通过 (python -m py_compile)
[ ] B类 19 个文件全部写入并编译通过
[ ] C类 3 个文件定位并提取
[ ] engine-core workers/ 子目录创建，__init__.py 导出
[ ] make test-fast 无新增 failures
[ ] 各目标包导入测试通过
```

## 六、执行时间估算

| 阶段 | 模块数 | 预计时间 |
|------|:-----:|:-----:|
| A1: eidos 精准修复 | 11 | 30min |
| A2: agora 精准修复 | 14 | 30min |
| A3: ontoderive 精准修复 | 9 | 25min |
| A4: 其他精准修复 | 6 | 15min |
| B1: Workers 批量提取 | 12 | 15min |
| B2: Core 手工适配 | 7 | 40min |
| C: 搜索补齐 | 3 | 10min |
| **合计** | **62** | **~2.5h** |

---

*维护: 2026-06-02 · 剩余模块拆解架构方案 v1.0*
