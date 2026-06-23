---
plane: knowledge
type: design
status: draft
freshness: 2026-05-31
maintainer: auto
---
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# Phase 5 entry architecture

> **Assumption**: 用户未在线确认边界，因此默认采用最稳妥方案：**Phase 5 先做设计与进入条件定义，实际实现只收口 Phase 4 的剩余 Wave 2 任务。**
>
> **Inputs**: `phase5-requirements.md` v0.1、`task-center-requirements.md` v0.2.1、Phase 4 roadmap/Wave 2 plan、最新 convergence audit。
> 本文档属于历史阶段的入口设计分析，保留当时的 entry gate 判断、Wave 拆分和推进边界，不是当前阶段状态、当前任务许可或当前系统事实 SSOT。
> 当前执行面一律以 `/.omo/goals/current.yaml`、`/.omo/state/system.yaml`、`/.omo/tasks/active/`、`/.omo/PROJECTS.yaml` 为准。

## 1. Executive judgment

`phase5-requirements.md` 的方向是对的，但它默认了一个**已经稳定存在的 Task Center 与治理面**。  
当前 `.omo` 的真实状态是：

1. **Phase 4 已经把 worker/gate/triage 的基础设施做出来了**
2. **Task Center v0.2 仍是设计包，不是已运行底座**
3. **Phase 5 v0.1 直接从“目标定义”跳到了“3 个实施 wave”，中间缺少明确的 entry gate**

所以正确的推进方式不是“直接开始 Phase 5 Wave 1”，而是：

1. **先关掉 Phase 4 Wave 2 的四个剩余口子**
2. **把 Phase 5 增补一个 Wave 0 / Entry Gate**
3. **再按 Durable → Governance → Auto-Discovery/Templates → Skill Federation 的顺序进入 Phase 5**

## 2. What Phase 5 gets right

Phase 5 草案的五个目标是合理的：

1. **Durable Execution**：补齐“进程死掉后还能继续”的能力
2. **Governance Pipeline**：补齐 proposal / approval / execute / verify
3. **Script Auto-Discovery**：消除 registry 与脚本元数据双写
4. **Task Templates**：减少重复 YAML
5. **Skill Federation**：把 AI skill 与调度系统统一到同一条治理链

这五个目标与当前 `.omo`/Task Center 的真实演化方向一致，没有战略偏航。

## 3. Where Phase 5 v0.1 is still optimistic

### 3.1 It treats Task Center as already-landed infrastructure

Phase 5 文档把 `_truth/task-center/`、`_delivery/task-center/`、proposal/tooling 扩展都当成“下一步可以直接开做”的前提。  
但当前仓库还停留在：

- Phase 4 worker ops / handoff / gate hardening
- Task Center v0.2 为设计态，而非稳定实现态

因此 **Phase 5 的真正前置不是“读完需求”**，而是：

1. Task Center 落位与 plane ownership 固化
2. secrets / Hermes / proposal ownership 说清楚
3. Phase 4 delivery artifacts 真正落地

### 3.2 It misses a phase boundary artifact

现在 Phase 4 → Phase 5 缺少一个明确的“entry contract”。  
至少要有：

- Phase 4 closeout retrospective
- G4.2 closure evidence
- Phase 5 entry checklist
- Task Center readiness judgment

否则会出现 “Phase 4 还在半施工、Phase 5 已经开工” 的双相态。

### 3.3 Wave ordering is right, but Wave 1 is overloaded

`phase5-requirements.md` 里 Wave 1 同时塞了：

- checkpoint schema
- restart/recovery
- proposal schema
- proposal MCP tools
- governance level state machine

这在设计上同属“基础治理”，但实现上其实有两个不同的收敛面：

1. **Durable runtime plane**
2. **Governance proposal plane**

建议保持同一波次，但拆成两个 execution lanes，而不是当成一个连续串行包。

## 4. Recommended architecture boundary

## 4.1 Phase 4 owns “execution governance”

Phase 4 的收尾范围应锁定为：

