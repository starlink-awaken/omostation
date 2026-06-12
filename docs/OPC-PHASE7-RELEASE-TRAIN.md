# OPC-P7: Governance Hardening & Release Train

> Date: 2026-06-11
> Source: OPC-ROADMAP.md §M7, opc-roadmap-omo-plan.md §Phase 7
> Status: partial closeout (H2/H4/H5 已落地, Gate H 仍待 H1/H3)
> Tracking: `.omo/tasks/planned/OPC-P7-RELEASE-TRAIN.yaml`

---

## Objective

P7 makes OPC maintainable as a long-running personal operating system.
Deliverables:
- 1-2 week release train (cut → review → ship cadence)
- Phase gates and review templates
- Cross-repo audit rollout hardening and expansion plan
- Documentation sync policy for PANORAMA/ENTRY/JOURNEY/ROADMAP

## Prerequisites

- **opc_phase3_gate_d_passed** (P3 业务收口)
- **opc_phase4_gate_e_passed** (P4 LLM 路由)
- **opc_phase5_gate_f_passed** (P5 scenarios 跑通)
- **opc_phase6_gate_g_passed** (P6 evolution loop)
- §19 跨仓债 E1-E4 收口

## Sub-gates

| ID | Title | Status | Evidence Requirement |
|:---|:------|:-------|:---------------------|
| P7-H1 | release train 节奏 | 📋 not_yet_passed (1 次 manual ≠ 1-2 周周期) | 至少 1 个 1-2 周周期跑通 (cut → review → ship + retrospective 落盘) |
| P7-H2 | 跨仓 phase gate 实装 | ✅ passed (checker + matrix + 双格式 audit 落盘) | `check_phase_gate.py` 跑通, 8 Gate acceptance 自动检查 + audit 写入 |
| P7-H3 | 跨仓 audit rollout 硬扩 | 📋 not_yet_passed (cron wrapper 落, 但未真实 cron 触发) | E2 dispatcher cron (monthly + weekly + pre-release), 5 仓 §17 metrics 自动聚合 |
| P7-H4 | 文档同步 policy | ✅ passed (doc-lint + index + drift_total=0) | 4 关键文档 (PANORAMA/ENTRY/JOURNEY/ROADMAP) 自动 lint + 跨文档术语一致 |
| P7-H5 | 评审模板 | ✅ passed (硬基础设施, 8 字段模板 + 1 review) | `REVIEW-TEMPLATE.md` 落地, 至少 1 次 review 跑通 |

> 2026-06-12 当前状态修正: H2 已完成 checker + phase-gate matrix 双格式落盘，
> 且当前 plan/doc/report 自洽；H4 已完成 doc-lint + index 建档且 drift_total=0。
> H1 仍缺真实 1-2 周 release cycle；H3 仍缺真实 cron 触发。Gate H 继续保持未关闭。

## Readiness / Cadence

- **Readiness**: 已满足
  - H1 release runner / wrapper / changelog / retro / index 已可运行
  - H3 daemon / fallback / index / metrics aggregation 已可运行
  - H2/H4/H5 已 closeout
- **Cadence**: 未满足
  - H1 缺真实 1-2 周 interval
  - H3 缺 weekly/monthly/pre-release 真实 cron 时间窗

原则:
- Readiness passed = 工程层与证据 writer 已就绪
- Cadence passed = 原始时间窗标准满足
- Gate H 只有在 H1/H3 cadence 满足后才可能 passed

## Gate Status

- `opc_phase7_gate_h_not_yet_passed` (Gate H — **最终 gate**)

## Red Lines

- ❌ "release notes 缺 summary/validation/debt 三件套" (Gate G acceptance 必备)
- ❌ "phase 缺 retrospective 落盘" (硬要求)
- ❌ "dashboard 缺 phase/milestone/blockers/debt 4 字段" (硬要求)
- ❌ "cross-repo metrics 仅规划无消费" (Gate G 必备)
- ❌ "在 P3/P4/P5/P6 任一 Gate 未 passed 前 claim P7 Gate H" (Playbook §3)
- ❌ "P7 业务实施跳 H1-H5 顺序" (H1 release train 跑通是其他 H 的基础)

## Acceptance Package (H1-H5 全部 passed 所需)

1. H1: 1 release cycle 跑通 + retrospective 落盘
2. H2: check_phase_gate.py 跑通, 8 Gate 自动检查
3. H3: 5 仓 §17 metrics 跨仓聚合 cron 实证
4. H4: 4 文档 lint 跑过, 0 stale
5. H5: REVIEW-TEMPLATE.md 落地 + 1 次 review
6. 红线 6 项全 hold

## Phase Open Condition (任务 4 readiness)

P7 **可开始** 当且仅当:
- ✅ P3 Gate D passed
- ✅ P4 Gate E passed
- ⏳ P5 Gate F passed (当前未满足)
- ⏳ P6 Gate G passed (当前未满足)
- ⏳ OPC 路线图所有前序 gate 收口 (P3-P6; 当前未满足)

P7 **blocked**:
- P3/P4/P5/P6 任一 Gate 退到 not_started (不允许)
- 任何前序 phase retrospective 缺失

P7 **final close condition** (Gate H passed = OPC 路线图全闭环):
- H1-H5 全部 runtime 实证
- 验收包 6 项全有 evidence
- 红线 6 项全 hold
- OPC 路线图 8 阶段 (M0-M7) 全部 done
- 9 个连续 Gate (A → B → B2 → C → D → E → F → G → H) 全部 hit 实质化 + 实证

## Forbidden Premature Claims

- ❌ "P7 完成" 在 H1-H5 未全部 passed 之前
- ❌ "release train 跑通" 在 H1 retrospective 落盘缺失时
- ❌ "phase gate 自动化" 在 H2 实证缺失时
- ❌ "cross-repo metrics 治理闭环" 在 H3 cron 实证缺失时
- ❌ "OPC 路线图 100% 收口" 在 Gate H 未 passed 时 (此即 P7 终点)

## Signal

```
opc_phase7_gate_h_not_yet_passed
opc_phase7_subgate_h1_not_yet_passed
opc_phase7_subgate_h2_passed
opc_phase7_subgate_h3_not_yet_passed
opc_phase7_subgate_h4_passed
opc_phase7_subgate_h5_passed
```

(待 H1-H5 全部 passed 后 emit `opc_phase7_gate_h_passed` = OPC 路线图全闭环信号)
