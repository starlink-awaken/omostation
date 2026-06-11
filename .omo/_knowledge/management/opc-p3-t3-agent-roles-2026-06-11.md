# OPC-P3-T3 agent 角色集 (6 角色)

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P3 (Swarm spine) T3 — 6 角色契约
> **目的**: 给 swarm-engine / cockpit / llm-gateway 提供统一 agent 角色定义
> **链接**: OPC-P3-T1 SwarmTask / T2 swarm 边界 / llm-gateway / BaseWorkerProfile

---

## §1.0 一句话总结

**OPC-P3-T3 落地 6 角色契约: researcher/planner/coder/reviewer/operator/critic, 每角色定义 (capability 集 / 工具集 / 模型路由 / 输入输出契约 / 心跳), 与 swarm-engine BaseWorkerProfile 兼容, Gate D acceptance "6 角色" 命中。**

## §1.1 6 角色总览

| # | 角色 | 单一职责 | 主要模型 | 工具集 |
|---|------|---------|----------|--------|
| 1 | **researcher** | 信息搜集 + 跨边界 recall | haiku-4-5 (廉价) | search, query, get_page, get_knowledge, get_asset |
| 2 | **planner** | 任务拆解 + DAG 设计 | sonnet-4-6 (中等) | swarm/plan, get_task_history, list_boundary_routes |
| 3 | **coder** | 内容生成 + 代码实现 | sonnet-4-6 (中等) | search, query, put_page (write), shell_exec |
| 4 | **reviewer** | 审校 + 质量门 | sonnet-4-6 (中等) | search, get_page, get_boundary_metrics |
| 5 | **operator** | 任务执行 + 资源调度 | haiku-4-5 (廉价) | shell_exec, job_submit, budget_track |
| 6 | **critic** | 反方观点 + 风险识别 | opus-4-7 (高质量) | search, get_debt_registry, get_phase_history |

## §1.2 每角色详细契约

### §1.2.1 researcher (信息搜集)

```yaml
role_id: researcher
archetype: knowledge-gather
capabilities:
  - cross_boundary_search
  - evidence_extraction
  - source_attribution
tools:
  - bos://memory/search (T2 URI)
  - bos://governance/knowledge/* (recall)
  - bos://ontology/concept/{slug} (KOS 概念查询)
input_schema: 
  query: string
  boundary: enum[memory|ontology|work|asset|governance]
  since: ISO8601
output_schema:
  results: list[SourceMap]  # 100% attribution (T4)
  coverage: float  # 边界命中率 (T5)
heartbeat_interval: 5s
max_concurrency: 5
cost_per_task: ~$0.01 (haiku)
```

### §1.2.2 planner (任务拆解)

```yaml
role_id: planner
archetype: task-decomposer
capabilities:
  - goal_decomposition
  - dag_design
  - dependency_analysis
tools:
  - swarm/plan (T1 RPC)
  - get_task_history
  - list_boundary_routes (T2 路由)
input_schema:
  goal: string
  constraint: object
output_schema:
  swarm_tasks: list[SwarmTask]  # ≥ 3 tasks (Gate D)
  dag: object  # dependencies 图
heartbeat_interval: 3s
max_concurrency: 2
cost_per_task: ~$0.05 (sonnet)
```

### §1.2.3 coder (内容生成)

```yaml
role_id: coder
archetype: content-generator
capabilities:
  - article_writing
  - code_generation
  - document_creation
tools:
  - search (T2 URI)
  - put_page (T1 写权限)
  - shell_exec (代码执行)
input_schema:
  task: SwarmTask
  outline_uri: bos://...
output_schema:
  output_uri: bos://memory/page/<slug>
  metrics: {lines, tokens, time}
heartbeat_interval: 10s
max_concurrency: 3
cost_per_task: ~$0.10 (sonnet)
```

### §1.2.4 reviewer (审校)

```yaml
role_id: reviewer
archetype: quality-gate
capabilities:
  - content_review
  - quality_scoring
  - source_verification
tools:
  - search
  - get_page
  - get_boundary_metrics
input_schema:
  draft_uri: bos://memory/page/<slug>
  rubric: object
output_schema:
  review_comments: list[Comment]
  quality_score: float  # 0-1
  approved: bool
heartbeat_interval: 5s
max_concurrency: 3
cost_per_task: ~$0.08 (sonnet)
```

### §1.2.5 operator (任务执行)

