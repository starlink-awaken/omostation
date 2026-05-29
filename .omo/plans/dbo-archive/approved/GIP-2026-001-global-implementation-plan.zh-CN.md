---
id: GIP-2026-001
title: DigitalBrainOS Global Implementation Plan
status: approved
owner_role: Conductor
created_at: 2026-05-14
updated_at: 2026-05-24
ssot: true
scope: global
---

# DigitalBrainOS 全局实施计划

本文件是 DigitalBrainOS 后续协作的实施计划 SSOT。路线图、方案、任务包、Agent 调度、交接、事件线都必须以本文件为上游依据。

## SSOT 规则

| 对象 | SSOT |
|---|---|
| 长期愿景 | `docs/00-vision/vision.zh-CN.md` |
| 全局实施计划 | `plans/approved/GIP-2026-001-global-implementation-plan.zh-CN.md` |
| 高层路线 | `docs/60-roadmap/master-roadmap.zh-CN.md` |
| 推进层级 | `docs/20-operating-model/execution-taxonomy.zh-CN.md` |
| 方案管理 | `docs/20-operating-model/plan-proposal-management.zh-CN.md` |
| 任务执行 | `work-packets/` |
| 过程状态 | `coordination/` |
| 重大架构决策 | `docs/90-decisions/` |

修改规则：

- 改变阶段、Wave、Sprint、优先级、依赖或退出条件，必须更新本文件。
- 新增 accepted proposal 后，如果影响全局实施，必须回写本文件。
- Work Packet 不能单独改变路线，只能执行本文件或已批准方案定义的工作。
- Agent 输出不能直接修改本文件，必须经过 Conductor integration review。

## 当前推进栈

```text
Goal: Digital Brain Operating System
Horizon: H0 Blueprint and Control Plane
Phase: Phase 2 Trusted Execution with durable single-operator MVP
Wave: P2B external runtime adapter implementation
Sprint: S5 AgentMesh/eCOS live facade implementation completed
Readiness: R3 bootstrap ready; durable MVP usable; external live facades completed
```

## 2026-05-21 规划纠偏

当前 Workspace 其他项目的成熟度已经改变了 DigitalBrainOS 的合理边界：

- SharedBrain 已经提供可复用的记忆、审计、surface contract 和 sovereignty interface。
- Agora 已经提供服务注册、路由、健康检查、事件总线和持久化注册表。
- agentmesh 已经提供 multi-agent gateway / scheduler / router。
- eCOS 已经把 B-OS 桥接、LADS/SSB 持久事件流和多模型协同前置成现实能力。
- pallas 已经成为知识工程统一入口。
- Forge 已经形成可复用的工具注册表、能力索引和发现/沉淀机制，适合作为外部能力源。
- MetaOS 已经形成较完整的决策门控、日课、复盘、周检和行动协议，适合作为协议源与模板源。

因此本计划从今天起采用新的硬约束：

1. DigitalBrainOS 优先作为控制平面，而不是重复构建外部项目已成熟的 runtime。
2. 能 wrap 的不重写，能 delegate 的不内建，能复用现成接口的不重复定义第二套真相源。
3. Forge 进入外部能力源轨道，MetaOS 进入协议源轨道；两者都不作为 DBOS 的新 runtime 主线。
4. Phase 2 之后的推进，必须优先以 adapter / bridge / policy integration 为主，而不是继续在本仓库堆重复运行时。

## 2026-05-24 Workspace 迭代校准

最近 14 天外部项目增量显示：`agentmesh/agora/eCOS/SharedBrain/Forge/MetaOS` 都处于持续活跃迭代。

因此新增执行约束：

1. P3 期间禁止新增“外部 runtime 等价实现”到 DBOS 主仓。
2. 每个 Phase gate 前，必须执行一次 `~/Workspace` 外部项目迭代快照校准，并记录到 review artifact。
3. 对外部依赖只做 read-only/projection/delegate/bridge 四类接入，禁止隐式写回路径。

## 2026-05-29 Workspace 目标纠偏

