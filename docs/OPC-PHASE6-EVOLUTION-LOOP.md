# OPC-P6: Self-Evolution Loop

> Date: 2026-06-11
> Source: OPC-ROADMAP.md §M6, opc-roadmap-omo-plan.md §Phase 6
> Status: governance baseline (载体建立, 不做业务实现)
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

## Prerequisites

- **opc_phase5_gate_f_not_yet_passed** (P5 scenarios 跑通, radar source 来自 F1)
- **opc_phase3_gate_d_not_yet_passed** (P3 业务 dispatch 路径)
- **opc_phase4_gate_e_not_yet_passed** (P4 LLM 路由)
- §19 跨仓债 E1-E4 收口
- `tech-radar` 场景 (P5-F1) 提供 radar source

## Sub-gates

| ID | Title | Status | Evidence Requirement |
|:---|:------|:-------|:---------------------|
| P6-G1 | evolution loop 闭环 | 📋 not_started | 至少 1 周完整闭环 (radar → gap → task → swarm → audit → retro), 6 阶段每个都有 evidence |
| P6-G2 | 周更升级报告 | 📋 not_started | 至少 2 周连续周报, 每份含 ≥3 candidates + score 排序 + source + timestamp + next-action + 人工审批栏 |
| P6-G3 | drift detector | 📋 not_started | 4 类漂移 (entry/doc/duplicate_facts/agora_bypass) 检测器, 跑 ≥1 周零漂移 OR 全漂移 + 自动 fix 路径 |
| P6-G4 | 闭环实证 | 📋 not_started | 至少 1 个 candidate 从 radar 跑到 retrospective 闭环实证, ≥3 仓 audit trail 完整 |

## Gate Status

- `opc_phase6_gate_g_not_yet_passed` (Gate G, 区别于 P7 Gate G — phase 隔离)

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
- ✅ P3 Gate D passed (现状: not_yet_passed — P6 业务实施 blocked, 但 P6 治理载体建立可进行)
- ✅ P4 Gate E passed (现状: not_yet_passed)
- ✅ P5 Gate F passed (现状: not_yet_passed) — P6 radar 来源依赖 F1
- ⏳ 至少 1 周 retrospective 模板

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
opc_phase6_subgate_g1_not_started
opc_phase6_subgate_g2_not_started
opc_phase6_subgate_g3_not_started
opc_phase6_subgate_g4_not_started
```

(待 G1-G4 全部 passed 后 emit `opc_phase6_gate_g_passed`)
