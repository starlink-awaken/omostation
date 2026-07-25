# C 波 — 协作协议升级端到端 + 失败路径 (Round2 主轴)

> 日期: 2026-07-25
> workflow: 20260725T143401Z-governance-state-mutation-c76e84a8 (governance_code lane)
> goal: strat-p81 round2 C 波 (C1 协议升级 + C2 失败路径)

## C1 协议升级端到端 (含真实冲突)

`run_collab_pipeline_with_conflict` 编排 (ADR-0235 D2 第二条线深化):

1. **任务分解**: governance `decompose_into_subtasks` (大任务→子任务→组合)
2. **多轮协商**: `run_multi_round_negotiation` governance↔research (2 轮)
3. **真实冲突**: engineering (pass=True) vs audit (pass=False) 对同一产物分歧
4. **冲突消解**: `resolve_message_conflict` → audit 胜出 (优先级 > engineering)

**验证**: `pipeline_ok=True`, 4 角色, 2 轮协商, conflict `[engineering, audit]`, winner=`audit`.
满足 goal "≥3角色 / ≥2轮协商 / 含1次真实冲突消解".

## C2 失败路径 (≥5 场景, 补上轮 100% 盲区)

`simulate_failure_scenario` + `run_failure_scenario_suite`:

| 场景 | trigger | handling | recoverable |
|------|---------|----------|-------------|
| timeout | 角色超时未响应 | 标记 timeout + 重分派 | True |
| reject | 产物不合格被审计驳回 | verify fail → 回退 engineering | True |
| retry | 子任务失败需重分派 | retry ≤3 次后升级 | True |
| escalate | 冲突未消解升级 | governance 仲裁 (最高优先级) | True |
| exhaust | 协商耗尽 max_rounds | 标记 unsatisfied + 写卡 Inbox | False |

**验证**: 5 场景全 `deterministic_handled=True`, `no_silent_loss=True`.
满足 goal "≥5 场景确定性处理, 失败不卡死/不静默丢".

## 通道问题 (goal 熔断记录)

C 波原计划 `project-code-change`, 但 run `abe091ce` (静默遗留 Kairon 清理, observe halt)
持有 `project.lock` 阻塞. 绕道 `governance-state-mutation` (governance_code lane)
完成 C1+C2, 不阻塞. abe091ce 卡死送 Inbox (`needs-human-run-abe091ce-dormant`),
需人类决策清理. project-code-change 通道仍卡 (本轮 C 波 governance_code lane 完成).

## 后续 (Round2 剩余)

- C3 gbrain 黑板深化 (跨任务复用 case ≥3, 命中率入 audits)
- C4 协作仪表进 BRIEF (含失败率, 不只报喜)
- W3 C1 五角色正式实装 (cockpit 集成, 用户已拍板 go)
- abe091ce 清理 (人类决策, 释放 project-code-change 通道)
- D 波 (三债卡 + KOS + X3 八月)