2026-05-29 的外部依赖快照显示，P5 strict gate 的当前阻断点已经从旧叙事里的 `MetaOS/agora` 转移为 `kos_still_red`：

- `MetaOS` 当前为 green，继续监控，不再作为当前 gate blocker。
- `agora` 当前为 green，dirty 变化不命中 contract watch 关键路径，不再作为当前 gate blocker。
- `kos` 当前为 red，dirty=72、effective=52、noise=20，是 P5 -> P6 strict gate 的唯一 P0 阻断点。
- `eCOS` 与 `Forge` 当前为 attention，进入 P1/P2 triage，不阻断 gate。

因此 P5-W3 的执行焦点纠偏为：

1. 优先执行 `WP-2026-232`，对 KOS dirty/effective/noise 与合同影响做 read-only baseline recalibration。
2. 不修改外部项目，不清理外部 dirty worktree，不用 DBOS 代替 owner-side 修复。
3. strict preflight 继续绑定 external unblock guardrail；只有 `kos_still_red` 消除且 strict preflight 通过后，才允许继续 P5 -> P6。
4. 后续日报、handoff、phase gate、authoritative status 必须以 2026-05-29 快照事实为准，不得继续散发 `MetaOS/agora` 旧 blocker。

## 总体阶段

| Phase | 时间 | 核心目标 | 退出条件 | Readiness |
|---|---:|---|---|---|
| Phase 0 | 2026-05-14 到 2026-05-20 | 蓝图、控制空间、协作机制、Runtime 合同种子 | R3 bootstrap ready | R2 → R3 |
| Phase 1 | 2026-05-20 到 2026-05-20 | 个人大脑最小闭环 | 资料到记忆闭环、最小 personal surface 已验证 | R3 |
| Phase 2A | 2026-05-20 到 2026-05-20 | 单人 durable MVP | 任务、审批、审计、failed/recovery 主链可用 | R3 |
| Phase 2B | 2026-05-21 起 | 外部 runtime 集成化 | SharedBrain / Agora / agentmesh / eCOS / pallas 的边界与 adapter 路线冻结 | R3 → R4 |
| Phase 3 | 后续 | 工作流与长任务恢复 | 长任务可恢复、评估、复盘 | R4+ |
| Phase 4 | 后续 | 团队大脑 | 团队共享记忆、决策、权限和审计 | R5 seed |
| Phase 5 | 后续 | 多脑联邦 | 多 Brain 可策略化共享、撤销和同步 | R5 |
| Phase 6 | P5 strict gate 通过后 | 受控生产运行 | 日常运行、生产证据、事件演练、发布候选证据闭环 | R5 operations |

## Phase 6 受控生产运行入口

Phase 6 只能在 P5 strict gate 通过后启动。P6 不新增外部 runtime，不替代 KOS/SharedBrain/Agora/agentmesh/eCOS 等外部 truth source；它负责把已经通过 P5 的系统带入受控日常运行。

入口 SSOT：`docs/60-roadmap/phase6-entry-plan.zh-CN.md`。

P6 初始任务包：

| Packet | 目标 | 状态 |
|---|---|---|
| `WP-2026-235` | P6 entry gate and confirmation pack | planned |
| `WP-2026-236` | Controlled operator run loop | planned |
| `WP-2026-237` | Production ledger convergence | planned |
| `WP-2026-238` | Incident drill and rollback rehearsal | planned |
| `WP-2026-239` | P6 daily operations dashboard | planned |
| `WP-2026-240` | P6 release candidate evidence pack | planned |

当前约束：`scripts/p6_entry_preflight.py` 必须通过后，才能把 phase gate 从 P5 推进到 P6。当前因 `kos_still_red` 仍处于 hold。

## Phase 2B 外部化运行时集成原则

### 控制平面原则

DigitalBrainOS 负责：

- work packet
- coordination
- phase gate
- truth ledger
- operator dashboard
- daily brief / retrospective
- cross-project integration policy

DigitalBrainOS 不应重复内建：

