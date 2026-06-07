# AetherForge 行业调研报告

> 对标 LiteLLM / K8s Scheduler / Ray / CrewAI 等主流方案，识别差距与优化方向
> 2026-06

---

## 一、调研对象

| 类别 | 系统 | 核心能力 | 对标 AetherForge 的层 |
|:-----|:-----|:---------|:---------------------|
| **AI Gateway** | LiteLLM | 100+ Provider 统一接口/智能路由/成本管控 | gateway |
| **AI Gateway** | Portkey | 可观测性/护栏/负载均衡 | gateway |
| **容器调度** | Kubernetes Scheduler | 谓词+优先级/拓扑感知/binpacking | mesh scheduler |
| **分布式计算** | Ray | 对象存储/placement group/actor 模型 | mesh worker |
| **Multi-Agent** | CrewAI | 角色编排/任务分解/流程控制 | swarm |
| **Multi-Agent** | AutoGen (Microsoft) | 对话式多Agent/代码执行 | swarm |
| **Workflow** | Temporal | 持久化工作流/重试/超时 | swarm lifecycle |

---

## 二、关键发现与差距分析

### 2.1 LiteLLM → Gateway

LiteLLM 的架构:

```
Client → LiteLLM Proxy (router) → Provider API
         ├── Router (策略: cost/latency/usage-based)
         ├── Failover (fallback 链)
         ├── Circuit Breaker (熔断)
         ├── Rate Limiter (tpm/rpm 限流)
         ├── Cost Tracker (SpendLog → DB)
         └── Virtual Keys (RBAC)
```

| 能力 | LiteLLM | AetherForge | 差距 |
|:-----|:-------:|:-----------:|:----:|
| Provider 数量 | 100+ | 6 | 🔴 仅覆盖主流, 缺 Azure/Bedrock/Vertex/智谱等 |
| 路由策略 | cost/latency/usage-based/custom | cost/speed/capability/balanced | 🟡 缺 usage-based、自定义策略注册 |
| Fallback 链 | 多级、可配置 | 单级 fallback_chain | 🟡 需支持 N 级 |
| Rate Limiting | tpm/rpm 双维度 | ❌ 无 | 🔴 |
| Virtual Keys | ✅ 团队管理 | ❌ 无 | 🟢 个人场景不急需 |
| 管理 UI | ✅ Web Dashboard | ❌ 无 | 🟢 eCOS 需求低 |
| 性能 | 5000 QPS (4C8G) | 未测试 | 🟡 需 benchmark |
| Token 计量 | ✅ 精确追踪 | JSONL 文件 | 🟡 需结构化存储 |
| MCP 集成 | ✅ 代理层 MCP | ✅ FastMCP | 🟢 一致 |

### 2.2 K8s Scheduler → Mesh Scheduler

K8s 调度框架:

```
Pod → Schedule Cycle
        ├── PreFilter  (硬约束)
        ├── Filter     (候选节点过滤)
        ├── PostFilter (抢占)
        ├── Score      (打分: binpacking/资源利用率)
        └── Bind       (绑定)
```

| 能力 | K8s | AetherForge | 差距 |
|:-----|:---:|:-----------:|:----:|
| Filter/Score 分离 | ✅ 插件架构 | ❌ 线性打分 | 🔴 需插件化调度框架 |
| 节点拓扑感知 | ✅ nodeSelector/affinity | 🟡 zone 偏好 | 🟡 细化到 region/zone/rack |
| Binpacking | ✅ 资源密度优先 | ❌ 无 | 🟡 GPU 利用率优化 |
| 抢占/驱逐 | ✅ 高优先级抢占 | ❌ 无 | 🟢 个人场景不急 |

### 2.3 Ray → Mesh Worker

| 能力 | Ray | AetherForge | 差距 |
|:-----|:---:|:-----------:|:----:|
| 分布式对象存储 | ✅ plasma store | ❌ 无 | 🔴 大消息传递效率 |
| Placement Group | ✅ 资源亲和性 | ❌ 无 | 🟡 多 Worker 协同 |
| Actor 模型 | ✅ 有状态服务 | ❌ 无 | 🟡 长期 Agent 对话 |
| 自动扩缩 | ✅ autoscaler | ❌ 无 | 🟢 单机场景不急 |

### 2.4 CrewAI/AutoGen → Swarm

| 能力 | CrewAI | AutoGen | AetherForge Swarm | 差距 |
|:-----|:------:|:-------:|:-----------------:|:----:|
| 角色定义 | ✅ role/goal/backstory | ✅ system_message | ✅ AgentCard | 🟢 完整 |
| 任务分解 | ✅ Task 对象 | ❌ 手动 | ✅ task_decomposer | 🟢 完整 |
| 流程控制 | sequential/hierarchical | round-robin | 🟡 auction/DAG | 🟡 缺 hierarchical |
| 工具集成 | ✅ MCP/自定义 | ✅ code execution | ✅ ToolSchema | 🟢 完整 |
| 记忆管理 | ✅ 短期+长期 | ✅ 对话历史 | ✅ context_injector | 🟢 完整 |
| 人机协作 | ❌ 无 | ✅ human_input_mode | ✅ HITL Provider | 🟢 有优势 |

