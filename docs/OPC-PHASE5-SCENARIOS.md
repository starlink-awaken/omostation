# OPC-P5: North Star Scenarios

> Date: 2026-06-11
> Source: OPC-ROADMAP.md §M5, opc-roadmap-omo-plan.md §Phase 5
> Status: partial closeout (F2/F3/F4 已落地, Gate F 仍待 F1 时间窗)
> Tracking: `.omo/tasks/planned/OPC-P5-SCENARIOS.yaml`

---

## Objective

P5 proves OPC value through **3 repeatable real-user product scenarios**:
1. **technical-radar** — collect AI/agent/knowledge-engineering updates, score relevance, emit upgrade tasks
2. **work-assistant** — generate sourced structured drafts for real work questions
3. **family-health** — summarize family medical records, produce next-action items

Outputs include **source, timestamp, next-action** (per Gate F acceptance).

## Prerequisites

- **opc_phase3_gate_d_passed** (P3 worker dispatch path 已收口)
- **opc_phase4_gate_e_passed** (P4 model gateway / compute policy 已收口)
- `cockpit` 仓 CLI entry 完整
- P2 §5 boundaries 跑通 (recall-flow 端到端)
- §19 跨仓债 E1-E4 收口

## Sub-gates

| ID | Title | Status | Evidence Requirement |
|:---|:------|:-------|:---------------------|
| P5-F1 | technical-radar scenario | 📋 not_yet_passed (待 ≥2 周真实 cron 跑通) | 至少 2 周连续 cron 跑通, 每次输出 ≥3 升级 candidates + 源声明 + next-action |
| P5-F2 | work-assistant scenario | ✅ passed (真实 query + 5 sources + audit trail) | 至少 1 个真实工作 query 跑通, 输出结构化草稿含 source/timestamp/next-action |
| P5-F3 | family-health scenario | ✅ passed (3 级 next-action + confidential local store) | 至少 1 个真实家庭健康 query 跑通, 输出含 紧急/关注/正常 三级 next-action, privacy=confidential |
| P5-F4 | cockpit 统一入口 | ✅ passed (硬基础设施, 单独 closeout) | 用户通过 cockpit CLI 一键跑 3 场景, 无需理解仓边界 |

> 2026-06-12 当前状态修正: F1 仍未满足 "≥2 周连续 cron" 的原始时间性要求；
> F2 已以真实工作 query 跑通并写入 archive receipt；F3 已以 3 个真实家庭 query
> 跑出 urgent/attention/normal 且 privacy_path 固定为本地 confidential family store；
> F4 保持 passed。Gate F 仍等待 F1 closeout.

## Readiness / Cadence

- **Readiness**: 已满足
  - F1 runner / history / archive / cron 入口 已落地
  - F2/F3/F4 已真实通过
- **Cadence**: 未满足
  - F1 仍缺 `≥2 周连续 cron`

原则 (2026-06-12 复验重新校准):
- Readiness satisfied = 工程链路可运行
- Cadence satisfied = 原始时间窗标准满足
- Gate F 只有在 Cadence 也满足时才可 passed
- 本节仅作为 reviewer 复验信号, 不在 plan.yaml 增加新 status 字段

## Gate Status

- `opc_phase5_gate_f_not_yet_passed` (命名: Gate F, 区别于 P6 Gate F — phase 隔离)

## Red Lines

- ❌ "scenario 输出没有 source 声明" (Gate F acceptance 必备)
- ❌ "scenario 输出没有 timestamp" (Gate F acceptance 必备)
- ❌ "scenario 输出没有 next-action" (Gate F acceptance 必备)
- ❌ "用户需手动切换仓才能跑 scenario" (P5-F4 必备, 用户无感)
- ❌ "family-health scenario 用 non-confidential privacy class" (隐私约束)
- ❌ "scenario 跑通次数 < 2 即声明 passed" (可重复性硬要求)

## Acceptance Package (F1-F4 全部 passed 所需)

1. F1: 2 次 cron 输出各含 ≥3 candidates + source + timestamp + next-action
2. F2: 1 个真实 work query 输出 + 5 仓 audit trail
3. F3: 1 个 family-health query 输出 + privacy 路径实证
4. F4: cockpit CLI 3 scenario 跑通, 用户不需切仓
5. 红线 6 项全 hold

## Phase Open Condition (任务 4 readiness)

P5 **可开始** 当且仅当:
- ✅ P3 Gate D **passed** (现状满足)
- ✅ P4 Gate E **passed** (现状满足)
- ⏳ F1 至少 1 次设计 baseline 且进入真实 cron 窗口 (现状: 未满足)
- ✅ F2/F3 已有真实 runtime baseline
- ✅ P3 业务 dispatch spine 已完成

P5 **blocked**:
- P3 Gate D 退到 not_started (不允许)
- P4 Gate E 退到 not_started (不允许)
- cockpit 入口降级 (3 scenario 走不通)

P5 **final close condition** (Gate F passed):
- F1-F4 全部 runtime 实证
- 验收包 5 项全有 evidence
- 红线 6 项全 hold

## Forbidden Premature Claims

- ❌ "P5 实施完成" 在 F1-F4 未全部 passed 之前
- ❌ "scenario 通过验收" 在 2 次以下重复跑之前
- ❌ "用户可以跑 scenario" 在 F4 入口落地之前
- ❌ "family-health 可用" 在 F3 privacy 路径实证之前

## Signal

```
opc_phase5_gate_f_not_yet_passed
opc_phase5_subgate_f1_not_yet_passed
opc_phase5_subgate_f2_passed
opc_phase5_subgate_f3_passed
opc_phase5_subgate_f4_passed
```

(待 F1-F4 全部 passed 后 emit `opc_phase5_gate_f_passed`)