- SharedBrain 已有的 memory / audit / surface runtime
- Agora 已有的 registry / routing / health convergence
- agentmesh 已有的 multi-agent execution gateway
- eCOS 已有的持久桥接与委员会连续性机制

### 集成优先级

1. SharedBrain adapter：记忆、审计、surface contract、memory sovereignty
2. Agora adapter：ToolService registry、service routing、health/event convergence
3. agentmesh adapter：AgentRun execution gateway、scheduler、router
4. eCOS bridge：B-OS/SSB continuity、handoff、failure circulation
5. pallas surface：知识工程统一编排入口
6. Forge capability source：工具注册、能力索引、发现/沉淀索引
7. MetaOS protocol source：决策门控、复盘模板、行动协议

### Phase 2B 关键交付

| Packet | 标题 | 产物 |
|---|---|---|
| WP-2026-115 | Planning Realignment for Externalized Runtime | GIP / roadmap / blueprint realignment |
| WP-2026-116 | External Runtime Integration Strategy | asset substitution matrix + integration priority |
| WP-2026-117 | SharedBrain Runtime Adapter Strategy | truth ownership matrix + retained governance fields |
| WP-2026-118 | Agora Service Fabric Delegation Strategy | service-fabric delegation boundary + no-duplicate list |
| WP-2026-119 | Agora Adapter Contract Mapping | ToolService / route / health / event field mapping |
| WP-2026-120 | SharedBrain Contract Mapping | stable ref / cache / governance override / degraded mode rules |
| WP-2026-121 | SharedBrain Binding Sample Pack | memory/audit/surface/sovereignty binding examples |
| WP-2026-122 | Agora Delegated Route Sample Pack | service/route/health/event binding examples |
| WP-2026-123 | SharedBrain Read-Only Probe | verify stable refs and projection-only bindings without writes |
| WP-2026-124 | Agora Read-Only Probe | verify registry/route/health/event placeholders against live readable truth |
| WP-2026-125 | SharedBrain Memory Contract Deep Probe | push beyond placeholder on MemoryItem canonical object shape |
| WP-2026-126 | Agora Live-Readable Registry Snapshot Probe | verify concrete sample service presence if readable |
| WP-2026-127 | AgentMesh Execution Adapter Strategy | freeze delegate/boundary contract for agent execution gateway |
| WP-2026-128 | eCOS Continuity Bridge Strategy | freeze bridge/event mapping for continuity and handoff |
| WP-2026-146 | Forge Capability Source / Read-Only Facade / Discovery Binding | capability source boundary + read-only facade |
| WP-2026-147 | MetaOS Protocol Source / Decision Gate Import / Review Template Binding | protocol import boundary + review template binding |
| next | adapter / bridge live implementation | implement minimal live facades and acceptance evidence for AgentMesh / eCOS |

补充：`WP-2026-129` 到 `WP-2026-140` 已全部完成，Phase 2B 当前不再停留在边界冻结与概念层，下一步是把 AgentMesh / eCOS 的最小 read-only facades 真正接入 DBOS 控制平面，并用 acceptance evidence 验证。
进一步补充：`WP-2026-141`、`WP-2026-142`、`WP-2026-143` 已全部完成，AgentMesh / eCOS live facade path 以及其正式验收已落到真实工作树，后续只剩 adapter follow-up 收口，不再进行新的 boundary freeze。
进一步补充：Forge 和 MetaOS 不进入 Phase 2B live adapter/bridge 主线，它们分别进入外部能力源与协议源的 read-only 轨道，优先做索引、模板和边界收口，不做 runtime 重建。
进一步补充：`WP-2026-146`、`WP-2026-147` 已完成验收。Forge 作为外部 capability source、MetaOS 作为外部 protocol source 的 follow-up 已正式收口为只读边界；两者都不进入 DBOS runtime core。
进一步补充：Phase 2B 仍未 closeout，下一步依旧只做 adapter follow-up。
进一步补充：`WP-2026-148` 已完成 Forge / MetaOS 之后的 Phase 2B closeout recheck。结论不变：phase gate 仍未通过，不能进入 Phase 3，下一步仍是 adapter follow-up。
进一步补充：`WP-2026-149` 已完成 adapter follow-up operator binding。`adapter-follow-up.json` 现在把 AgentMesh / eCOS facade 状态与 phase gate 合并成机器可读判定；当前仍为 `adapter_followup_required`。
进一步补充：`WP-2026-150` 已完成 eCOS failure snapshot exit rule。stale 但可读的 failure snapshot 被归类为 `acceptable_degraded` 且 `closeout_blocking=false`；禁止用 stale failure data 声明 verified remediation closure。
进一步补充：`WP-2026-151` 已完成 Phase 2B strict exit review。技术 gate 已通过：`gate_passed=true`、`state=ready_for_confirmation`；但 `allow_next_phase=false` 且 `confirmation.confirmed=false`，不得启动 Phase 3。
## Phase 0 详细实施

