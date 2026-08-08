---
id: ADR-0396
title: 数字生命体架构 — 四论框架 × 四面一脊 × 五阶段演进
status: accepted
type: decision
owner: architecture-governance
date: 2026-08-08
lifecycle: active
last-reviewed: 2026-08-08
related:
  - 0387-dual-track-scene-admission.md
  - docs/DIGITAL-ORGANISM-ARCHITECTURE.md
  - docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md
---

# ADR-0396: 数字生命体架构

## Context

omostation从治理框架演进为数字生命体——具备感知/认知/执行/反思/进化能力, 渐进自主, 可扩展给家庭成员, 可形成蜂群。

## Decision

### 1. 四论框架 (理论约束)

| 理论 | 约束 | 工程映射 |
|------|------|---------|
| 系统论 | 结构 | namespace隔离 + Meta-0~3层次 + 涌现 |
| 信息论 | 信息流 | signal→info→knowledge→wisdom |
| 控制论 | 反馈 | Trust Policy(负) + 熟悉度(正) + 滑动窗口(阻尼) |
| 图灵论 | 计算 | journey=状态机 + checkpoint=人工Oracle |

### 2. 四面一脊 × 四层元架构

- ①感知面(信号) → ②认知面(MOS+Advisor) → ③执行脊柱(journey-runner) → ④结果面(outcome) → Meta-3进化(evolution-agent)

### 3. 五条收敛原则

1. Ashby必要多样性: 治理≥被治理
2. Shannon信息不减损: context只增
3. Wiener反馈阻尼: |Δtrust/日|≤0.05
4. Turing计算边界: 不可计算→人工
5. Autopoiesis进化治理: S1自动/S2确认/S3审批

### 4. 能力分层 (C1-C5)

C1观察(自主) → C2准备(自主) → C3沟通(积累) → C4系统(连接器) → C5交易(风控门禁)

### 5. Agent三层生态

常驻(感知/编排/参谋/治理) + 按需(文档/邮件/数据) + 涌现(模式→新agent)

### 6. 心智模型五层

Identity(慢) → Strategy(中) → Pattern(快) → Knowledge(持续) → Feedback(实时)
日轻量更新 + 周重量归纳

### 7. MOS agent_belief三表 (Keystone)

world_snapshot + capability_calibration + decision_outcome — 一切认知/决策/进化的数据基石

## Alternatives

- A: 扩展external catalog包含内部能力 → 语义污染 ❌
- B: 不建MOS, 手动approval → 不可审计 ❌
- C: 统一框架(一步到位) → YAGNI ❌

## Consequences

- MOS三表是Keystone, Phase 0优先建设
- 所有已有工具(outcome/reflection/feedback)桥接到MOS
- Advisor扩展SceneWatcher(不新建)
- 消息走Aetherforge(不新建bus)
- spec走MOF(不发明格式)

## Follow-ups

- 五阶段实施: Phase 0(接血管) → 1(建大脑) → 2(补领域) → 3(建进化) → 4(开放)
- 详见: `.omc/plans/digital-organism-implementation.md`
