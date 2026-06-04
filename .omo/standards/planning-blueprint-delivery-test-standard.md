# 规划、蓝图、架构、里程碑、交付与测试迭代标准

> 日期: 2026-05-30  
> 版本: v1.0  
> 状态: active  
> 范围: `.omo` 下所有规划、蓝图、架构、方案、设计、任务规格书、交付标准、测试与复盘文档

---

## 1. 目标

`.omo` 是 omostation 的治理控制面，不只是文档目录。未来所有规划与执行材料必须同时满足三件事：

1. **可追溯**：任何任务都能追溯到蓝图、阶段目标、任务规格、验收证据。
2. **可执行**：Agent 只能从明确的执行源领取任务，不能从历史文档里自由解释任务。
3. **可验证**：每个里程碑必须有测试、日志、健康指标或人工验收证据。

---

## 2. 权威源分层

| 层级 | 权威文件/目录 | 职责 | 更新者 |
|------|---------------|------|--------|
| Blueprint | `.omo/MASTER-BLUEPRINT.md` | 长期愿景、架构边界、阶段地图 | human + architect agent |
| Plan Registry | `.omo/plans/README.md` | 规划文件状态与执行入口 | governance agent |
| Phase Specs | `.omo/plans/phase*-task-specs*.md` | 阶段任务候选、验收清单、agent prompt | phase owner |
| Standards | `.omo/standards/*.md` | 跨阶段不可变规范、门禁、交付标准 | governance agent |
| Goals | `.omo/goals/current.yaml` | 当前 Phase 目标、进入模式、Go/No-Go | human |
| Goal History | `.omo/goals/history/*.yaml` | 已关闭或暂停 Phase 的目标快照 | governance agent |
| Task SSOT | `.omo/tasks/{active,done,blocked}/*.yaml` | Agent 可写任务状态 | assigned agent |
| Runtime State | `.omo/state/system.yaml` | 聚合状态，只读输入 | system aggregator / manual calibration |
| Evidence | `.omo/summaries/*.md`, reports | 验收、复盘、审计、事故证据 | verifier / auditor |
| Tests | `.omo/tests/` | 治理、集成、门禁测试规范或测试代码 | test agent |

规则：

- `_archive/TASK_POOL.md` 降级为历史镜像或迁移入口，不再作为真实任务 SSOT。
- `plans/archive/` 与旧 Phase 5/9/13 文档只能作为参考，不得被 Agent 直接执行。
- `phase3`、`phase4` 任务规格默认是 **future-gated**，只有前序 gate 通过后才能进入 EXECUTION。

---

## 3. 文档状态机

| 状态 | 含义 | 是否可执行 |
|------|------|------------|
| `draft` | 草稿，未评审 | 否 |
| `proposed` | 已提出，等待采纳 | 否 |
| `active` | 活文档，可迭代 | 否，除非被 current goal 引用 |
| `execution-gated` | 执行候选，但需要前置门禁 | 仅限 gate 任务 |
| `execution` | 当前可执行源 | 是 |
| `reference` | 已吸收，保留参考 | 否 |
| `archived` | 已被新版取代 | 否 |

任何从 `execution-gated` 升级到 `execution` 的文档必须满足：

1. `goals/current.yaml` 引用它。
2. `.omo/tasks/active/` 已生成首批任务 YAML。
3. 至少一个验收测试或检查清单存在。
4. 前序 Phase 的关闭状态已记录。

---

## 4. 规划与蓝图迭代规则

每次更新规划、蓝图或架构，必须同步检查以下文件：

| 变更类型 | 必须同步 |
|----------|----------|
| Phase 状态变化 | `goals/current.yaml`, `state/system.yaml`, `plans/README.md`, `../_knowledge/design/MASTER-BLUEPRINT.md` |
| 新里程碑 | 对应 `phase*-task-specs*.md`, `.omo/tasks/active/*.yaml` |
| 新架构边界 | `../_knowledge/design/MASTER-BLUEPRINT.md`, `standards/ARCHITECTURE_CONVERGENCE.md` 或新标准 |
| 新安全约束 | Phase specs、验收清单、测试标准 |
| 新连接器/外部数据源 | 数据分类、RBAC、审计、备份、隐私门禁 |
| 审计发现 | 进入任务 YAML 或明确豁免，不得只停留在审计文档 |

