# AetherForge API Reference

> 完整 API 文档覆盖所有公开模块。
> 自动生成入口: `make docs`

---

## Gateway (`llm_gateway`)

### Provider 抽象

```python
from llm_gateway.provider import (
    LLMProvider,      # ABC — 所有 Provider 的基类
    LLMRequest,       # 请求: prompt, model, max_tokens, temperature...
    LLMResponse,      # 响应: content, model, input_tokens, output_tokens...
    MockLLMProvider,  # 测试用 Mock
    NoneProvider,     # 静默降级
)

# 所有 Provider 子类
from llm_gateway.providers import (
    ollama_provider,    # OllamaProvider
    openai_provider,    # OpenAIProvider
    anthropic_provider, # AnthropicProvider
    gemini_provider,    # GeminiProvider
    deepseek_provider,  # DeepSeekProvider
    hitl_provider,      # HitlLLMProvider (人机协作)
)
```

### 自动检测

```python
from llm_gateway.detection import (
    detect_backends,    # → list[LLMProvider] 自动发现可用后端
    create_provider,    # (name: str, **kwargs) → LLMProvider
)
```

### 调度 (RouterPipeline)

```python
from llm_gateway.policies import (
    RouterPipeline,     # Filter→Score→Select 编排器
    # Filters (硬约束)
    OnlineFilter,       # 仅在线模型
    CapacityFilter,     # 容量未满 (max_load)
    BudgetFilter,       # 预算范围内 (max_cost_per_1k)
    CapabilityFilter,   # 能力匹配
    # Scores (软偏好)
    CostScore,          # 便宜优先
    SpeedScore,         # 快速优先
    CapabilityScore,    # 能力匹配优先
    BalancedScore,      # 综合加权 (0.3 cost + 0.3 speed + 0.4 cap)
    ZoneAffinityScore,  # 同 zone/拓扑优先

    # 低阶 API
    register_policy,    # [legacy] 注册自定义策略
    list_policies,      # 列出所有策略
    score_models,       # [legacy] 策略评分
)
```

### 限流

```python
from llm_gateway.rate_limiter import (
    RateLimiter,        # tpm/rpm 双维度滑动窗口限流器
    RateLimitError,     # 限流异常
)
```

### 指标

```python
from llm_gateway.metrics import (
    MetricsCollector,   # Prometheus 兼容指标收集
    ModelMetrics,       # 单模型聚合指标
)
```

### 注册表

```python
from llm_gateway.registry import (
    ModelRegistry,      # Provider + Model 生命周期管理
)
```

### 类型定义

```python
from llm_gateway.types import (
    ProviderConfig,     # Provider 连接配置
    ChatOptions,        # 聊天选项
    ChatResult,         # 聊天结果
    StreamChunk,        # 流式块
    ModelDescriptor,    # 模型描述 (id, provider, capabilities, cost...)
    ModelRoutePolicy,   # 路由策略 (strategy, priority, fallback_chain)
    ModelRequest,       # 调度请求
    ModelSelection,     # 调度结果
    LoadInfo,           # 负载信息
    SchedulerConfig,    # 调度器配置
    FallbackRule,       # 多级回退规则 (model, strategy, timeout, cooldown)
)
```

---

## Mesh (`compute_mesh`)

### 拓扑 (L2)

```python
from compute_mesh.topology import (
    ComputeNode,        # 算力节点 (node_id, topology, status, load...)
    NodeStatus,         # 节点状态: UNKNOWN, ONLINE, OFFLINE, DEGRADED, DRAINING
    NodeEngineType,    # 引擎类型: LOCAL_DAEMON, CLOUD_API, REMOTE_WORKER...
    TopologyLabels,     # 四层拓扑: region, zone, rack, host
    NodeRegistry,       # 线程安全节点注册表
    TopologyScanner,    # 多后端发现编排器
    # 发现方法
    load_static_nodes,  # 从 L0 M1 YAML 加载
    probe_local_daemons, # 探测本地守护进程
    detect_cloud_nodes,  # 从环境变量检测云 API
)
```

### 资源池 (L3)

```python
from compute_mesh.pool import (
    ComputePool,        # 资源聚合: 扫描/健康检查/负载追踪/自动扩缩容
    CostTracker,        # 成本记录 (SQLite + JSONL 双写)
    CostDB,             # SQLite 成本数据库
)
```

**ComputePool 方法**:
```python
pool = ComputePool()
pool.scan()                       # 拓扑发现
pool.health_check_node(id)        # 单节点健康检查 → bool
pool.health_check_all()           # 全节点健康检查 → dict[id, bool]
pool.get_online()                 # 在线节点 → list[ComputeNode]
pool.get_best_node(zone="")       # 最优节点
pool.assign_request(id)           # 分配请求 → bool
pool.release_request(id)          # 释放请求 → bool
pool.auto_scale_workers(reg, ...) # 自动扩缩容 Worker
pool.get_load_report()            # 负载报告
pool.get_status()                 # 完整状态
pool.get_summary()                # 紧凑摘要
```

