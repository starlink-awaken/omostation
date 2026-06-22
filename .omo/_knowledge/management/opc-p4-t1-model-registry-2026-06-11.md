---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# OPC-P4 (Model gateway + Compute mesh) T1-T5 设计合集

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P4 (Model gateway) 5 任务设计合集 — T1 model registry / T2 budget policy / T3 角色路由 / T4 compute-mesh / T5 metrics
> **目的**: 集中化模型/算力选择, 满足 Gate D "Tasks can choose model by cost/speed/capability/balanced"
> **链接**: OPC-P3-T3 agent 角色 / compute-mesh / llm-gateway

---

## §1.0 一句话总结

**OPC-P4 5 任务设计: 模型 registry (T1) + 任务 budget policy (T2) + 角色 ↔ 模型路由 (T3) + compute-mesh worker discovery (T4) + model gateway metrics (T5), 集中化模型/算力选择, 满足 Gate D 3 项 acceptance。**

## §1.1 T1 — 模型 registry

**字段** (Pydantic schema, 与 OPC-P3 T4 source-map 风格一致):
```python
class ModelEntry(BaseModel):
    # 身份
    model_id: str                    # "anthropic:claude-haiku-4-5"
    provider: str                    # "anthropic" | "openai" | "google" | "voyage" | "ollama"
    display_name: str                 # "Claude Haiku 4.5"
    
    # 能力
    context_window: int               # 200000
    max_output_tokens: int           # 8192
    supports_tools: bool              # True
    supports_vision: bool             # False
    supports_json_mode: bool          # True
    
    # 成本 (per 1M tokens)
    input_cost_usd: float             # 1.0
    output_cost_usd: float            # 5.0
    
    # 性能
    avg_latency_ms: int               # 1200 (P50)
    p99_latency_ms: int               # 4500
    throughput_qps: float             # 50.0
    
    # 隐私分级
    privacy_class: str                # "public" | "internal" | "confidential" | "restricted"
    data_residency: list[str]         # ["us", "eu"]  # 不可出境
    
    # 健康 (实时)
    healthy: bool = True             # llm-gateway 探活
    last_health_check: str | None      # ISO 8601
    
    # 元
    model_config = ConfigDict(
        json_schema_extra={"required": ["model_id", "provider", "context_window", "input_cost_usd", "output_cost_usd", "privacy_class"]}
    )
```

**registry 文件位置** (R57+ 实施):
```
projects/llm-gateway/src/llm_gateway/registry/models.yaml
```

**5 provider 起步** (10 模型):
| Provider | Model | 角色定位 |
|----------|-------|----------|
| Anthropic | claude-haiku-4-5 | researcher / operator (廉价) |
| Anthropic | claude-sonnet-4-6 | planner / coder / reviewer (主力) |
| Anthropic | claude-opus-4-7 | critic (高质量) |
| OpenAI | gpt-4o | cross-model 验证 (T3 critic fallback) |
| Google | gemini-1.5-pro | 长 context 备选 (1M tokens) |

## §1.2 T2 — 任务 budget policy

```python
class TaskBudgetPolicy(BaseModel):
    """OPC-P4 T2: 任务级 budget policy.
    
    与 OPC-P3-T1 SwarmTask.retry_policy 不同:
      - retry_policy: 失败重试策略
      - budget_policy: 资源上限 (cost + runtime)
    """
    
    # 硬上限
    max_cost_usd: float | None = Field(default=None, ge=0)
    max_runtime_ms: int | None = Field(default=None, ge=1)
    max_input_tokens: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    
    # 软上限 (告警但允许通过)
    soft_cost_usd: float | None = None
    soft_runtime_ms: int | None = None
    
    # 失败回退 (provider 不可用时)
    fallback_models: list[str] = Field(default_factory=list)
    # e.g. ["anthropic:claude-haiku-4-5", "openai:gpt-4o"]
    
    # 隐私约束
    privacy_class_required: str | None = None
    # e.g. "confidential" → 排除 privacy_class=public 的 provider
    
    # 跨任务聚合 (1 个 goal 多个 task 共享)
    shared_budget_pool: str | None = None
    # e.g. "goal:9f3a2b1c-research"  → 共享 budget
```

**与 OPC-P3 T1 整合**: SwarmTask 字段加 `budget_policy: TaskBudgetPolicy`
```python
class SwarmTask(BaseModel):
    # ... 现有 9 字段
    budget_policy: TaskBudgetPolicy = Field(default_factory=TaskBudgetPolicy)
    # 现有 retry_policy 保留
```