---

## 三、优化方向

### 3.1 Gateway: 借鉴 LiteLLM

**P0: Rate Limiter**

```python
class RateLimiter:
    """滑动窗口限流器 (tpm/rpm 双维度)"""
    
    def __init__(self, tpm: int = 0, rpm: int = 0):
        self._tpm = TokenBucket(tpm)   # tokens per minute
        self._rpm = TokenBucket(rpm)   # requests per minute
    
    async def acquire(self, model: str, tokens: int) -> bool:
        """获取配额，返回是否允许通过"""
```

**P0: 插件化路由策略** (Filter/Score 两阶段)

```python
# 当前: 写死在 _registry dict 里的 _score_* 函数
# 目标: 插件式 Filter + Score 两阶段，与 K8s 对齐

@router_filter("cost-first")
def cost_filter(models, request) -> list[ModelDescriptor]:
    """Filter 阶段: 移除超预算模型"""
    budget = request.metadata.get("max_cost", float("inf"))
    return [m for m in models if m.effective_cost <= budget]

@router_score("cost-first")  
def cost_score(model, request) -> float:
    """Score 阶段: 越便宜分越高"""
    return 1.0 - (model.effective_cost / max_cost_reference)
```

**P1: 多级 Fallback 链**

```python
# 当前: fallback_chain: list[str]
# 目标: 支持策略 + 超时 + 退避
fallback_chain: list[FallbackRule]
```

### 3.2 Mesh Scheduler: 借鉴 K8s

**P0: Plugin-based Scheduling Framework**

```python
class SchedulerPlugin(ABC):
    @abstractmethod
    def filter(self, node: ComputeNode, request: ModelRequest) -> bool: ...
    @abstractmethod
    def score(self, node: ComputeNode, request: ModelRequest) -> float: ...

# 内置插件
plugins = [
    NodeOnlinePlugin(),       # Filter: 节点在线
    CapacityPlugin(),         # Filter: 有剩余容量
    ZoneAffinityPlugin(),     # Score: 同 zone 加分
    CostOptimizerPlugin(),    # Score: 成本优先
    LoadAwarePlugin(),        # Score: 低负载优先
    BinpackingPlugin(),       # Score: 高密度优先
]
```

**P1: 拓扑四层模型** (region/zone/rack/host)

### 3.3 Worker: 借鉴 Ray

**P2: Worker 消息总线**

```python
class WorkerMessageBus:
    """Worker 间消息传递 (内存 Queue + SQLite 持久化)"""
    def send(self, to_worker: str, message: dict): ...
    def receive(self, worker_id: str) -> list[dict]: ...
```

### 3.4 Swarm: 借鉴 CrewAI

**P2: Hierarchical Process**

```python
class HierarchicalProcess:
    """Manager 分解任务 → Worker 执行 → Manager 汇总"""
    def run(self, manager_agent, worker_agents, task): ...
```

---

## 四、优先级路线图

| 优先级 | 优化项 | 参考来源 | 工作量 | 影响 |
|:------:|:-------|:--------:|:------:|:----:|
| 🔴 P0 | Rate Limiter (tpm/rpm) | LiteLLM | 小 | 防止账单爆炸 |
| 🔴 P0 | 插件化调度框架 (Filter/Score) | K8s Scheduler | 中 | 路由可扩展 |
| 🟡 P1 | 多级 Fallback 链 | LiteLLM | 小 | 高可用提升 |
| 🟡 P1 | 拓扑四层模型 (region/zone/rack) | K8s | 小 | 调度精度 |
| 🟡 P1 | 结构化 Cost 存储 | LiteLLM | 中 | 成本可查 |
| 🟡 P2 | Hierarchical Process | CrewAI | 中 | 编排能力 |
| 🟡 P2 | Worker 消息总线 | Ray | 中 | 分布式协同 |
| 🟢 P3 | Metrics Collector | Prometheus | 中 | 可观测性 |
| 🟢 P3 | Placement Group | Ray | 大 | 资源亲和性 |

---

## 五、差异化优势（AetherForge 独有的）

| 能力 | AetherForge | LiteLLM | CrewAI | 说明 |
|:-----|:-----------:|:-------:|:------:|:------|
| **HITL Provider** | ✅ | ❌ | ❌ | 人机协作，Agent 无法决策时回退到人工 |
| **EnergyLedger** | ✅ | ❌ | ❌ | EU 能量货币经济账本，Agent 间的激励机制 |
| **三层融合** | ✅ | ❌ | ❌ | 单一代码库包含 gateway/mesh/swarm 全栈 |
| **ComputePool** | ✅ | ❌ | ❌ | 算力节点自动发现与健康管理 |
| **拍卖市场** | ✅ | ❌ | ❌ | 市场化 Agent 任务分配 |

建议**继续深化这些差异化能力**，同时补齐 LiteLLM 和 K8s 已验证的基础设施能力（Rate Limiter / 插件化调度 / Fallback）。