### P0-W0 Project Set Bootstrap

时间：2026-05-14。

状态：completed。

目标：

- 建立独立项目集空间。
- 建立 README、AGENTS、CLAUDE、贡献、安全和校验基础。
- 不移动、不合并、不修改旧项目。

完成证据：

- `scripts/validate_workspace.sh` 通过。
- `WP-2026-001` 到 `WP-2026-003` 相关产物已落盘。

### P0-W1 Conductor Operating System

时间：2026-05-14 到 2026-05-20。

状态：active，基本完成。

目标：

- 建立 Conductor 中枢工作方式。
- 建立 Agent 团队、协作空间、事件线、热启动、workflow/skills。
- 建立 readiness 校验。
- 建立计划/方案管理。

主要产物：

- `coordination/`
- `scripts/hot_start.sh`
- `scripts/readiness_check.sh`
- `agents/registry/team.md`
- `agents/skills/`
- `workflows/`
- `docs/20-operating-model/agent-handoff-contract.zh-CN.md`
- `docs/20-operating-model/plan-proposal-management.zh-CN.md`

退出条件：

- `validate_workspace.sh` 通过。
- `readiness_check.sh` 通过。
- active work packets 无 pending validation。
- W2 的 Work Packets 已创建。

### P0-W2 Runtime Contract Freeze

时间：2026-05-21 到 2026-06-03。

状态：bootstrap completed，后续可继续细化实现。

目标：

- 冻结 Runtime API v0。
- 冻结 Event/Audit Ledger v0。
- 冻结 Object Field Schema v0。
- 明确 SharedBrain、KOS、Minerva、Sophia、Agora、AgentMesh 的边界合同。

Work Packets：

| Packet | 标题 | 产物 | Owner | 依赖 |
|---|---|---|---|---|
| WP-2026-009 | Runtime API v0 | `docs/10-architecture/runtime-api-v0.md` | Runtime Engineer | W1 |
| WP-2026-010 | Event/Audit Ledger v0 | `docs/10-architecture/event-audit-ledger.md`, schemas | System Architect | WP-2026-009 |
| WP-2026-011 | Object Field Schema v0 | `docs/10-architecture/object-field-schema.md`, schemas | Knowledge Architect | WP-2026-010 |
| WP-2026-012 | Project Asset Maturity Map | `docs/10-architecture/project-asset-maturity-map.md` | Integration Engineer | W1 |

验收：

- Memory、Task、Approval、Audit、Tool Registry 都有接口定义。
- TimelineEvent、AuditEvent、AgentRun、ApprovalReceipt 有 schema。
- 核心对象有字段、状态、版本、所有者、权限和审计字段。
- 每个现有项目有成熟度、入口、集成方式和风险。

当前完成证据：

- `docs/10-architecture/runtime-api-v0.md`
- `docs/10-architecture/event-audit-ledger.md`
- `docs/10-architecture/object-field-schema.md`
- `docs/10-architecture/project-asset-maturity-map.md`
- `schemas/audit-event.schema.json`
- `schemas/agent-run.schema.json`
- `schemas/approval-receipt.schema.json`
- `schemas/object-field.schema.json`

