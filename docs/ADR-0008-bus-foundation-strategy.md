# ADR-0008: Bus Foundation Strategy — 先沉淀再拆

> Status: Accepted (R57)
> Date: 2026-06-12
> Deciders: agora team, omo team, metaos team, runtime team

## Context
agora 现在有 8 套机制并存 (EventBus, MessageBus, cron, SSE, WS, TaskSync, omo_daemon, croniter), 没有统一接口。考虑过直接拆独立仓 (bus-foundation), 但风险高。

## Decision
**先沉淀到 agora/bus/ 子包 (Phase A, R57-R58), 拆仓时机由 5 硬条件驱动 (Phase B, R63+)。**

## 5 硬条件 (Phase B 触发)
全部满足才允许拆仓:

1. **≥3 个项目生产环境调用 `from agora.bus`**
   - 测量: `grep -rln "from agora.bus" projects/{omo,metaos,runtime,kairon,cockpit}/src/ | wc -l` ≥ 3
   - 频率: 月度

2. **bus/ 子包有 ≥180 天 git history**
   - 测量: `git log --since="180 days ago" -- projects/agora/src/agora/bus/ | wc -l` ≥ 1
   - 频率: 持续

3. **agora CLAUDE.md 写明 bus owner**
   - 测量: `grep -q "bus.*owner" projects/agora/CLAUDE.md`
   - 频率: 一次性

4. **≥1 个 eCOS 之外的项目使用**
   - 测量: GitHub issue / PR 数量 ≥ 1, by non-contributor
   - 频率: 持续
   - **R63 amendment**: 包含 HTTP / MCP 消费者 (hermes-console TS HTTP adapter 这种)
     — `Condition 1b: ≥1 HTTP / MCP consumer` 补充检查 (script 算 Python `from agora.bus`,
     实际 TS adapter 走 HTTP/MCP 不算, 但仍证明 API stability)

5. **bus 改动频率 ≥ agora 主体 50%**
   - 测量: `git log --since="6 months ago" -- projects/agora/src/agora/bus/ | wc -l` ≥ `git log --since="6 months ago" -- projects/agora/src/agora/ | wc -l` * 0.5
   - 频率: 月度

## Consequences
**正**: 6 个月沉淀期 = 演化自由度比直接拆高 10x
**负**: 现在看着冗余, 团队可能质疑"为什么不直接拆"
**退路**: R62 末评估不满足 → 继续沉淀, R63 重评

## References
- `.omo/_delivery/async-event-cron-architecture-2026-06-12.md`
- `docs/bus-unification-plan.md`
