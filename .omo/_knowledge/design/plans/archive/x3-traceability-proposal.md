---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P55 R1: Phase 1-13 历史执行计划归档, 当前阶段/状态以 .omo/state/system.yaml + .omo/goals/current.yaml 为准"
---
# X3 引用链追溯方案

> 基于 KOS consensus (L1/L2/L3) + PipelineTracer 的扩展方案
> 2026-05-28

---

## 目标

在现有共识系统上增加引用链追溯能力 —— 一条共识结论是如何形成的、依赖了哪些上游共识、可信度如何。

## 现状

```
KOS consensus: entity_id/agreed_by/agreement/confirmed_at/expires_at/status
PipelineTracer: pipelineId/stepIndex/tool/action/startedAt/endedAt/durationMs/status
```

两者目前无关联。一条共识记录无法追溯到生成它的执行链路。

## 方案选项

### 🟢 Option A: Simple (~1h)

**做法**: 在 consensus entry 中添加一个 `provenance_chain` 字段：

```python
@dataclass
class ConsensusEntry:
    entity_id: str
    agreed_by: list[str]
    agreement: str
    status: str
    confirmed_at: str
    expires_at: str
    provenance_chain: list[dict] = field(default_factory=list)
    # 格式: [{"pipeline_id": "...", "tool": "...", "step": 0}, ...]
```

当 KOS consensus 记录一条结论时，同时传入 PipelineTracer 的 pipeline_id。不解析、不验证——只引用。

**优点**: 最小改动，不破坏现有 API
**缺点**: 只是链接，不是真正的追溯

### 🟡 Option B: Medium (~2h)

**做法**:
- 在 consensus 中存储完整的 provenance_chain（PipelineTracer 记录的每个步骤）
- 提供一个 `trace(entity_id)` 工具：返回共识结论 + 完整执行链路
- 在 KOS MCP 中暴露 `trace_consensus(entity_id)` 工具

**优点**: 真正的端到端追溯
**缺点**: 存储量增大，consensus entry 可能包含大量执行数据

### 🔴 Option C: Full (~4h)

**做法**:
- 共识系统支持「引用树」——一条共识可以引用另一条共识
- `depends_on: list[str]` 字段
- 可视化引用链图谱
- PipelineTracer 步骤可以直接链接到共识条目

**优点**: 完整的价值堆栈追溯
**缺点**: 重量级，需要前端可视化

## 建议

**采用 Option A + 准备 Option B**:

1. 先在 consensus entry 中加 `provenance_chain` 字段（~30 分钟）
2. 在 consensus MCP 中加 `trace(entity_id)` 工具（~30 分钟）
3. 在 PipelineTracer 完成 pipeline 时，自动 POST 到 KOS consensus API（~1 小时）
4. Option B 的存储优化按需再做

### 影响

| 项目 | 影响 |
|------|------|
| KOS consensus | +1 dataclass field, +1 MCP tool |
| PipelineTracer | +1 POST callback |
| Pipeline:json | 无需修改 |
| 现有测试 | 无破坏性变更 |