### P0-W3 Dispatch Automation

时间：2026-06-04 到 2026-06-14。

状态：completed with conditional freeze.

目标：

- 建立 `dbos-agent` 最小调度脚手架。
- 从 Work Packet 生成 Agent prompt。
- 记录 run metadata。
- 收集 artifact。
- 执行 evaluate/readiness。
- 完成一次外部 Agent 只读试跑。

Work Packets：

| Packet | 标题 | 产物 | Owner | 依赖 |
|---|---|---|---|---|
| WP-2026-013 | Hierarchical ID System | `docs/20-operating-model/hierarchical-id-system.zh-CN.md`, `scripts/dbos-agent` | Conductor | WP-2026-010 |
| WP-2026-014 | External Agent Read-only Trial | `artifacts/reviews/2026-05-14-w3-dispatch-automation/external-agent-readonly-trial.md` | Conductor | WP-2026-013 |
| WP-2026-015 | Project Asset Read-only Probes | `artifacts/reviews/2026-05-14-w3-dispatch-automation/project-asset-readonly-probe.md` | Integration Engineer | WP-2026-010 |
| WP-2026-016 | Runtime API Review | `artifacts/reviews/2026-05-14-w3-dispatch-automation/runtime-api-review.md` | Architecture Reviewer | WP-2026-010 |
| WP-2026-017 | Phase 0 Freeze Review | `plans/approved/phase0-freeze-report.md` | Evaluation Engineer | WP-2026-014, WP-2026-015, WP-2026-016 |

验收：

- `scripts/dbos-agent dispatch` 能生成 prompt/run record。
- `scripts/dbos-agent collect` 能登记 artifact。
- `scripts/dbos-agent evaluate` 能跑基础检查。
- Copilot/Claude/Gemini 至少一个完成只读试跑，且不写 canonical docs。

当前完成证据：

- `scripts/dbos-agent`
- `scripts/r3_readiness_check.sh`
- `coordination/runs/`
- `artifacts/runs/run-20260514170030-copilot/prompt.md`
- `artifacts/reviews/2026-05-14-w3-dispatch-automation/external-agent-readonly-trial.md`
- `artifacts/reviews/2026-05-14-w3-dispatch-automation/project-asset-readonly-probe.md`
- `artifacts/reviews/2026-05-14-w3-dispatch-automation/runtime-api-review.md`
- `plans/approved/phase0-freeze-report.md`
- `reports/retrospectives/2026-05-14-w3-dispatch-automation.md`

Freeze decision:

- Phase 0 status: conditional pass.
- Phase 1 preparation is active.
- Phase 1 implementation and external project integration remain blocked until
  follow-up hardening packets close.

Follow-up work:

| Packet | 标题 | 目的 | Gate |
|---|---|---|---|
| WP-2026-018 | External Agent Execution Evidence Hardening | Record command, prompt, stdout/stderr, exit code, artifact hash, and evaluation result | Completed 2026-05-15 |
| WP-2026-019 | Read-only Probe Boundary Verification | Verify per-asset read-only command boundaries | Completed 2026-05-15 |
| WP-2026-020 | AgentRun Schema Enforcement and Historical Drift Marking | Enforce current AgentRun schema and label older drifted runs | Completed 2026-05-15 |
| WP-2026-021 | Phase 1 Object Schemas v0 | Define SourceItem, ResearchRun, Claim, Evidence, MemoryItem, Review, Reflection | Completed 2026-05-15 |
| WP-2026-022 | Ledger Machine Contract Hardening | Align Timeline/Audit schemas with the ledger prose contract | Completed 2026-05-15 |

Phase 1 preparation current evidence:

- `WP-2026-018` completed.
- `WP-2026-019` completed.
- `WP-2026-020` completed.
- `WP-2026-021` completed.
- `WP-2026-022` completed.
- `scripts/dbos-agent` now supports `execute` evidence capture.
- New runs can record prompt, command, cwd, stdout/stderr, exit code, artifact
  hashes, and structured `evaluation_result`.
