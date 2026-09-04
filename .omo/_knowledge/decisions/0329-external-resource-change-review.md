---
id: ADR-0329
title: 外部资源目录变化风险分类与人工复核投影
status: archived
type: decision
owner: architecture-governance
date: 2026-08-03
lifecycle: spec
last_updated: 2026-08-03
related:
  - ../../../docs/WORKFLOW-MESH-IMPLEMENTATION.md
  - 0319-external-resource-observation-surfaces.md
  - 0328-external-resource-catalog-freshness.md
---

# ADR-0329: 外部资源目录变化风险分类与人工复核投影

## 背景

目录观察已经能够告诉系统“资源发生了变化”，但 `changed_count` 无法区分 provider/权限/能力版本
变化与单纯 health 波动。动态扩展规模上升后，如果所有变化都同等处理，运营人员会被噪声淹没；
如果所有变化都自动放行，又会把 descriptor 变化误当作健康恢复。

## 决策

1. Agora diff 对每项变化增加 `review_required`、`risk_class` 和 `risk_codes`，并在 summary 中
   聚合 `review_required_count`、`operational_observation_count` 和稳定风险码。
2. 新增/移除资源，以及 provider、protocol、version、capabilities、mode、lifecycle、
   permission_ref、expires_at、review_at、rollback_plan 变化，统一归类为 `manual_review`。
3. 仅 availability、health、reason_codes 等运行观测变化归类为 `operational_observation`，不升级
   为 descriptor 复核事件。
4. OMO 观察记录持久化安全摘要，不创建第二套审批状态机，不自动改变 lifecycle、admission 或
   WorkflowRun。`manual_review` 只是复核要求，不是激活许可。
5. 后续产品复核入口必须消费同一份 diff 摘要；若要进入 active，仍需现有 Scene Card、权限、
   OMO admission、receipt 和回滚证据，不能凭风险分类结果越过边界。

## 验证

- Agora 外部连接：17 passed。
- OMO 外部资源观察：6 passed。
- 根仓外部资源目录：6 passed。
- Agora、OMO 和根仓变更文件 Ruff 与 `git diff --check` 通过。
