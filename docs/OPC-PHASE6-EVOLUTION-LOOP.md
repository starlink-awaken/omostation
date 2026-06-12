# OPC-P6: Self-Evolution Loop

> Date: 2026-06-11
> Source: OPC-ROADMAP.md §M6, opc-roadmap-omo-plan.md §Phase 6
> Status: in progress (实现/预演存在, Gate G 未通过)
> Tracking: `.omo/tasks/planned/OPC-P6-EVOLUTION-LOOP.yaml`

---

## Objective

P6 makes system improvement a **governed recurring workflow**, not ad-hoc.
The 6-stage loop:
1. **radar** — collect external signals (technical-radar scenario, P5-F1)
2. **gap** — compare to current OPC state, identify upgrade gaps
3. **task** — generate OMO planned task YAML
4. **swarm** — human approval → P3 worker dispatch
5. **audit** — 5 仓 audit trail (R50/B-1/B-2)
6. **retrospective** — weekly report + retrospective doc

**Key constraint** (from OPC-ROADMAP §6.2):
> "Self-evolution tasks may enter planned state only; human approval is required for active execution."

当前补充载体:
- `scripts/opc_p6_weekly_loop_cron.sh` / `scripts/opc_p6_self_evolve_cron.sh`
- `.omo/_control/evolution/loop/trace-index.json`
- `.omo/_control/evolution/approval-board/current.{json,md}`

## Readiness / Cadence

- **Readiness**: 已满足
  - G1 loop runner / trace-index 可用
  - G2 weekly 格式与审批栏可用
  - G3 drift detector / self-evolve / approval board 可用
  - G4 candidate trace / audit trail 可追
- **Cadence**: 未满足
  - G1-G4 都缺真实周级窗口

原则:
- Readiness 用于确认工程闭环已经搭起来
- Cadence 保留原始时间窗和真实周窗标准
- Gate G 不因 readiness passed 而自动 passed

## Prerequisites

- **opc_phase5_gate_f_passed** (P5 scenarios 跑通, radar source 来自 F1)
- **opc_phase3_gate_d_passed** (P3 业务 dispatch 路径)
- **opc_phase4_gate_e_passed** (P4 LLM 路由)
- §19 跨仓债 E1-E4 收口
- `tech-radar` 场景 (P5-F1) 提供 radar source

## Sub-gates

| ID | Title | Status | Evidence Requirement |
|:---|:------|:-------|:---------------------|
| P6-G1 | evolution loop 闭环 | 📋 not_yet_passed (有实现/预演, 无周级实证) | 至少 1 周完整闭环 (radar → gap → task → swarm → audit → retro), 6 阶段每个都有 evidence |
| P6-G2 | 周更升级报告 | 📋 not_yet_passed (格式齐, 但未满足真实连续周报) | 至少 2 周连续周报, 每份含 ≥3 candidates + score 排序 + source + timestamp + next-action + 人工审批栏 |
| P6-G3 | drift detector | 📋 not_yet_passed (检测器与 approval board 已落地, 无 ≥1 周观测证据) | 4 类漂移 (entry/doc/duplicate_facts/agora_bypass) 检测器, 跑 ≥1 周零漂移 OR 全漂移 + 自动 fix 路径 |
| P6-G4 | 闭环实证 | 📋 not_yet_passed (trace index 存在, 但依赖前序未通过) | 至少 1 个 candidate 从 radar 跑到 retrospective 闭环实证, ≥3 仓 audit trail 完整 |

## Gate Status

- `opc_phase6_gate_g_not_yet_passed` (Gate G, 区别于 P7 Gate G — phase 隔离)
- 2026-06-12 复验修正: G1-G4 均存在实现或预演证据, 但周级时间窗与人工审批红线未满足, Gate G 不得宣告 passed

## Red Lines

- ❌ "self-evolution task 自动 active (无 human approval)" (违反 OPC §6.2)
- ❌ "周报 candidate < 3" (Gate F acceptance 必备)
- ❌ "drift detector 0 漂移就 claim passed (没跑 ≥1 周不算)" (硬要求)
- ❌ "retrospective 缺失 source" (Gate F acceptance 必备)
- ❌ "retrospective 缺失 next-action" (Gate F acceptance 必备)
- ❌ "candidate 未变 OMO planned task 即算闭环" (闭环硬要求)

## Acceptance Package (G1-G4 全部 passed 所需)

1. G1: 1 周完整闭环 6 阶段 evidence
2. G2: 2 周连续周报, 每份 ≥3 candidates + 5 acceptance 字段
3. G3: drift detector 跑 ≥1 周, 0 漂移 OR 漂移 + fix
4. G4: 1 candidate 端到端追溯 (radar → retro), 5 仓 audit 完整
5. 红线 6 项全 hold

## Phase Open Condition (任务 4 readiness)

P6 **可开始** 当且仅当:
- ✅ P3 Gate D passed (现状满足)
- ✅ P4 Gate E passed (现状满足)
- ⏳ P5 Gate F passed (现状未满足) — P6 radar 来源依赖 F1
- ⏳ 1 周 retrospective 模板 + 真实周级实证 (现状未满足)

P6 **blocked**:
- P3/P4/P5 任何 gate 退到 not_started (不允许)
- 闭环任何阶段缺 evidence

P6 **final close condition** (Gate G passed):
- G1-G4 全部 runtime 实证
- 验收包 5 项全有 evidence
- 红线 6 项全 hold

## Forbidden Premature Claims

- ❌ "evolution loop 跑通" 在 G1 闭环 evidence 缺失时
- ❌ "周报格式正确" 在 G2 2 周连续周报缺失时
- ❌ "无 drift" 在 G3 跑 ≥1 周缺失时
- ❌ "闭环实证" 在 G4 candidate 端到端追溯缺失时

## Signal

```
opc_phase6_gate_g_not_yet_passed
opc_phase6_subgate_g1_not_yet_passed
opc_phase6_subgate_g2_not_yet_passed
opc_phase6_subgate_g3_not_yet_passed
opc_phase6_subgate_g4_not_yet_passed
```

(待 G1-G4 全部满足真实时间窗与审批红线后 emit `opc_phase6_gate_g_passed`)