- Negative checks prove missing prompt/artifacts and missing collect artifacts
  fail instead of silently passing.
- Known external assets have read-only probe boundaries and adapter-readiness
  recommendations. KOS is the first adapter candidate after remaining gates.
- AgentRun records are now split into current schema valid, negative test
  fixture, and historical drift. Historical records are preserved but not
  counted as fresh evidence.
- Phase 1 object schemas now define the capture-to-memory loop with provenance,
  permission, confidence, evidence, owner, status, and audit fields.
- Ledger schemas now require work packet, artifact, evidence, correlation,
  correction, policy, and approval fields needed for provenance and approval
  gates.
- `WP-2026-023` completed. Copilot is promoted to core scoped execution
  assistant. Phase 1 first slice is `Inbox -> SourceItem`.

## Phase 1 个人大脑 MVP

时间：2026-06-15 到 2026-09-30。

目标闭环：

```text
Inbox → SourceItem → ResearchRun → Claim/Evidence → MemoryItem → Review → Reflection
```

Waves：

| Wave | 时间 | 目标 | 关键产物 |
|---|---:|---|---|
| P1-W1 Capture and Source Layer | 2026-06-15 到 2026-07-05 | 资料捕获和 SourceItem 归一化 | Inbox、SourceItem schema、KOS adapter |
| P1-W2 Research Loop | 2026-07-06 到 2026-08-02 | Minerva/Sophia 研究闭环 | ResearchRun、Claim/Evidence、report |
| P1-W3 Memory Promotion | 2026-08-03 到 2026-08-30 | 研究产物晋升为长期记忆 | MemoryItem、Review、Reflection |
| P1-W4 Personal Brain Surface | 2026-09-01 到 2026-09-30 | 个人工作台最小体验 | project workspace、review queue |

Phase 1 退出条件：

- 一个真实项目完成从资料到记忆的闭环。
- 记忆有来源、证据、置信度、状态和淘汰机制。
- 个人大脑 MVP 有可重复流程。

Phase 1 entry decision:

- Status: conditional go.
- First implementation slice: `Inbox -> SourceItem`.
- Next work packets: `WP-2026-024`, `WP-2026-025`, `WP-2026-026`.
- Copilot may execute scoped worker tasks with artifact-first output and exact
  write scopes. Conductor keeps SSOT integration authority.

## Phase 2 可信执行 Runtime

时间：2026-10-01 到 2026-12-31。

目标闭环：

```text
TaskRun → ApprovalRequest → ToolCall → AuditEvent → MemoryItem / Reflection
```

Waves：

| Wave | 时间 | 目标 | 关键产物 |
|---|---:|---|---|
| P2-W1 Task Runtime | 2026-10-01 到 2026-10-25 | TaskRun 和状态机 | Task API、task ledger |
| P2-W2 Approval and Policy | 2026-10-26 到 2026-11-20 | 审批、策略、风险门禁 | ApprovalReceipt、Policy engine seed |
| P2-W3 Tool Registry and Audit | 2026-11-21 到 2026-12-15 | 工具注册、调用和审计 | ToolService、ToolCall、AuditEvent |
| P2-W4 Trusted Execution Review | 2026-12-16 到 2026-12-31 | 可信执行验收 | security/eval report |

退出条件：

- 高风险动作不能绕过审批。
- 每个工具调用可回溯到任务、操作者、策略和审计事件。

## Phase 3 工作流大脑

时间：2027-01-01 到 2027-03-31。

Waves：

| Wave | 目标 | 关键产物 |
|---|---|---|
| P3-W1 WorkflowRun Engine | 工作流状态机 | WorkflowRun、StepRun |
| P3-W2 Checkpoint and Recovery | 中断恢复 | Checkpoint、RecoveryPlan |
| P3-W3 Evaluation Gates | 质量门禁 | EvaluationReport、scorecard |
| P3-W4 Reflection Promotion | 复盘晋升 | Failure → Pattern → Standard |