```yaml
role_id: operator
archetype: resource-coordinator
capabilities:
  - shell_execution
  - job_scheduling
  - budget_tracking
tools:
  - shell_exec
  - job_submit
  - budget_track (T1 跨仓)
input_schema:
  command: string
  env: object
output_schema:
  exit_code: int
  stdout: string
  stderr: string
  cost_usd: float
heartbeat_interval: 3s
max_concurrency: 10
cost_per_task: ~$0.01 (haiku + 资源费)
```

### §1.2.6 critic (反方观点)

```yaml
role_id: critic
archetype: risk-spotter
capabilities:
  - risk_identification
  - contrarian_analysis
  - debt_detection
tools:
  - search
  - get_debt_registry
  - get_phase_history
input_schema:
  target_uri: bos://...
  context: object
output_schema:
  risks: list[Risk]
  confidence: float
  counter_argument: string
heartbeat_interval: 30s
max_concurrency: 1
cost_per_task: ~$0.20 (opus, 高质量)
```

## §1.3 角色 ↔ BaseWorkerProfile 兼容

| OPC 角色 | BaseWorkerProfile.worker_id | persona |
|----------|------------------------------|---------|
| researcher | researcher-{A,B,C} | Knowledge Gatherer |
| planner | planner-{A,B} | Task Decomposer |
| coder | coder-{A,B,C} | Content Generator |
| reviewer | reviewer-{A,B,C} | Quality Gate |
| operator | operator-{A..J} | Resource Coordinator |
| critic | critic-A | Risk Spotter |

## §1.4 角色 ↔ 模型路由 (llm-gateway)

| 角色 | 首选模型 | 降级链 | cost/task |
|------|---------|--------|-----------|
| researcher | anthropic:claude-haiku-4-5 | (固定) | $0.01 |
| planner | anthropic:claude-sonnet-4-6 | opus-4-7 (复杂) | $0.05 |
| coder | anthropic:claude-sonnet-4-6 | opus-4-7 (大改) | $0.10 |
| reviewer | anthropic:claude-sonnet-4-6 | opus-4-7 (审核严) | $0.08 |
| operator | (无 LLM, 仅工具) | - | $0.00 |
| critic | anthropic:claude-opus-4-7 | (固定) | $0.20 |

**总成本 estimate** (1 goal 拆 4 task): $0.01 + $0.05 + $0.10 + $0.08 + $0 + $0.20 = $0.44/goal

## §1.5 真实 example: 角色组合 (T2 example 续)

```
Task 1: researcher  收集 .omo 文档  ($0.01)
Task 2: planner     起草大纲      ($0.05)
Task 3: coder       写完整文章    ($0.10)
Task 4: reviewer    审校          ($0.08)
  + 旁路 critic    反方观点      ($0.20)
```

**总: 5 个角色, 4 个 task + 1 个旁路 critic, $0.44/goal**

## §1.6 Gate D acceptance 命中

```
Gate: "Agent role set: researcher, planner, coder, reviewer, operator, critic."
  ✅ 6 角色全部定义 (本 doc)
  ✅ 每角色 capability/tools/model 明确
  ✅ 角色 ↔ BaseWorkerProfile 兼容
  ✅ 角色 ↔ llm-gateway 模型路由
```

## §1.7 实施分阶段

1. **T3.1** (本 Round): 设计文档 + 6 角色契约
2. **T3.2** (R57+): swarm-engine/worker_profile.py 落地 6 角色 profile
3. **T3.3** (R58+): llm-gateway 角色路由表 (model_per_role)
4. **T3.4** (R59+): cockpit role picker 实施 (用户选目标 + 角色自动分配)

## §1.8 推进路径 (T3 → T4-T5)

| 任务 | 内容 | 工作量 |
|------|------|--------|
| **OPC-P3-T3** | 6 角色契约 (本 doc) | ✅ done |
| **OPC-P3-T4** | worker dispatch (heartbeat + retry + failure debt + result 收集) | 2 Round |
| **OPC-P3-T5** | min-demo (1 goal 拆 ≥ 3 worker task 实证) | 1 Round |

**Gate D acceptance** (累计):
- ✅ goal 拆 ≥ 3 worker task (T2 example 4 task, 设计命中)
- ✅ worker tasks have owner/status/input/output/audit (T1 + T2)
- 🔄 failure creates retry or debt (T4 实施)
- 🔄 results can be written back to memory (T1.4 + T2.4 实施)
- ✅ **agent role set (本 T3, 设计命中)**

---

**OPC-P3-T3 设计完成。** 6 角色契约 + capability/tools/model 详细 + 角色 ↔ profile 兼容 + 角色 ↔ model 路由 + cost estimate $0.44/goal。R57+ 推进 T4 worker dispatch 实施候选已列。
