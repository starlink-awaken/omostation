# 蜂群式AI超级大脑 — API 文档

## L0 核心 API

### StateSyncService

```python
from ecos.l0.governance import StateSyncService, SyncStrategy

# 创建节点
node = StateSyncService("node-id", SyncStrategy.EVENTUAL)

# 设置状态
node.set("key", "value")

# 获取状态
value = node.get("key")

# 生成快照
snap = node.generate_snapshot()

# 同步状态
result = node.sync_from_snapshot(remote_snap)

# 获取增量
delta = node.get_delta_since(remote_clock)
```

### TaskScheduler + DAGScheduler

```python
from ecos.l0.governance import TaskScheduler, DAGScheduler

ts = TaskScheduler()
dag = DAGScheduler(ts)

# 提交任务
ts.submit_task("task-1", "任务名称", required_capabilities=["cap1"], priority=10)

# 添加依赖
dag.add_dependency("task-2", "task-1")

# 拓扑排序
order = dag.get_topological_order()

# 关键路径
critical = dag.get_critical_path()

# 执行计划
plan = dag.get_execution_plan()
```

### CollectiveDecision

```python
from ecos.l0.governance import CollectiveDecision, DecisionMethod

cd = CollectiveDecision()

# 创建提案
cd.create_proposal("p1", "提案标题", ["选项A", "选项B"], DecisionMethod.MAJORITY_VOTE)

# 投票
cd.vote("p1", "agent-1", "选项A")
cd.vote("p1", "agent-2", "选项A")

# 决策
result = cd.decide("p1")

# 加权投票
cd.create_proposal("p2", "加权提案", ["X", "Y"], DecisionMethod.WEIGHTED_VOTE, agent_weights={"boss": 10, "worker": 1})
cd.vote("p2", "boss", "X")
cd.vote("p2", "worker", "Y")
result = cd.decide("p2")
```

### KnowledgeGraphBuilder

```python
from ecos.l0.governance import KnowledgeGraphBuilder

kg = KnowledgeGraphBuilder()

# 添加节点
kg.add_node("n1", {"type": "concept"})
kg.add_node("n2", {"type": "fact"})

# 添加边
kg.add_edge("n1", "n2", "related", weight=1.0)

# PageRank
pr = kg.pagerank()

# 度中心性
dc = kg.degree_centrality()

# 介数中心性
bc = kg.betweenness_centrality()

# 社区发现
communities = kg.find_communities()

# 路径搜索
paths = kg.find_path("n1", "n2")
```

### RecommendationEngine

```python
from ecos.l0.governance import (
    PersonalKnowledgeManager, KnowledgeNode, KnowledgeType,
    PreferenceEngine, RecommendationEngine,
)

km = PersonalKnowledgeManager()
pe = PreferenceEngine()

# 添加知识
km.add_knowledge(KnowledgeNode(
    node_id="doc-1", knowledge_type=KnowledgeType.FACT,
    content={"text": "AI fundamentals"}, tags=["ai"],
))

# 学习偏好
pe.learn("user-1", "ai", "topic", 5.0)

# 推荐
engine = RecommendationEngine(km, pe)
recs = engine.recommend("user-1", limit=5)

# 相似推荐
similar = engine.recommend_similar("doc-1", limit=3)
```

## L3 MCP 工具

| 工具名 | 参数 | 说明 |
|--------|------|------|
| governance_check | dimension: X1/X2/X3/X4/all | 运行治理检查 |
| governance_status | - | 查看治理状态 |
| governance_history | days: int | 查看历史记录 |
| cluster_list | - | 列出集群节点 |
| cluster_health | - | 集群健康检查 |
| swarm_status | - | 蜂群状态 |
| swarm_detect | - | 涌现行为检测 |
| swarm_decide | proposal_id, agent_id, option | 集体决策投票 |
| knowledge_stats | - | 知识库统计 |
| knowledge_query | query: str, limit: int | 查询知识 |
| knowledge_add | key: str, content: dict, tags: list | 添加知识 |
| task_submit | task_id: str, name: str, ... | 提交任务 |
| task_status | task_id: str | 查询任务状态 |
| role_switch | agent_id: str, new_role: str | 切换角色 |

---

## Workflow 引擎

### 架构

```
M1 YAML → loader.py → validator.py (X1-X4) → executor.py
            └── (load workflow)       │
                                      └──→ backend_registry.py → backend(X)
```

5 个后端注册:
- `default` — 硬编码 subprocess action 执行器（向后兼容）
- `agora` — Agora MCP 路由（跨层经 I0 BOS Mesh）
- `symphony` — Symphony 状态机编排（协议级阶段跃迁）
- `swarm` — Swarm 多 Agent 任务编排（aetherforge）
- `runtime` — Runtime 项目生命周期编排（INIT→DELIVERY）
- `metaos` — MetaOS DAG 工作流引擎（可选依赖）

### CLI 用法

```bash
# 列出所有可用工作流
ecos workflow list

# 执行工作流
ecos workflow run WORKFLOW-ECOS-DAILY-HEALTH
ecos workflow run WORKFLOW-ECOS-DAILY-HEALTH --dry-run

# 查看工作流定义
ecos workflow describe WORKFLOW-ECOS-DAILY-HEALTH

# 查看后端注册状态
ecos workflow backends

# 查看运行历史
ecos workflow logs --recent 10
ecos workflow logs --status failed --verbose
ecos workflow logs WORKFLOW-ECOS-DAILY-HEALTH
```

### Python API

```python
from ecos.workflow import (
    # 加载
    load_workflow,      # load_workflow(name) -> dict | None
    list_workflows,     # list_workflows() -> list[dict]
    # 执行
    execute_workflow,   # execute_workflow(name, params, dry_run) -> dict
    execute_m1_workflow,# execute_m1_workflow(name, params, dry_run) -> dict
    # 后端
    register,           # register(name, module_path, entrypoint, description)
    resolve,            # resolve(m1_node) -> Callable
    list_backends,      # list_backends() -> list[dict]
    # 事件
    listen_forever,     # listen_forever(host="0.0.0.0", port=7432)
    match_event,        # match_event(event, triggers) -> list
)

# 示例: 执行工作流
result = execute_m1_workflow("WORKFLOW-ECOS-DAILY-HEALTH")
print(result["passed"], "✅", result["failed"], "❌")

# 示例: 注册自定义后端
register("my-backend", "my_package.my_module", "execute",
         description="自定义后端")
```

### 工作流定义格式 (M1)

工作流定义存储在 `ssot/mof/m1/workflow/WORKFLOW-*.yaml`:

```yaml
type: Workflow
id: WORKFLOW-ECOS-DAILY-HEALTH
name: eCOS 日常健康巡检
domain: governance
layer: L0
bos_uri: "bos://governance/workflows/daily-health"
status: active

execution:
  backend: default
  mode: workflow
  on_failure: continue

steps:
  - name: 健康检查
    action: health_check
  - name: 域漂移检测
    action: domain_audit
```

### 运行历史 (M0)

每次执行自动生成 M0 快照在 `~/.omo/state/workflow-runs/`:

```bash
ecos workflow logs                   # 全部历史
ecos workflow logs --status failed   # 只查失败的
ecos workflow logs WORKFLOW-ECOS-DAILY-HEALTH  # 查特定工作流
```

### 事件驱动

```bash
# 启动事件监听器（默认 :7432）
python -m ecos.workflow.event_listener

# 事件格式 (SSE)
# event: bos://ecos/events/health_check
# data: {"action": "health_check", "source": "...", "timestamp": "..."}
```