### 调度 (L4)

```python
from compute_mesh.scheduler import (
    MeshScheduler,      # 拓扑感知 Mesh 调度器 (含请求队列)
)
```

**MeshScheduler**:
```python
sched = MeshScheduler(pool, gateway, max_queue_size=100)
await sched.select_model(request, policy)  # 选择最优模型
sched.enqueue_request(request, policy)     # 排队 (满负荷时)
sched.dequeue_ready()                      # 退队
sched.get_queue_stats()                    # 队列状态
sched.get_scheduler_status()               # 调度器状态
```

### Worker (L5)

```python
from compute_mesh.worker import (
    MeshWorker,         # 执行槽位
    WorkerStatus,       # IDLE, BUSY, DRAINING, ERROR, TERMINATED
    WorkerRegistry,     # Worker 注册表 (心跳/状态)
    TaskDispatcher,     # 任务分发引擎
    # 消息总线
   WorkerMessageBus,    # Worker 间通信 (内存+SQLite)
    Message,            # 消息体
)
```

**StepCallbacks**:
```python
from compute_mesh.worker.callbacks import StepCallbacks
cb = StepCallbacks()

@cb.on_task_start
def log_start(worker_id, task):
    print(f"Starting task on {worker_id}")

@cb.on_task_complete
def log_done(worker_id, result):
    print(f"Done: {result['latency_ms']}ms")

dispatcher.set_callbacks(cb)
```

**ObjectStore**:
```python
from compute_mesh.worker.object_store import ObjectStore
store = ObjectStore()
oid = store.put({"large_data": "..." * 1000})  # returns reference
data = store.get(oid)     # retrieve by reference
store.delete(oid)         # explicit delete
# TTL support
temp_oid = store.put({"temp": True}, ttl=60)  # auto-expires in 60s
```

**TaskDispatcher**:
```python
dispatcher = TaskDispatcher(pool, registry)
dispatcher.dispatch(node_id, prompt="...")   # 分发任务
dispatcher.provision_for_node(id, count=4)    # 为节点创建 Worker
dispatcher.provision_all(workers_per_node=4)  # 为所有节点创建 Worker
```

---

## Swarm (`swarm_engine`)

### 核心模块

```python
from swarm_engine import (
    # 拍卖市场
    TaskAuctioneer,       # 市场化任务分配
    TaskBidder,           # 竞标者
    # DAG
    TaskDAG,              # 任务依赖图
    TaskNode,             # DAG 节点
    # 生命周期
    SwarmStateMachine,    # 状态机
    # 经济
    EnergyLedger,         # EU 能量货币账本
    # 事件
    EventBus,             # 事件总线
    # Worker
    WorkerAbstract,       # Worker 抽象基类
    # 桥接
    GatewaySynapse,       # Gateway ↔ Swarm 桥接 🆕
)
```

### GroupChat (vs AutoGen) 🆕

```python
from swarm_engine.group_chat import GroupChat, GroupChatAgent, GroupChatResult

chat = GroupChat(agents=[
    GroupChatAgent(name="Researcher", system_prompt="You research.", role="researcher"),
    GroupChatAgent(name="Writer", system_prompt="You write.", role="writer"),
], max_turns=6)

result = chat.run("Research and write about AI safety")
for msg in result.history:
    print(f"[{msg.sender}]: {msg.content[:100]}")
```

### GraphWorkflow (vs LangGraph) 🆕

```python
from swarm_engine.graph_workflow import GraphWorkflow

wf = GraphWorkflow()

@wf.node("research")
def research(state):
    # state is a shared dict across all nodes
    return {"findings": f"Research on {state['topic']}"}

@wf.node("write")
def write(state):
    return {"output": f"Based on: {state['findings']}"}

wf.add_edge("research", "write")
wf.set_entry("research")
state = wf.run({"topic": "AI"})
print(state["output"])
```

Supports LLM nodes, conditional branching, cycle detection, and `visualize()`.

### 层级编排 (Hierarchical Process)

```python
from swarm_engine.hierarchical_process import (
    HierarchicalProcess,  # Manager→Worker 层级执行引擎
    HierarchicalResult,   # 执行结果
    SubTask,              # 子任务
)
```

**快速开始**:
```python
process = HierarchicalProcess()
result = process.run(
    manager_prompt="Plan a 3-day Beijing itinerary",
    worker_roles=["researcher", "writer", "critic"],
)
print(result.final_output)  # 合成后的最终输出
print(result.subtasks)      # 所有子任务详情
```

---

## Config (`aetherforge.config`)

