---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0117-p52-undo-p60-stage-8.md
  - 0115-p52-model-driven-8-stages.md
  - 0132-l0-mof-m4-metamodel.md
  - 0136-m3-yaml-extension-p5.md
  - 0138-meta-element-promotion.md
  - ../../../projects/model-driven/src/model_driven/mof/m3_extended.py
  - ../../../projects/ecos/src/ecos/ssot/mof/m3.yaml
supersedes: []
---

# ADR-0139: model-driven 8 阶段复活评估 — 拒回 (Round 2c)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。
> **决策**: 不复活 8 阶段, 维持 ADR-0117 撤销生效。

---

## 0. TL;DR

Round 2c 评估结论:**拒绝**复活 model-driven 第 8 阶段 (GOVERNANCE_MAINTENANCE)。
ADR-0117 撤销决定今天仍然成立, 且 M4 闭合后该决定更坚实 — 不是更脆弱。

**关键论点**:
- 7 阶段足够表达业务生命周期
- governance 职责由治理层 (governance-team + project-registry + GacRule + GaC gate) 履行, **不归业务 lifecycle 模型**
- M4 元模型闭合后 (m3.yaml 34 element + 4-check strict PASS), governance 自闭环已系统化, 无需业务模型再承载
- 复活 8 阶段会触发 P52 ADR-0117 已经实证的"撤销 1 改烧 15 测试 fail" 历史风险

---

## 1. 评估触发

Round 2 (after ADR-0132 ~ 0138) 完成后, 模型基础已重整:
- m3.yaml 7 大类 (新增 MetaElement)
- 4-check strict 0/0/0/0
- 38 回归测试 38/38 PASS
- 8+4+4 MetaType/MetaRelation/MetaConstraint 提升到 m3.yaml 主根 (ADR-0138)

自然涌现问题:**M4 闭合后 governance 是否需要重新纳入 business lifecycle**?
具体表现为: **model-driven 第 8 阶段 GOVERNANCE_MAINTENANCE 是否应该复活**?

P60 (2026-06-24) 添加 → P52 ADR-0117 (2026-06-25) 撤销 → 现在 (2026-07-06) 评估。

---

## 2. 历史脉络回顾

### P60 添加 (2026-06-24)

P60 governance internalization 提案在 `.omo/_knowledge/audits/2026-06-23-p60-governance-internalization-proposal.md`:

- 提议把 governance 纳入 LifecycleStage 第 8 阶段
- 实施 commit `87b7914`: `projects/model-driven/src/model_driven/mof/m3_extended.py` +
  `LifecycleStage.GOVERNANCE_MAINTENANCE` enum value +
  对应 m3_extended Stage mapping

### P52 撤销 (2026-06-25)

ADR-0115 (8 阶段接受) → ADR-0117 (撤销)。理由 4 条:

1. governance 横切所有 Y 阶段 (business), 属于 X 轴治理框架
2. 模型-driven 7 阶段是业务 Y 轴, 加 governance 破坏 5+4+1+1 分层
3. 治理维护职责应归 aetherforge/c2g/bus-foundation 等 X 框架 (而非 model-driven 业务模型)
4. P60 错塞破坏 m3 自反, 实测 15 测试 fail (ADR-0117 §1)

撤销提交 `ad90c48 + 036b833a`。

### 当前现状 (2026-07-06)

model-driven `LifecycleStage` 仍 7 阶段 (已撤销 8)。
ADR-0117 撤销决定生效, governance 维护归:
- 治理 Agent (governance-agent profile in `agent-workflows.yaml`)
- projects/omo governance kernel
- GaC rules engine (`bin/gac-local-gate.py`)
- X 轴 governance framework (aetherforge/c2g/bus-foundation)

---

## 3. Round 2c 评估

### 论据 1: 7 阶段足够

业务 lifecycle 7 阶段是 PLANNING → BUSINESS_OPS 的线性流水。每个阶段有:
- entry_criteria
- exit_criteria
- deliverables

这是**业务制品流动模型**,governance 维护不是 business deliverable。
把 governance 塞入 7 阶段会让 exit_criteria 出现 "验证 GaC gate PASS" 这种 Y 轴 + X 轴混杂。

### 论据 2: governance 自闭环已系统化