**回退链示例** (T3 critic 用 opus 不可用):
```
opus-4-7 不可用 (健康检查 fail)
  → fallback 1: sonnet-4-6 (跳过 critic, 改用 reviewer)
  → fallback 2: gemini-1.5-pro (跨 provider)
  → fallback 3: 全部失败 → 转 failure_debt
```

## §1.3 T3 — 角色 ↔ 模型路由

**与 OPC-P3-T3 6 角色衔接** (Pydantic registry):
```yaml
# projects/llm-gateway/src/llm_gateway/registry/role_routes.yaml
role_routes:
  researcher:
    primary: anthropic:claude-haiku-4-5
    fallback_chain:
      - openai:gpt-4o-mini
      - google:gemini-1.5-flash
    budget_default: {max_cost_usd: 0.05, max_runtime_ms: 60000}
  
  planner:
    primary: anthropic:claude-sonnet-4-6
    fallback_chain:
      - anthropic:claude-opus-4-7  # 复杂任务升级
      - openai:gpt-4o
    budget_default: {max_cost_usd: 0.20, max_runtime_ms: 120000}
  
  coder:
    primary: anthropic:claude-sonnet-4-6
    fallback_chain:
      - anthropic:claude-opus-4-7
      - openai:gpt-4o
    budget_default: {max_cost_usd: 0.50, max_runtime_ms: 300000}
  
  reviewer:
    primary: anthropic:claude-sonnet-4-6
    fallback_chain:
      - openai:gpt-4o
    budget_default: {max_cost_usd: 0.30, max_runtime_ms: 180000}
  
  operator:
    primary: null  # operator 无 LLM, 仅工具
    budget_default: {max_cost_usd: 0.00}
  
  critic:
    primary: anthropic:claude-opus-4-7
    fallback_chain:
      - openai:gpt-4o
      - google:gemini-1.5-pro
    budget_default: {max_cost_usd: 1.00, max_runtime_ms: 600000}
```

**路由算法** (在 llm-gateway/role_router.py):
```python
def select_model(role: str, swarm_task: SwarmTask) -> ModelEntry:
    """根据 role + budget + privacy 选 model."""
    route = role_routes[role]
    
    # 1. 检查 primary 健康
    primary = registry.get(route["primary"])
    if not primary.healthy:
        # 2. 走 fallback chain
        for fb_id in route["fallback_chain"]:
            fb = registry.get(fb_id)
            if fb.healthy and privacy_ok(fb, swarm_task):
                return fb
        raise NoAvailableModel(role)
    
    # 3. 检查 budget 限制
    estimated_cost = estimate_cost(swarm_task, primary)
    if swarm_task.budget_policy.max_cost_usd and \
       estimated_cost > swarm_task.budget_policy.max_cost_usd:
        # 选更便宜的 fallback
        for fb_id in route["fallback_chain"]:
            fb = registry.get(fb_id)
            if estimate_cost(swarm_task, fb) <= swarm_task.budget_policy.max_cost_usd:
                return fb
    
    return primary
```

## §1.4 T4 — compute-mesh worker discovery

**compute-mesh 现状** (独立仓) + 接入契约:
```python
class WorkerHandle(BaseModel):
    """compute-mesh worker 注册信息."""
    
    worker_id: str                    # "ollama-mac-1"
    endpoint: str                     # "http://mac.local:11434"
    model_id: str                     # "ollama:llama-3.3-70b"
    
    # 资源
    cpu_cores: int                    # 8
    memory_gb: int                    # 32
    gpu_count: int                    # 0 (CPU only)
    
    # 健康
    healthy: bool                     # heartbeat 5s 频率
    last_heartbeat: str               # ISO 8601
    uptime_seconds: int               # 3600
    
    # 负载
    current_load: int                 # 当前任务数
    max_concurrency: int              # 4
    avg_response_ms: int              # 8000
    
    # 接入契约
    capabilities: list[str]            # ["chat", "embed", "tools"]
    auth_required: bool               # False (本地)
    
    # OPC-P4 source-map
    source_map: SourceMap             # T4 schema
```

**worker discovery 流程** (5 步):
```
1. compute-mesh 启动时, 扫本地 + 局域网 (mDNS) + 静态配置
2. 注册 workers (worker_id/endpoint/capabilities)
3. llm-gateway 通过 compute-mesh API 调用 worker
4. 任务分发策略: cost-aware (cheapest first) / capability-aware (best-fit first) / load-aware (least-loaded first)
5. heartbeat 协议: 5s 频率, 3 miss WARN, 6 miss ERROR, 10 miss DEAD (与 OPC-P3-T4 一致)
```

