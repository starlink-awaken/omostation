---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# OPC-P3-T2 swarm 边界 (5 仓端到端流向)

> **状态**: ✅ design (2026-06-11)
> **作者**: 老王
> **定位**: OPC-P3 (Swarm spine) T2 — 5 仓 swarm 端到端流向
> **目的**: 给 Gate D "goal 拆 ≥ 3 worker task" 提供端到端 trace
> **链接**: OPC-P3-T1 SwarmTask 契约 / T2 memory-uri / §19 治理

---

## §1.0 一句话总结

**OPC-P3-T2 落地 5 边界 swarm 端到端: cockpit (入口) → agora (路由) → swarm-engine (DAG 调度) → runtime (worker 执行) → gbrain (output 写回) + omo (audit 治理), 1 个目标拆 3 个 worker task 走通。**

## §1.2 5 边界 swarm 流向 (端到端 trace)

```
[用户目标]
  │  1. collect (cockpit)
  ▼
[2. plan]  cockpit → agora MCP → planner agent
  │       生成 SwarmTask DAG (3+ worker tasks)
  ▼
[3. dispatch]  agora MCP → swarm-engine
  │           接收 SwarmTask 列表, 按 DAG dependencies 调度
  ▼
[4. execute]   swarm-engine → runtime (worker pool)
  │           heartbeat + retry + timeout + audit
  ▼
[5. collect_output]  runtime → swarm-engine
  │           worker 完成后 output 收集
  ▼
[6. write_back]  swarm-engine → gbrain
  │           output 写回 bos://memory/page/<slug>
  ▼
[7. audit]    swarm-engine → omo
              全过程 audit trail 写 bos://governance/task/<id>
```

## §1.3 真实 example: "我写了新章节" 目标

**用户目标**: 写一篇关于 OPC Memory spine 的深度文章

**DAG 拆解** (3+ worker task):

```
Task 1 (researcher): 搜集 OPC M1.5+M2 阶段所有 .omo 文档
  ↓ 完成后
Task 2 (planner): 根据 Task 1 收集的文档起草文章大纲
  ↓ 完成后
Task 3 (coder): 根据大纲写完整文章 (md)
  ↓ 完成后
Task 4 (reviewer): 审校文章, 输出 review comments
```

(4 个 worker task, 满足 "≥ 3" Gate D acceptance)

### §1.3.1 SwarmTask 1 (researcher)

```yaml
id: 9f3a2b1c-...
owner: swarm-engine:researcher-A
status: working
input:
  query: "OPC M1.5 M2 阶段所有 .omo 文档"
  boundary: governance
  since: 2026-06-01
  uri: bos://governance/knowledge/*
output: null
dependencies: []
timeout_seconds: 120
retry_policy: {max_retries: 2, backoff_strategy: exponential}
audit_uri: bos://governance/audit/swarm-researcher-9f3a2b1c.jsonl
source_map:
  source: bos://swarm/task/9f3a2b1c
  timestamp: 2026-06-11T15:00:00Z
  owner: swarm-engine:researcher-A
  freshness: {iso: PT0S, human: just now}
  boundary: governance
```

### §1.3.2 SwarmTask 2 (planner)

```yaml
id: 7d8e4f5a-...
owner: swarm-engine:planner-B
status: pending
input:
  upstream_output_uri: bos://governance/knowledge/...   # Task 1 output
  target: "OPC Memory spine 深度文章大纲"
output: null
dependencies: ["9f3a2b1c-..."]  # 等待 Task 1 完成
timeout_seconds: 60
retry_policy: {max_retries: 2, backoff_strategy: exponential}
audit_uri: bos://governance/audit/swarm-planner-7d8e4f5a.jsonl
```

### §1.3.3 SwarmTask 3 (coder)

```yaml
id: 3a6b8c2d-...
owner: swarm-engine:coder-C
status: pending
input:
  outline_uri: bos://swarm/output/.../planner-7d8e4f5a.json
  target: "OPC Memory spine 深度文章"
output: null
dependencies: ["7d8e4f5a-..."]  # 等待 Task 2 完成
timeout_seconds: 300
retry_policy: {max_retries: 3, backoff_strategy: exponential}
audit_uri: bos://governance/audit/swarm-coder-3a6b8c2d.jsonl
```

### §1.3.4 SwarmTask 4 (reviewer)

```yaml
id: 5e9f0a1b-...
owner: swarm-engine:reviewer-D
status: pending
input:
  draft_uri: bos://swarm/output/.../coder-3a6b8c2d.md
  target: "审校深度文章"
output: null
dependencies: ["3a6b8c2d-..."]  # 等待 Task 3 完成
timeout_seconds: 120
retry_policy: {max_retries: 2, backoff_strategy: exponential}
audit_uri: bos://governance/audit/swarm-reviewer-5e9f0a1b.jsonl
```

