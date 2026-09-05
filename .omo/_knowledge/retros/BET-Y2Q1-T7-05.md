---
schema_version: retrospective/v1
type: retro
title: BET-Y2Q1-T7-05 Closeout Retro — calibration 与五档 tier 语义统一
bet_id: BET-Y2Q1-T7-05
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y2Q1-T7-05 Closeout Retro

> **TL;DR**: T7-03 (commit 7494bb127) 已把场景卡存储归一到 `docs/scene-cards/`, review 工具 (bin/ssot/scene-card-review.py) 和 lifecycle 标准 (.omo/standards/scene-card-lifecycle.yaml) 都从同源读 5 档 tier + calibration 字段。本 bet 是 文档 closeout: 写 T7-05 专用 spec (因 T7-03 spec 走 T7-03 bet_id), 添加 spec binding + CE matrix, flip status candidate→done。verify: scene-card-review status 跑过 (lifecycle=assisted, 与 5 档枚举一致), gac-local-gate PASS。

## Deliverables

- `docs/superpowers/specs/2026-09-05-t7-05-calibration-tier-unification.md` — T7-05 专用 spec (38 行, 4 段: 目标 / In scope / Out / 验收)
- `docs/plans/3y-bet-ledger.yaml` — T7-05 补 accepted_specifications + 调整 write_surfaces + flip status
- `.omo/_knowledge/retros/BET-Y2Q1-T7-05.md` — 本 retro

## Q1 实际耗时 vs appetite?

Appetite 1 day。本轮 ~20 min (T7-03 的实现早完成, 本轮只补 spec + retro + ledger closeout)。

## Q2 done_when 是否全部通过?

| 条目 | 结果 |
|------|------|
| scene-card-lifecycle 标准文件写明 calibration 字段的角色 | **PASS** (T7-03 已固化 min_calibration: 0.6 for assisted 升级) |
| review 工具的 promote/weekly-review 输出与五档枚举一致 | **PASS** (scene-card-review.py status 输出 lifecycle=assisted, 与 5 档 draft/shadow/assisted/supervised/routine 一致) |

## Q3 过程中发现的与 plan 不符的事实（打假）?

1. **实现早已完成**: T7-03 PR #3226 (commit 7494bb127) 已经把场景卡存储归一, review 工具和 lifecycle 标准都从 `docs/scene-cards/` 读 5 档 + calibration。本 bet 实际只是 "在 ledger 里登记" 的 closeout 工作, 不需要改代码。

2. **Spec 复用陷阱**: T7-05 的 CE matrix 引用 T7-03 的 spec (因为两者目标相近), 但 `agent-workflow start` 严格校验 spec frontmatter `bet_id` 必须等于 BET id。修法: 写一份 T7-05 专用 spec (38 行), 与 T7-03 spec 互不冲突。

3. **bet-ledger start 校验严格化**: 这套工作流持续在收紧, 早期 closeout 不会要求 spec binding, 现在要求了。T7-05 第一次 start 失败 `SPEC_BINDING_REQUIRED`, 加 binding 后失败 `SPEC_FRONTMATTER_BET_MISMATCH`, 加 T7-05 专用 spec 后通过。**教训**: 每个 BET 写自己的 spec, 不复用其他 BET 的 spec 文件。

4. **5 档 tier 单一 SSOT 状态**: 跨工具同源 = `docs/scene-cards/<id>.yaml` 里的 `lifecycle` 字段; calibration 是数值辅助, 升级门是 `readiness` (T7-02 固化)。两套语义不冲突, 只是需要在标准里明确分工。这是本 bet 的实质内容 (写明在 spec 的 In scope §1), 但不需要改任何代码。

## Q4 净增减

- 新文件 2: spec (38 行), retro
- 改文件 1: docs/plans/3y-bet-ledger.yaml (T7-05 entry)
- 工作区代码: 0 改动 (实现面早 ship)

## Q5 下一个认领本 track 的 agent 需要知道什么?

1. **T7-05 是 "语义分工" 类 bet**: 5 档 tier + calibration 字段同源, 但分工 = tier 是 SSOT 状态, calibration 是 readiness 参考。这种 "类比 1 个字段多个角色" 的清理模式未来可能再出现 (例如 observation/eval/score 三字段)。

2. **CE matrix 可以指向 T7-03 retro 作为 proxy**: 因为 T7-05 的实质语义由 T7-03 实现, retro 只指向 T7-03 是合理选择 (替代: 写新 retro 解释两 bet 关系)。本 bet 选了后者 (写新 retro + 解释"实现早已完成" + 引用 T7-03 PR #3226)。

3. **不要复用其他 BET 的 spec 文件**: agent-workflow start 严格校验 frontmatter bet_id, 必须每个 BET 有自己的 spec。即便是姊妹 bet 或续写, 写新 spec 是规范。

4. **T7-03 后的 follow-up 链**: T7-04 (omo 死链清理 + ecos 第四家存储) → T7-05 (本文) → 未来 T7-06+。T7-04 也在 candidate 池, 是当前 P3 候选。

## Closeout refs

- run: `20260905T233228Z-project-doc-change-96626bcc`
- branch: `work/bet-y2q1-t7-05`
- spec: `docs/superpowers/specs/2026-09-05-t7-05-calibration-tier-unification.md` (accepted, T7-05 专用)
- prior delivery: PR #3226 (T7-03, commit 7494bb127) by another agent — 实现早已完成
- verify: `bin/ssot/scene-card-review.py status inbox-to-decision` exit 0 + lifecycle=assisted; gac-local-gate
- dependency: T7-02 (readiness 门) + T7-03 (存储归一)
- 被依赖: 未来 T7-06+ (层级同源化趋势)