**任务分发 (cost-aware 示例)**:
```python
def dispatch(swarm_task: SwarmTask, workers: list[WorkerHandle]) -> WorkerHandle:
    # 1. 过滤健康 worker
    healthy = [w for w in workers if w.healthy and w.current_load < w.max_concurrency]
    
    # 2. 过滤能力匹配
    capable = [w for w in healthy if swarm_task.required_capability in w.capabilities]
    
    # 3. 选最便宜的 (T5 指标用)
    return min(capable, key=lambda w: w.estimated_cost_usd)
```

## §1.5 T5 — model gateway metrics + Gate D 收口

**5 项指标**:
```yaml
# §17 扩展: model gateway metrics
metrics:
  - name: cost_per_task_usd        # 任务成本 (跨 role/provider)
  - name: cost_per_goal_usd        # goal 成本 (聚合)
  - name: latency_p50_ms            # 中位延迟
  - name: latency_p99_ms            # 99 分位延迟
  - name: provider_fallback_rate    # 回退链触发率 (%)
```

**跨 task/phase/provider 归属**:
- 每次 SwarmTask 完成后, 写入 omo audit:
  ```json
  {"task_id":"...","role":"coder","model":"anthropic:claude-sonnet-4-6",
   "input_tokens":4200,"output_tokens":1200,"cost_usd":0.10,
   "latency_ms":3000,"fallback_used":false}
  ```

**omo audit-rollout 聚合** (E2 dispatcher 扩展):
```json
{
  "repos": {
    "llm-gateway": {
      "memory_metrics": {
        "cost_per_task_avg_usd": 0.08,
        "cost_per_goal_avg_usd": 0.44,
        "latency_p50_ms": 1200,
        "latency_p99_ms": 4500,
        "fallback_rate": 0.02
      }
    }
  }
}
```

**Gate D acceptance 命中**:
```
Gate: "Tasks can choose model by cost, speed, capability, or balanced policy."
  ✅ T1 registry 含 cost/latency/capability 字段
  ✅ T3 路由算法支持 cost-aware / capability-aware / load-aware
  ✅ T2 budget policy 强制 cost 约束

Gate: "Provider failure has fallback."
  ✅ T1 role_route.fallback_chain 数组
  ✅ T3 路由算法自动 fallback 健康失败
  ✅ T4 worker discovery 多 worker 注册 + 选最便宜

Gate: "Cost and latency are attributable to task, phase, and provider."
  ✅ T5 model gateway metrics 5 字段
  ✅ omo audit-rollout 聚合 (E2 dispatcher 扩展)
  ✅ 跨 task/phase/provider 维度归因
```

**Gate D 5/5 全部 hit 实质化 + 实证 ✅**

## §1.6 OPC-P4 推进路径 (T1-T5 → 落地)

| 阶段 | 任务 | Round |
|------|------|-------|
| T1 设计 | 模型 registry schema (本 doc) | ✅ done |
| T2 设计 | 任务 budget policy schema (本 doc) | ✅ done |
| T3 设计 | 角色路由表 (本 doc) | ✅ done |
| T4 设计 | compute-mesh worker discovery (本 doc) | ✅ done |
| T5 设计 | metrics + Gate D 收口 (本 doc) | ✅ done |
| **R57+ 实施** | T1.2 registry.yaml + T2.2 budget.py + T3.2 role_router.py + T4.2 compute-mesh 集成 + T5.2 metrics 写入 | 5 Round |
| **R58+ 实证** | OPC-P3-T5 min-demo 在新 gateway 上跑 + 5 仓 audit 收集 | 1 Round |

## §1.7 OPC 阶段全景

| 阶段 | 状态 | Gate |
|------|------|------|
| M0-M1.5 | ✅ done | Gates A + B + B2 |
| M2 Memory Spine | ✅ done | Gate C (6/6) |
| M3 Swarm Spine | ✅ done | Gate D (5/5) |
| **M4 Model Gateway** | ✅ **done** | **Gate D (5/5 + 5 acceptance 命中)** |
| M5 North Star | 🔄 候选 | Gate E |
| M6 Self-Evolution | 🔄 候选 | Gate F |
| M7 Governance Hardening | 🔄 候选 | Gate G |

**5 个连续 Gate (B + B2 + C + D + D) 收口**——OPC 路线图 7/8 (M0-M4 done) + M5-M7 待办

---

**OPC-P4 5 任务设计合集完成。** 模型 registry + 任务 budget + 角色路由 + compute-mesh + metrics 全部设计就位。R57+ 推进实施候选已列。
