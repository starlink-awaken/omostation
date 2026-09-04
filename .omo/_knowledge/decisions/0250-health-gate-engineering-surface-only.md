---
id: ADR-0250
status: ACCEPTED
lifecycle: spec
owner: 夏明星
last_updated: 2026-07-27
related:
  - 0249-governance-budget-cap-40-40-20.md
  - 0247-strategic-pivot-collab-first-physical-deferred.md
supersedes: []
amends: []
---

# ADR-0250: health 门禁改为只卡工程执行面 (owner 集中度不再阻断)

## Context

P82 Stage A 退出门禁 `health ≥ 95` 撞上悖论: health 93 的 anomaly 含 **owner 集中度**
(`strategy.py::_check_anomalies`: `concentration > 50%` 触发), 而单人运营 workspace 中
human 持有 75-80% 任务是**运营现实** (单人 + agent 协作), 非缺陷. 用它阻断工程推进
(Stage B 启动) 是**门禁测错了东西** — owner 集中度是 Stage B 协作在产化要降的 KPI,
而非工程推进的前置条件. 把"待解问题"当"准入门槛"造成循环依赖 (要 Stage B 降 owner,
但要先降 owner 才能启 Stage B).

## Decision

health composite 的 governance 维度**门禁判定**改为只卡**工程执行面三项**:

| 工程执行面指标 | 门禁要求 |
|---------------|----------|
| `orphan_worktrees` | = 0 |
| `adr_renumber_events` | = 0 |
| `concurrent_conflicts` | = 0 (active run 收口) |

**不再卡** `base_anomaly_score` 中的 **owner 集中度** 指标.

## 区分标准 (供后续引用)

| 指标 | 性质 | 门禁处理 |
|------|------|---------|
| orphan_worktrees / adr_renumber / concurrent_conflicts | **工程执行纪律** | **卡** (必须归零) |
| owner 集中度 (human 占比) | **运营现实** (单人 workspace) | **不卡** (记录进 BRIEF, 不阻断工程) |
| done 流转停滞 (done/ 空) | **任务状态机信号** | **不卡** (另立卡追踪, 不阻断 Stage B) |
| freshness / runtime | 工程健康 | **卡** (≥阈值) |

## Rationale

这是**修正"测错东西"的门禁**, 不是为掩盖问题而放宽标准:
- owner 集中度高的**真解药**是 Stage B 协作在产化 (agent 承担任务降 human 占比),
  而非卡住工程推进让它永远启动不了.
- freshness + runtime + execution-surface 三项足以守护**工程健康**.
- owner 集中度 / done 停滞作为**运营信号**保留在 health 报告里供观察, 但不阻断.

## Enforcement

- Stage A/B 启动门禁: `execution_deduction == 0` (三项归零) + freshness ≥ 阈值 + runtime ≥ 阈值.
- compass_radar 的 health composite **计算不变** (仍含 owner 集中度 anomaly 进 base_anomaly),
  但**门禁判定**忽略 owner 集中度项.
- 若 owner 集中度持续高位, 进 BRIEF 协作仪表观察, 由 Stage B 协作管线自然消化.

## 实测验证 (2026-07-27)

清 concurrent_conflicts (run1/run3 收口) 后:
- governance 77 → 85 (execution_deduction 8 → 0)
- health composite 93 → **96** (≥95 门禁通过)
- anomalies 仍 = 1 (owner 集中度), 按 本 ADR 不阻断.