退出条件：

- 长任务可中断、恢复、评估和复盘。

## Phase 4 团队大脑

时间：2027-04-01 到 2027-09-30。

Waves：

| Wave | 目标 | 关键产物 |
|---|---|---|
| P4-W1 Workspace and Members | 团队空间和成员 | Workspace、Member、RoleBinding |
| P4-W2 Team Memory | 共享记忆 | TeamMemory、visibility policy |
| P4-W3 Decision and Approval | 团队决策和审批 | DecisionRecord、TeamApproval |
| P4-W4 Team Product Surface | 团队体验 | Team Brain UI/API |

退出条件：

- 团队项目可沉淀共享上下文、决策、任务和复盘。

## Phase 5 多脑联邦

时间：2027-10-01 起。

Waves：

| Wave | 目标 | 关键产物 |
|---|---|---|
| P5-W1 Brain Federation Model | 多 Brain 模型 | BrainFederation |
| P5-W2 Delegation and Revocation | 委托和撤销 | Delegation、Revocation |
| P5-W3 Policy-aware Sync | 策略同步 | SyncPolicy、ConflictResolution |
| P5-W4 Extension Ecosystem | 插件生态 | SDK、connector market |

退出条件：

- 多个 Brain 可以按策略共享知识和能力。
- 授权可撤销，共享可追踪，冲突可解释。

## 当前下一批 Work Packets

以下是进入 W2 前应创建或执行的下一批任务：

| 优先级 | Packet | 标题 | 类型 | 目标 |
|---:|---|---|---|---|
| 1 | WP-2026-011 | External Agent Read-only Trial | execution | 使用 dbos-agent 包装一次外部 Agent 只读任务 |
| 2 | WP-2026-012 | Project Asset Read-only Probe | integration | 对重点项目做只读入口探测 |
| 3 | WP-2026-013 | Runtime API Review | review | 让架构/治理 Agent 复核 Runtime API |
| 4 | WP-2026-014 | Phase 0 Freeze Review | evaluation | 冻结 Phase 0 并准备 Phase 1 |

## 协作更新协议

每次协作必须遵守：

1. 热启动：运行或读取 `scripts/hot_start.sh` 输出。
2. 定位层级：确认 Goal/Horizon/Phase/Wave/Sprint。
3. 查 SSOT：读取本文件相关部分。
4. 建任务：创建或更新 Work Packet。
5. 派工：必要时使用 `agent-collaboration-run`。
6. 交接：复杂任务使用 `agent-handoff-integration`。
7. 方案：涉及方案取舍时使用 `plan-proposal-decision`。
8. 验证：运行 workspace/readiness/timeline checks。
9. 回写：更新本文件、timeline、dispatch、handoff。

## 变更控制

本文件的变更需要满足：

- 有明确来源：用户请求、accepted proposal、ADR、phase review 或 readiness review。
- 有 work packet。
- 有验证证据。
- 有 timeline event。
- 如果影响长期架构或治理，必须创建 ADR。


补充（2026-05-22）：`WP-2026-152` 已记录用户确认并进入 Phase 3。当前阶段为 `P3-W1 WorkflowRun Engine`，首个 active packet 是 `WP-2026-153 WorkflowRun Engine Contract Seed`。P3 仅为 entry/in_progress，未声明 P3 exit 或 production readiness。

补充（2026-05-22）：`WP-2026-154` 已完成 file-backed WorkflowRun / StepRun service，CLI 支持 `workflow create/list/advance`，personal surface 输出 `workflow-queue.json`。下一步是 WorkflowRun web operator surface；P3 仍为 in_progress。

补充（2026-05-22）：`WP-2026-155` 已完成 WorkflowRun web operator surface，`GET /workflows`、`POST /workflows`、`POST /workflows/{workflow_id}/advance` 均通过 service 层运行。下一步是 high-risk StepRun approval enforcement；P3 仍为 in_progress。
