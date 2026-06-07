# AetherForge Round 1 Design

> Swarm 清理 + RouteScheduler + OpenAgent 思路借鉴
> 2026-06

---

## 一、背景

### 1.1 Swarm 现状

```
swarm_engine/ → 96 .py 文件, ~18,000 行, 3 子目录

来源: SharedBrain B-OS D_Execution 域迁移
问题: 大量模块从未被 AetherForge 调用，部分已被 gateway/mesh 替代
目标: 按价值分类，保留有用的，剥离可复用的，删除空桩
```

### 1.2 调度现状

```
当前: GetBestNode() 只看 load_factor + network_zone
问题: 不看配额、不看成本、不看真实可用性
目标: RouteScheduler 三层路由 (Provider → Model → Node)
```

### 1.3 OpenAgent 借鉴

oh-my-openagent 的核心架构思路:

- **多模型编排**: 不同任务分配给最适合的模型（Claude 编排、GPT 推理、Kimi 速度）
- **Agent Team**: Agent 按角色和能力组成团队
- **Task Router**: 任务分解后路由到不同 Agent

对应到 AetherForge:
- RouteScheduler 的 Provider 评分机制（成本/速度/配额）就是对"多模型编排"的实现
- Swarm 的 auctioneer/bidder 机制就是对"Agent Team"的实现
- 我们的 QuotaEngine + PricingRegistry 提供了 OpenAgent 没有的**成本感知**能力

---

## 二、A: Swarm 模块清理

### 2.1 分类标准

```
🟢 保留 (42 文件, ~8,000 行) — 被 __init__.py 导出、有调用方、有价值的
🟡 剥离到 aetherforge-swarm-ext (28 文件, ~6,000 行) — 有价值但当前无用
🔴 删除 (12 文件, ~20 行) — 空桩/re-export
```

### 2.2 保留列表 (42 文件)

```
auctioneer / bidder                   市场机制 — 与 RouteScheduler 互补
dag                                   任务DAG
economy_seed                          EnergyLedger 经济账本
event_bus                             事件总线
group_chat / graph_workflow           🆕 群聊 + 工作流
hierarchical_process / monitor        🆕 层级编排 + 监控
synapse_gateway                       Gateway 桥接
conflict_resolution / resolver        CRDT 冲突解决
arbitrator                            冲突仲裁
context_injector                      上下文注入
env_resolver                          环境解析
binding_strategies / call_dispatcher  核心调度
capability / capability_matcher       能力匹配
cost_aware_dispatcher                 成本感知分发
domain_router / routing / router      路由体系
goal_task_mapper                      目标映射
hybrid_classifier                     混合分类
inference_engine / reasoning_engine   推理引擎
lifecycle_* (7 文件)                  生命周期框架
local_planner                         本地规划
retry_policy                          重试策略
role_message                          角色消息
semantic_matcher / reranker           语义工具
session_context_store                 会话上下文
slo_scheduler                         SLO 调度
task_context / task_dependency_dag    任务上下文/DAG
worker_abstraction / worker_profile   Worker 抽象
okr_framework                         OKR 框架
security_utils                        安全工具
core/ (3 文件)                        核心实现
```

### 2.3 剥离到 ext 包 (28 文件, ~6,000 行)

```
创建独立仓库: aetherforge-swarm-ext

ils_engine (860行) / ils_types / ils_plugins / ils_defaults
  → Intent Learning System，完善的独立子系统

perception_manager (534行) / perception_validation / vision_metabolizer
  → 多模态感知管线

hatcher_core (887行)
  → SharedBrain 孵化器，自我进化框架

execution_scheduler (852行) / nks_task_planner (800行)
  → 执行调度 + NKS 规划

possession_multi_session (357行)
  → 多会话管理

synapse_ollama / synapse_anthropic / synapse_github / synapse_hub
  → 旧连接器（参考用，已全部被 gateway 替代）

universal_worker (534行) / worker_dispatcher (730行) / worker_node
  → Worker 体系（mesh 有自己的 WorkerRegistry/TaskDispatcher）

mapping_engine (1行, stub) / mapping_worker_abstraction / mapping_worker_registry
  → 映射层（保留在 ext 以供参考）

result_aggregator / result_summarizer (各 1 行 stub)
associaton_engine / structural_merger
hypothesis_pipeline / rl_optimizer
mutation_validator / message_janitor
primordial_toolkit / refinement_daemon / burndown_engine
```