M4 闭合后:
- GaC 132 规则 (gac_validate)
- 38 回归测试 (round-trip 验证)
- 4-check strict 自反 (m3.yaml / m2/*.yaml / m2→m3 / m3-meta)
- 5 个 ACCEPTED ADR (0132..0138) + 2 个新加 (0137+0138)
- 新加 `mof-bootstrap.py` CLI 工具

**governance 维护职责已经被 X 轴 framework 完整覆盖**,无需在 business Y 模型加阶段。

### 论据 3: m3.yaml 现在有 GovernanceElement 元类

m3.yaml 第 3 大类 `GovernanceElement` 已经涵盖:
- Constraint / Policy / Pattern / Specification / GacRule (P74/ADR-0130) / Decision / **ConstraintL0** (M4)
- dimension: [X1, X2, X3, X4]

governance 在 m3 语义层是第一类元素。无需再加 LifecycleStage 业务阶段。

### 论据 4: 历史教训

P60 错塞 → 实测 15 测试 fail → ADR-0117 撤销 → ci-python-coverage 恢复 green.
复活 8 阶段会重新触发"7→8 测试断言同步" 工作, 即便加 enum 同样需要更新 m2_lifecycle.py 268 个引用, model-driven mcp_server.py 等多处。

P72 红线: **不要为了可逆一致性重做一类历史踩坑 path**。

---

## 4. 不复活 — 决策

### 决策

维持 7 阶段 (PLANNING, DESIGN, DEVELOPMENT, DEPLOYMENT, RUNTIME, OPERATIONS, BUSINESS_OPS)。
ADL-0117 撤销决定仍然生效。
GOVERNANCE_MAINTENANCE 仍然是已撤销状态, 由 X 轴 framework 履行。

### 实施: 0 改动 (no-op)

- ❌ 改 `m3_extended.py`: 不动
- ❌ 改 `m3.yaml` Stage enum: 不动 (现 7 个值, 维持)
- ❌ 改 `model-driven/mcp_server.py`: 不动
- ❌ 改 268 处 lifecycle_stage 引用: 不动
- ❌ 改 `mof_bridge.py`: 不动
- ❌ 改 `mof_driven.py`: 不动

唯一改动: 写本 ADR 文档化决策。

### 反向 audit

未来若需要 governance lifecycle 表达,正确做法是:
1. 在 `m3.yaml GovernanceElement` 下加新子类 (例如 `MaintenanceCycle`)
2. m2 schema 用新 lifecycle engine (例如 `projects/omo/maint/`) 而非 `model-driven`
3. 与 X 轴 framework 通过 relationship (即 m3 relation type "maintains") 联系

**不是** 在业务 Y 轴 `LifecycleStage` 加阶段。

---

## 5. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| m3.yaml Stage enum 7 个 | `bin/mof-bootstrap.py check_1` | 0 err |
| model-driven 7 阶段 | `mof_driven --validate` | stage_count=7 |
| 38 测试不回归 | `tests/integration/m4_metamodel/run_all.py` | 38/38 PASS |
| ADR-0117 still in effect | grep "GOVERNANCE_MAINTENANCE" model-driven | 仅注释, 无活跃代码 |

### 不动证据

- `projects/model-driven/src/model_driven/mof/m3_extended.py::LifecycleStage` 仍 7 enum value
- `projects/ecos/src/ecos/ssot/mof/m3.yaml::Stage` properties.stage.values 仍 7 个
- 268 处 lifecycle_stage= 各 value 引用未触发变更

---

## 6. 不在本 ADR 范围

- ❌ 复活 P60 (Round 2c 决策明确拒绝)
- ❌ 把 governance 引入 model-driven 业务模型 (永不允许)
- ❌ 改 ADR-0117 (本 ADR 完全契合, 无需 supersede)
- ❌ 改 m3.yaml Stage enum (维持 7 值)

---

## 7. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (Round 0 决策)
- [ADR-0136](./0136-m3-yaml-extension-p5.md) (Round 0.5 P5 phase)
- [ADR-0138](./0138-meta-element-promotion.md) (Round 2b)
- [ADR-0117](./0117-p52-undo-p60-stage-8.md) (本 ADR 完全继承其论点)

---

## 8. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 2c, 拒绝复活 8 阶段, 维持 ADR-0117 撤销生效) |