1. **Lifecycle gate semantics complete**
2. **Divergence triage operationalized**
3. **Utilization baseline becomes decision-grade**
4. **Handoff index becomes a real evidence corpus**
5. **Phase 4 retrospective written and linked**

这层做完后，`.omo` 才真正具备 “默认执行底座”。

## 4.2 Phase 5 owns “process governance”

Phase 5 不应再回头重写 Wave 2 已做过的 worker/gate 基础，而是从这些已有机制之上往上搭：

1. **Durable execution runtime**
2. **Proposal / approval / apply pipeline**
3. **Script/skill discovery and registration**
4. **Blueprint/template instantiation**
5. **Skill-to-task federation**

也就是说：

- **Phase 4 = execution plane hardening**
- **Phase 5 = process plane formalization**

## 4.3 Plane ownership for Phase 5

沿用最新四平面约束：

| Plane | Phase 5 owner entities | Notes |
|------|------------------------|-------|
| control | max governance level, rollout flag, entry gate state | 只存阶段状态与允许级别 |
| truth | task-center registry/proposals/blueprints, skill declarations | SSOT 实体 |
| knowledge | requirements, architecture, operator guides, review packets | 说明与设计 |
| delivery | runs, checkpoints, proposal execution logs, skill outputs | 运行证据 |

规则不变：**单 owner plane，其他平面只做索引与引用。**

## 5. Entry gate before Phase 5

在 Phase 5 Wave 1 前，增加一个 **Wave 0 / Entry Gate**：

### EG-1 Phase 4 closure

- G4.2 四个任务全部 done
- `state/system.yaml` 不再存在 blob 级 `orphaned_tasks:*`
- 至少一个真实 handoff index artifact 已生成并可回溯
- utilization baseline 已包含周期、完成率、handoff 指标

### EG-2 Task Center readiness

- `task-center-requirements.md` 与 `phase5-requirements.md` 的目录、ownership、secrets、Hermes 语义一致
- v0.1 review 的“已吸收/已过期”状态被显式标注

### EG-3 Governance entry packet

- Phase 4 closeout retrospective
- Phase 5 entry checklist
- 初始 Wave 1 plan

## 6. Recommended iteration cadence

## 6.1 Immediate cadence (now → Phase 4 close)

### Lane A — close current Wave 2

1. lifecycle gate hardening closeout
2. divergence triage artifactization
3. utilization baseline v2
4. handoff index corpus

### Lane B — prepare Phase 5 entry packet

1. write this architecture bridge
2. freeze entry gate
3. sequence the first implementation waves

## 6.2 Phase 5 cadence (revised)

### Wave 0 — entry gate (2-3 days)

- close Phase 4
- freeze Task Center landing model
- refresh review status
- seed Phase 5 goal/task shells

### Wave 1 — durable runtime + governance core (2 weeks)

Execution lanes:

1. **Lane 1**: checkpoint schema + persistence + resume scan
2. **Lane 2**: proposal schema + MCP tools + governance level state machine

Exit:

- runtime can recover
- L2/L3 proposal flow is enforceable

### Wave 2 — auto-discovery + templates (2-3 weeks)

1. frontmatter parser
2. directory scanning + auto registry section
3. blueprint engine + built-in templates

Exit:

- script metadata single-sourced
- repetitive task definitions substantially reduced

### Wave 3 — skill federation (2-3 weeks)

1. skill declaration schema
2. skill→task auto mapping
3. skill execution bridge + delivery outputs

Exit:

- AI skill execution becomes schedulable and governable

## 7. What to finish in this session

本轮不直接启动 Phase 5 实现。  
本轮要交付的是：

1. **Phase 5 入口设计与节奏**
2. **Phase 4 Wave 2 剩余任务收尾**
3. **Phase 4 retrospective / closeout**

## 8. Go / no-go

### Go

- 按“Phase 5 设计-only + Phase 4 execute”边界推进
- 先完成 G4.2，再开 Phase 5 Wave 0

### No-go

- 在 `task-center-requirements.md` 仍未完全落位前直接做 Phase 5 runtime
- 让 Phase 5 去补做 Phase 4 本该完成的 gate/triage/evidence 收尾