### 2.4 删除 (12 文件, ~20 行)

```
dispatch_compat (350行, 已被清理, 三副本之一)
semantic_index (5行)
task_decomposer (1行)
task_manager (1行)
capability_matcher (1行)
engine_worker_pool (1行)
mapping_worker_abstraction (4行, stub) → 移 ext
mapping_worker_registry (1行, stub) → 移 ext
```

### 2.5 迁移计划

```bash
# 1. 创建 ext 包
mkdir -p ../aetherforge-swarm-ext/src/swarm_ext
# 2. 复制模块
cp ils_*.py perception_*.py ... ../aetherforge-swarm-ext/src/swarm_ext/
# 3. 从主仓库删除
rm ils_*.py perception_*.py ...
# 4. 更新 __init__.py 移除对应导出
# 5. 运行测试确认 31/31 ✅
```

---

## 三、B: RouteScheduler

### 3.1 架构

```
用户请求 (model=gpt-4o, task="写代码")
  │
  ▼
RouteScheduler.select(request)
  │
  ├── Phase 1: Provider Filter
  │   QuotaEngine.is_available() → [deepseek, openai, ...]  
  │   过滤掉: 无Key/离线/配额<10%
  │
  ├── Phase 2: Provider Score  
  │   按策略评分 × 权重:
  │   ├── CostScore(provider_cost / max_cost_in_category)
  │   ├── QuotaScore(quota_pct / 100)  
  │   └── SpeedScore(1.0 - latency/10000)
  │   = 综合分 → [deepseek: 0.87, openai: 0.52, ...]
  │
  ├── Phase 3: Model Bind
  │   PricingRegistry.get_price(provider, model)
  │   确定最终模型 + 成本估算
  │
  └── Phase 4: Node Bind
      TopologyManager.bind(provider)
      选择最优计算节点
      → Route(provider=deepseek, model=deepseek-chat,
               node=deepseek-cloud, cost=$0.001/1K)
```

### 3.2 评分公式

```python
class RouteStrategies:
    BALANCED = {"cost": 0.35, "quota": 0.35, "speed": 0.30}
    COST_FIRST = {"cost": 0.70, "quota": 0.20, "speed": 0.10}
    SPEED_FIRST = {"cost": 0.10, "quota": 0.10, "speed": 0.80}
    QUOTA_FIRST = {"cost": 0.20, "quota": 0.60, "speed": 0.20}
```

### 3.3 新增文件

```
packages/gateway/src/llm_gateway/
├── route_scheduler.py       # RouteScheduler + Route + RouteStrategies

packages/gateway/tests/
└── test_route_scheduler.py  # 测试
```

### 3.4 CLI 增强

```bash
aetherforge gateway generate "你好"
  # 幕后自动选择最优 Provider

aetherforge gateway generate -m gpt-4o "你好"
  # 指定模型 → 自动选择有这个模型的 Provider 中评分最高的

aetherforge gateway list --quota
  # Provider × 配额 × 可用性一览

aetherforge gateway list --cost
  # 所有模型 + 定价
```

---

## 四、测试计划

```
清理后:
  Gateway tests: 13/13 ✅ (不变)
  Supplemental: 18/18 ✅ (不变)
  RouteScheduler tests: 5 NEW ← 🆕

RouteScheduler 测试用例:
  1. basic_select: 正常选择 → 返回 Route
  2. quota_exhausted: 所有 Provider 配额耗尽 → 返回 None
  3. strategy_switch: 不同策略输出不同结果
  4. model_bind: 指定模型 → 正确绑定
  5. fallback: 首选 Provider 失败 → 回退
```

---

## 五、交付标准

| 维度 | 标准 |
|:-----|:------|
| Swarm 清理 | 96 文件 → 42 保留 + 28 ext + 12 删除 |
| 测试 | 31+5 = 36 测试全部通过 |
| RouteScheduler | 三层路由可用，支持 4 种策略 |
| CLI | gateway generate 自动路由 |
| 代码质量 | 无 shell=True, 无静默吞异常 |
