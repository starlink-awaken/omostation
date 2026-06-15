# 蜂群式AI超级大脑 — 部署指南

## 快速开始

### 安装依赖

```bash
cd projects/ecos
uv sync
```

### 运行测试

```bash
# 全量测试
uv run pytest tests/ -q

# 分布式场景测试
uv run pytest tests/test_l0/test_distributed.py -v

# 集成测试
uv run pytest tests/test_l0/test_integration.py -v

# Lint 检查
uv run ruff check src/
```

## 架构概览

```
L0: 定义原语 (算法 + 数据结构)
    └── governance/ (16个核心模块)

L1: 运行时 (委托 L0)
    ├── runtime/ (CommunicationProtocol, StateSyncService, FailoverExecutor, LoadBalancerExecutor)
    └── transport.py (TCPNode)

L2: 引擎 (委托 L0)
    └── engine/ (CollaborationEngine, SwarmEngine, PersonalEngine)

L3: 入口 (调用 L0)
    └── entry/ (GovernanceCLI, GovernanceMCP)

common: 公共库
    ├── logger.py (JSON结构化日志)
    ├── exceptions.py (统一异常)
    ├── config.py (配置管理)
    ├── security.py (Token认证 + 输入校验)
    ├── cache.py (LRU缓存)
    └── persistence.py (SQLite持久化)
```

## 使用示例

### Python API

```python
from ecos.l0.governance import (
    StateSyncService, SyncStrategy,
    TaskScheduler, DAGScheduler,
    SwarmManager, CollectiveDecision, DecisionMethod,
    PersonalKnowledgeManager, KnowledgeNode, KnowledgeType,
)

# 状态同步
node_a = StateSyncService("node-a", SyncStrategy.EVENTUAL)
node_a.set("config", "production")
snap = node_a.generate_snapshot()

node_b = StateSyncService("node-b", SyncStrategy.EVENTUAL)
node_b.sync_from_snapshot(snap)

# DAG 任务调度
ts = TaskScheduler()
dag = DAGScheduler(ts)
ts.submit_task("design", "系统设计")
ts.submit_task("implement", "实现功能")
ts.submit_task("test", "测试验证")
dag.add_dependency("implement", "design")
dag.add_dependency("test", "implement")

order = dag.get_topological_order()
print(f"执行顺序: {order}")

# 蜂群决策
cd = CollectiveDecision()
cd.create_proposal("p1", "选择部署策略", ["canary", "blue-green"], DecisionMethod.MAJORITY_VOTE)
cd.vote("p1", "agent-1", "canary")
cd.vote("p1", "agent-2", "canary")
cd.vote("p1", "agent-3", "blue-green")
result = cd.decide("p1")
print(f"决策结果: {result}")

# 知识推荐
km = PersonalKnowledgeManager()
km.add_knowledge(KnowledgeNode(
    node_id="ai-basics", knowledge_type=KnowledgeType.FACT,
    content={"text": "Artificial Intelligence fundamentals"},
    tags=["ai", "basics"],
))
```

### CLI

```bash
# 检查治理状态
uv run python -m ecos.l3.entry check

# 查看集群状态
uv run python -m ecos.l3.entry cluster list

# 蜂群状态
uv run python -m ecos.l3.entry swarm status

# 知识库统计
uv run python -m ecos.l3.entry knowledge stats
```

### MCP 工具

```python
from ecos.l3.entry import GovernanceMCP

mcp = GovernanceMCP()

# 生成 Token
token = mcp.generate_token("admin-user")

# 调用工具
result = mcp.call_tool("governance_check", {"dimension": "X1"}, token=token)
print(result)

# 列出所有工具
tools = mcp.list_tools()
print(f"可用工具: {len(tools)} 个")
```

## 性能指标

| 操作 | 延迟 |
|------|------|
| 状态同步 (1000次) | < 100ms |
| PageRank (100节点×100次) | < 100ms |
| 集体决策 (1000次) | < 50ms |
| 多进程开销 (4进程) | < 1000ms |

## 测试覆盖

```bash
# 全量测试
uv run pytest tests/ -q  # 486 tests

# 分布式场景测试
uv run pytest tests/test_l0/test_distributed.py -v  # 28 tests

# 集成测试
uv run pytest tests/test_l0/test_integration.py -v  # 14 tests
```

## 生产级特性

- ✅ 错误处理: 全栈 try/except + ECOSException
- ✅ 日志记录: JSON 结构化日志
- ✅ 并发安全: threading.RLock
- ✅ 持久化: SQLite 状态存储
- ✅ 安全机制: Token 认证 + 输入校验
- ✅ 配置管理: 环境变量 + 配置文件
- ✅ 缓存机制: LRU 缓存

## 已知限制

- 通信层: asyncio TCP 因环境限制未完全测试
- 分布式验证: 多进程模拟，未真正多机测试
- 性能基准: 内存环境，未在生产环境验证
