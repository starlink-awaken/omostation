# OPC-P7: Governance Hardening & Release Train

> Date: 2026-06-11
> Source: OPC-ROADMAP.md §M7, opc-roadmap-omo-plan.md §Phase 7
> Status: governance baseline (载体建立, 不做业务实现)
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

- **opc_phase3_gate_d_not_yet_passed** (P3 业务收口)
- **opc_phase4_gate_e_not_yet_passed** (P4 LLM 路由)
- **opc_phase5_gate_f_not_yet_passed** (P5 scenarios 跑通)
- **opc_phase6_gate_g_not_yet_passed** (P6 evolution loop)
- §19 跨仓债 E1-E4 收口

## Sub-gates

| ID | Title | Status | Evidence Requirement |
|:---|:------|:-------|:---------------------|
| P7-H1 | release train 节奏 | 📋 not_started | 至少 1 个 1-2 周周期跑通 (cut → review → ship + retrospective 落盘) |
| P7-H2 | 跨仓 phase gate 实装 | 📋 not_started | `check_phase_gate.py` 跑通, 8 Gate acceptance 自动检查 + audit 写入 |
| P7-H3 | 跨仓 audit rollout 硬扩 | 📋 not_started | E2 dispatcher cron (monthly + weekly + pre-release), 5 仓 §17 metrics 自动聚合 |
| P7-H4 | 文档同步 policy | 📋 not_started | 4 关键文档 (PANORAMA/ENTRY/JOURNEY/ROADMAP) 自动 lint + 跨文档术语一致 |
| P7-H5 | 评审模板 | 📋 not_started | `REVIEW-TEMPLATE.md` 落地, 至少 1 次 review 跑通 |

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
- ✅ P5 Gate F passed
- ✅ P6 Gate G passed
- ✅ OPC 路线图所有前序 gate 收口 (P3-P6)

P7 **blocked**:
- P3/P4/P5/P6 任一 Gate 退到 not_started (不允许)
- 任何前序 phase retrospective 缺失

P7 **final close condition** (Gate H passed = OPC 路线图全闭环):
- H1-H5 全部 runtime 实证
- 验收包 6 项全有 evidence
- 红线 6 项全 hold
- OPC 路线图 8 阶段 (M0-M7) 全部 done
- 7 个连续 Gate (B → B2 → C → D → D → E → F → G) 全部 hit 实质化 + 实证

## Forbidden Premature Claims

- ❌ "P7 完成" 在 H1-H5 未全部 passed 之前
- ❌ "release train 跑通" 在 H1 retrospective 落盘缺失时
- ❌ "phase gate 自动化" 在 H2 实证缺失时
- ❌ "cross-repo metrics 治理闭环" 在 H3 cron 实证缺失时
- ❌ "OPC 路线图 100% 收口" 在 Gate H 未 passed 时 (此即 P7 终点)

## Signal

```
opc_phase7_gate_h_not_yet_passed
opc_phase7_subgate_h1_not_started
opc_phase7_subgate_h2_not_started
opc_phase7_subgate_h3_not_started
opc_phase7_subgate_h4_not_started
opc_phase7_subgate_h5_not_started
```

(待 H1-H5 全部 passed 后 emit `opc_phase7_gate_h_passed` = OPC 路线图全闭环信号)
