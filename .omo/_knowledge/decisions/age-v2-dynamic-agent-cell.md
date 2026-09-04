---
id: ADR-0401
status: ACCEPTED
lifecycle: spec
owner: architecture-governance
last_updated: 2026-08-24
---

# ADR-0401 — AGE-v2 动态 Agent Cell 架构

- **Status**: ACCEPTED
- **Date**: 2026-08-24
- **Owner**: architecture-governance

## Context

当前 Agent 执行模型是**被动的事件路由器 + 人工审批的执行器**:
- Resident Agent: cron 轮询 (2min), 事件路由, `--yes` 人工审批门
- Agent Workflow: 人工驱动 (start → claim → verify → closeout)
- 执行路径: 事件 → 路由 → 审批 → 执行 (Pi/Multica)

**核心缺口**: 缺少角色间的**协调层** — Planner/Executor/Verifier 没有结构化分工, 没有角色间 handoff 合约, 没有独立 Governor。

## Decision

采用 **AGE-v2 动态 Agent Cell** 架构, 包含 5 个核心角色:

| 角色 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **Planner** | 意图解析 → 任务分解 | 人类意图 / 信号 | ExecutionPlan |
| **Executor** | 按计划执行 → 工具调用 | ExecutionPlan | ExecutionResult |
| **Verifier** | 结果验证 → 质量评估 | ExecutionResult | Verdict |
| **Coordinator** | 角色调度 → Handoff 仲裁 | Episode | CellState |
| **Governor** | 风险分级 → 审批决策 | ActionRequest | Decision |

### 关键设计

1. **结构化 Handoff**: 角色间通过 typed contract 传递上下文和产物
2. **风险分级治理**: R0 (自动) / R1 (自动+审计) / R2 (人工异步) / R3 (人工同步)
3. **PDP/PEP 强制**: Policy Decision Point 评估 + Policy Enforcement Point 阻断
4. **记忆整合管道**: candidate → conflict → consolidate → forget
5. **跨系统可观测**: Resident ↔ Agora 事件桥接

## Implementation

### 文件结构

```
projects/omo/src/omo/resident/
├── cell.py              # Cell Coordinator
├── governor.py          # 风险分级治理
├── planner.py           # 意图解析 + 任务分解
├── executor.py          # 计划执行
├── verifier.py          # 结果验证
├── pdp_pep.py           # 策略决策/执行
├── memory_pipeline.py   # 记忆整合
├── replay.py            # 回放/影子/Eval
├── cell_cli.py          # CLI 入口
└── daemon.py            # 集成 Governor (修改)
```

### BOS URI 注册

```
bos://agent-cell/plan              # Planner
bos://agent-cell/execute           # Executor
bos://agent-cell/verify            # Verifier
bos://agent-cell/govern            # Governor
bos://agent-cell/pdp/evaluate      # PDP
bos://agent-cell/pep/enforce       # PEP
bos://agent-cell/memory/process    # Memory Pipeline
bos://agent-cell/memory/consolidate
bos://agent-cell/replay/run        # Replay
bos://agent-cell/replay/shadow     # Shadow
bos://agent-cell/replay/eval       # Eval
```

### Agora MCP 工具

```python
cell_plan(intent) → plan
cell_execute(plan) → result
cell_verify(result) → verdict
cell_govern(action) → decision
cell_pdp_evaluate(action) → decision
cell_pep_enforce(action) → enforcement
cell_memory_process(episode) → candidates
cell_memory_consolidate() → memories
cell_replay(episode) → result
cell_shadow(intent) → result
cell_eval(n) → metrics
```

### CLI 入口

```bash
omo cell plan "意图"
omo cell execute '<plan_json>'
omo cell verify '<result_json>'
omo cell govern <action>
omo cell pdp <action>
omo cell pep <action>
omo cell memory process '<episode>'
omo cell memory consolidate
omo cell replay shadow "意图"
omo cell replay eval [N]
```

## Consequences

### Positive

- **角色分离**: Planner/Executor/Verifier 独立演化
- **安全治理**: PDP/PEP 真正阻断危险操作
- **可观测**: 跨系统事件桥接, 全链路追踪
- **可发现**: BOS URI + MCP 工具, 其他 agent 可自动发现

### Negative

- **复杂度增加**: 5 个角色 + 协调层
- **延迟增加**: Handoff 开销
- **维护成本**: 需要测试覆盖

## Validation

- [x] 单元测试: 16/16 通过
- [x] BOS URI 注册: 11 个 URI
- [x] MCP 工具: 12 个工具
- [x] CLI 入口: `omo cell` 命令
- [ ] 集成测试: 待补充
- [ ] 性能测试: 待补充

## References

- `docs/architecture/digital-twin-blueprint-v1.md` — W5-01/W5-02
- `docs/architecture/blueprint-multi-agent-execution-control-v1.md`
- `docs/operations/lifeos-user-guide.md`