## §1.4 端到端 trace 流程

```
[t+0ms]    cockpit: 用户输入目标 "我写了新章节"
[t+5ms]    cockpit → agora MCP call: bos://swarm/plan (T1 契约)
[t+50ms]   agora → swarm-engine: planner 接收, 生成 4 个 SwarmTask
[t+60ms]   swarm-engine: 创建 4 个 SwarmTask, dependencies DAG 构建
[t+70ms]   swarm-engine: 启动 Task 1 (researcher)
[t+80ms]   runtime: worker pool 调度 Task 1 → worker-1 实际执行
[t+200ms]  worker-1: 扫 12 份 .omo 文档, 返回 4 份相关 (output 写 governance)
[t+220ms]  SwarmTask 1 status: completed
[t+230ms]  swarm-engine: 检测 Task 2 dependencies 满足, 启动 Task 2
[t+280ms]  worker-2: 根据 Task 1 output 起草大纲
[t+500ms]  SwarmTask 2 status: completed
[t+510ms]  swarm-engine: 启动 Task 3 (coder)
[t+600ms]  worker-3: 根据大纲写文章 (LLM 调用, ~3min)
[t+3500ms] SwarmTask 3 status: completed
[t+3510ms] swarm-engine: 启动 Task 4 (reviewer)
[t+3700ms] worker-4: 审校文章, 输出 review
[t+4200ms] SwarmTask 4 status: completed
[t+4210ms] swarm-engine: 全部 output 写回 gbrain page
[t+4250ms] SwarmTask 4 → bos://memory/page/opc-memory-spine-deep-dive.md
[t+4300ms] cockpit: 显示结果给用户 + 跨边界 URI 引用
[t+4350ms] omo: audit trail 全部 4 task 写完 → R0 健康度
```

**总延迟: ~4.3 秒** (4 个 task 串行 DAG)

## §1.5 5 仓职责分配

| 仓 | 职责 | SwarmTask 字段 |
|------|------|----------------|
| **cockpit** | 入口 + 输出显示 | 用户输入 + 跨边界结果展示 |
| **agora** | MCP 路由 + 认证 | SwarmTask RPC 入口 |
| **swarm-engine** | DAG 调度 + worker pool | dependencies 解析 + heartbeat |
| **runtime** | worker 实际执行 | input → output, retry + timeout |
| **gbrain** | 长期记忆 + 写回 | output → bos://memory/page/ |
| **.omo** | audit 治理 + 健康度 | audit_uri 收集 + 跨仓聚合 |

## §1.6 Gate D acceptance 命中

```
Gate: "A goal decomposes into at least three worker tasks."
  ✅ Example 拆 4 task (researcher/planner/coder/reviewer), ≥ 3

Gate: "Worker tasks have owner, status, input, output, and audit."
  ✅ SwarmTask 9 字段 (T1 契约) 覆盖全部 5 字段
  ✅ owner: swarm-engine:<role>-<id>
  ✅ status: 7 状态机 (T1)
  ✅ input: 任意 JSON
  ✅ output: 完成后填充
  ✅ audit: audit_uri → bos:// JSONL

Gate: "Failure creates retry or debt."
  ✅ retry_policy 字段 (T1)
  ✅ 失败 → RETRY_QUEUED 或 debt
```

## §1.7 实施分阶段

1. **T2.1** (本 Round): 设计文档 + DAG 流向 + 真实 example
2. **T2.2** (R57+): cockpit → agora 入口改造 (T1 SwarmTask RPC)
3. **T2.3** (R58+): swarm-engine DAG 调度 + heartbeat 实施
4. **T2.4** (R59+): gbrain 写回 + omo audit 实证

## §1.8 推进路径 (T2 → T3-T5)

| 任务 | 内容 | 工作量 |
|------|------|--------|
| **OPC-P3-T2** | swarm 边界 (本 doc) | ✅ done |
| **OPC-P3-T3** | agent 角色集 (6 角色) | 2 Round |
| **OPC-P3-T4** | worker dispatch (heartbeat + retry + failure debt + result 收集) | 2 Round |
| **OPC-P3-T5** | min-demo (1 goal 拆 ≥ 3 worker task 实证) | 1 Round |

**Gate D acceptance** (累计):
- ✅ goal 拆 ≥ 3 worker task (T2 example 4 task, 设计命中)
- ✅ worker tasks have owner/status/input/output/audit (T1 + T2)
- 🔄 failure creates retry or debt (T4 实施)
- 🔄 results can be written back to memory (T2.4 实施)

---

**OPC-P3-T2 设计完成。** 5 边界 swarm 端到端 + 4 task DAG example + 端到端 trace + Gate D 3 项 acceptance 设计命中。R57+ 推进 T3 agent 角色集 实施候选已列。