---

## 5. Milestone 标准模板

每个里程碑必须包含：

```yaml
id: M2.1
title: "KOS baseline restore"
phase: 2
entry_gate:
  - "M2.0 governance close complete"
exit_gate:
  - "KOS before/after document count recorded"
  - "10 known documents search 10/10 found"
user_visible_outcome: "知识检索恢复可信"
system_evidence:
  - "health metric"
  - "test report"
  - "audit log"
failure_injection:
  - "simulate 20% index drop"
rollback_or_delay:
  - "root cause unknown"
final_approver: "human + verifier"
```

禁止只用“文件创建”“工具注册”“Agent 自述完成”作为里程碑完成标准。

---

## 6. 任务规格书标准

任务规格书中的每个任务必须能被拆成任务 YAML。任务 YAML 至少包含：

```yaml
id: M2.2-SAFE-MESH-OP-LEVELS
phase: 2
milestone: M2.2
priority: P0
title: "Implement operation levels"
status: pending
assigned_to: null
source_docs:
  - ".omo/plans/archive/phase2-task-specs-v2.md"
depends_on:
  - "M2.0-PHASE1-GOVERNANCE-CLOSE"
risk_level: L2
operation_level: L2
human_approval_required: true
entry_gate: []
evidence_required:
  - "L2 write denied without confirmation"
  - "confirmation path audited"
test_plan:
  - ".omo/tests/README.md#operation-level-tests"
```

---

## 7. 交付标准

每个交付物必须归入以下类型之一：

| 类型 | 交付证据 |
|------|----------|
| 文档治理 | 文档状态更新、索引同步、一致性检查 |
| 架构设计 | 边界表、依赖图、失败模式、门禁 |
| 任务规格 | 可拆成 YAML 的任务、依赖、验收 |
| 代码能力 | 测试、日志、健康指标、回滚策略 |
| 连接器 | 权限、数据分类、dry-run、审计、隐私边界 |
| Agent 能力 | 身份、RBAC、sandbox、checkpoint、deadlock test |
| 数据能力 | 数据量基线、完整性校验、备份/恢复证据 |

---

## 8. 测试标准

所有 Phase 的测试必须分为五层：

1. **Spec tests**：文档和 YAML schema 是否完整。
2. **Unit tests**：单包/单模块行为。
3. **Integration tests**：跨项目、跨包、跨 Agent 的主路径。
4. **Failure-injection tests**：网络不可达、索引退化、权限拒绝、Agent 死锁。
5. **Acceptance tests**：用户可见闭环和人工验收。

Phase 2 起，任何 P0/P1 任务至少需要：

- 一个成功路径证据。
- 一个失败/拒绝路径证据。
- 一个审计或健康指标证据。

---

## 9. Phase 2 执行口径

Phase 2 不是“47 个任务全部启动”，而是：

```text
M2.0 governance close
  -> M2.1 KOS baseline
  -> M2.2 Safe Mesh
  -> M2.3 SSOT 7-domain minimal registration
  -> M2.4 real knowledge loop
  -> M2.5 expansion review
```

在 M2.0-M2.2 完成前，以下任务只能保持 `candidate`：

- Apple / WeChat / SMB / media 等敏感连接器。
- KOS self / 高自主自愈。
- Family OS、设备协同、跨域自动研究。
- 破坏性备份/恢复操作。

---

## 10. Go/No-Go 口径

| 决策 | 条件 |
|------|------|
| `NO-GO` | Phase 目标源、任务源、状态源冲突；或关键安全门禁缺失 |
| `LIMITED-GO` | 允许治理/KOS/安全类 P0 任务启动，禁止敏感连接器 |
| `GO` | 关闭前序 Phase，任务 YAML 完整，测试和审计证据存在 |

当前建议状态：

```text
Phase 1 = code_complete + runtime_evidence_pending
Phase 2 = limited_go_for_M2.0_M2.1_M2.2
```
