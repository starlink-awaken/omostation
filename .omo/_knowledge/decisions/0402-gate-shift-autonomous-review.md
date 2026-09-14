---
id: ADR-0402
status: active
lifecycle: spec
owner: '@Builder'
last-reviewed: '2026-08-09'
type: ssot
---

# ADR-0402: 门禁后移与自主审查架构

- status: accepted
- date: 2026-08-08
- owner: architecture-team
- related: ADR-0400 (DoD), action-permission-matrix.yaml, gac-worktree.sh

## Context

自主迭代系统遇到"提议-执行鸿沟"——系统能感知→分析→提议，但在"执行"这一步卡住，
5个能力域标记为⚠️部分达成。根因：门禁在提议阶段（前置审批），导致系统无法自主行动。

## Decision

**门禁从提议阶段后移到合并阶段（Gate Shift）**:

1. 系统在worktree沙盒里自由执行（三级名单控制安全边界）
2. 执行后submit PR，由PR审查矩阵（6维度+心智模型）审查
3. 全approve → 自动merge；有reject → block；needs_human → 人审

**三级名单**:
- 白名单: 自动执行（规则降级/工具归档/ADR草稿等确定性变更）
- 灰名单: AI心智模型判断→提级或拒绝
- 黑名单: 禁止（删除核心/修改门禁/修改名单本身）

**PR审查矩阵**:
- risk/security/architecture/policy/function 5个维度agent
- mental_model agent综合裁决（读TELOS+MOS beliefs+历史审批）
- 裁决: 全approve→auto_merge / 有reject→block / needs_human→提级

## Drivers

- worktree隔离体系(PASW)已存在，直接复用
- PR流程已存在，审查矩阵是自然扩展
- 用户明确要求"门禁后移"（grill-me决策#1）
- 三级名单设计来自用户（grill-me决策#5）

## Consequences

- **正面**: 系统获得worktree内完全自主权，从70%→~90%自主度
- **正面**: 人只审needs_human的PR，审批效率×10
- **正面**: Trust动态调整→名单级别自适应→权限随经验扩展
- **负面**: PR审查矩阵的判断力依赖启发式（初期可能误判）
- **约束**: 黑名单项永远不能自主（自我保护）

## Follow-ups

- [ ] T4: signal-poller事件驱动触发（粗粒度，后续实现）
- [ ] PR审查矩阵的mental_model agent接入真实TELOS评估
- [ ] 积累Trust数据后逐步提频（每日→每小时→事件驱动）