```python
from aetherforge.config import (
    load_config,            # 加载配置 → AetherForgeConfig
    write_default_config,   # 写入默认配置到文件
    AetherForgeConfig,      # 根配置对象
    # 子配置
    GatewayConfig,
    RateLimiterConfig,
    TopologyConfig,
    PoolConfig,
    WorkerConfig,
    SwarmConfig,
    MetricsConfig,
    LoggingConfig,
)
```

**配置加载顺序**:
1. `./aetherforge.yaml` (项目本地)
2. `~/.aetherforge/config.yaml` (用户全局)
3. `AETHERFORGE_CONFIG` 环境变量
4. 环境变量覆盖 (`AETHERFORGE_RATE_LIMIT_TPM=50000`)
5. 内置默认值

---

## 错误处理

```python
from llm_gateway.provider import (
    LLMError,                # 基础异常
    LLMAvailabilityError,    # Provider 不可用
    LLMRetryExhaustedError,  # 重试耗尽
)
from llm_gateway.rate_limiter import (
    RateLimitError,          # 限流
)
```

---

## 完整的 E2E 示例

```python
"""完整的 AetherForge 使用流程"""

# 1. 加载配置
from aetherforge.config import load_config
cfg = load_config()

# 2. 发现算力节点
from compute_mesh.pool import ComputePool
from compute_mesh.topology import TopologyScanner

pool = ComputePool()
pool.scan()
pool.health_check_all()
print(f"在线: {pool.get_summary()['online']}/{pool.get_summary()['total']} 节点")

# 3. 配置限流
from llm_gateway.rate_limiter import RateLimiter
limiter = RateLimiter()
cfg.apply_to_rate_limiter(limiter)

# 4. 创建 Worker 池
from compute_mesh.worker import WorkerRegistry, TaskDispatcher
wreg = WorkerRegistry()
dispatcher = TaskDispatcher(pool, wreg)
workers = dispatcher.provision_all()
print(f"Worker: {len(workers)} 个")

# 5. 调度请求
from llm_gateway.types import ModelRequest, ModelRoutePolicy
from llm_gateway.scheduler import ModelScheduler as GatewayScheduler
from llm_gateway.registry import ModelRegistry
from compute_mesh.scheduler import MeshScheduler

gateway = GatewayScheduler(ModelRegistry(), rate_limiter=limiter)
mesh_sched = MeshScheduler(pool, gateway)

request = ModelRequest(task="你好", required_capabilities=["chat"])
policy = ModelRoutePolicy(
    strategy="balanced",
    fallback_chain=[FallbackRule(model="claude-3", strategy="speed-first")],
)
selection = await mesh_sched.select_model(request, policy)

# 6. 执行生成
if selection:
    result = dispatcher.dispatch(selection.provider_name, prompt="你好")
    print(f"生成: {result['content'][:100]}")

# 7. 记录成本
from compute_mesh.pool import CostTracker
tracker = CostTracker(pool.registry)
tracker.record("ollama-local", prompt_tokens=50, completion_tokens=30)
print(f"成本: {tracker.get_report()}")

---

## 新增模块

### PricingRegistry — 模型定价

```python
from llm_gateway.pricing import PricingRegistry

pricing = PricingRegistry()
# 查询模型价格
cost = pricing.get_cost("gpt-4o")  # → {"input": 0.0025, "output": 0.01}
# 搜索支持 vision 的模型
models = pricing.search(capability="vision")
# 列出所有模型
all_prices = pricing.list_all()
```

### CredentialsManager — 凭据与配额

```python
from llm_gateway.credentials import CredentialsManager

cm = CredentialsManager()
# 添加凭据
cm.add_key("openai", "sk-xxx")
# 获取 Key (支持多 Key 加权轮转)
key = cm.get_key("openai")
# 设置月预算
cm.set_budget("deepseek", monthly_limit=50.0, action="block")
# 检查配额
quota = cm.get_quota("deepseek")
# 记录用量
cm.record_usage("deepseek", cost=0.015, model="deepseek-chat")
```

### M1Loader — L0 MOF 加载器

```python
from compute_mesh.topology.m1_loader import M1Loader, MachineInfo, NetworkZoneInfo

loader = M1Loader()
# 获取机器信息
machine = loader.get_machine("ENG-LMSTUDIO-Y7000P")
print(machine.summary)  # → "i7-13500H · Laptop"
# 获取网络区域
zone = loader.get_zone("ZONE-LOCALHOST")
print(zone.latency_profile)  # → "ultra_low"
```

## CLI 新增命令

### credentials

```bash
aetherforge credentials list                    # 列出所有凭据
aetherforge credentials add openai --key sk-..  # 添加凭据
aetherforge credentials budget deepseek --limit 50 --action block  # 设预算
aetherforge credentials quota deepseek          # 查看配额
```

### models

```bash
aetherforge models list                         # 列出可用模型
aetherforge models list --cost                  # 列出模型+定价
```
```
