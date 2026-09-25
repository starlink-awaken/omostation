---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: retro
bet_id: BET-Y3H1-T7-03
date: 2026-09-17
title: BET-Y3H1-T7-03 Retro — document-review routine 推进
---


# BET-Y3H1-T7-03 Retro — document-review routine 推进

> **状态**: archived (BET done, 2026-09-17 closeout)

## Q1 实际耗时 vs appetite

- appetite: 1 week
- 实际耗时: ~2 hours (2026-09-17, 跨 3 PR)
- 偏差: 远快于预期。Step 1-2 lifecycle transition 为纯 CLI 操作 (scene-card-lifecycle.py transition)，trial records 为 JSONL 追加。主要耗时在 CI 等待 (每 PR ~5 min) 和 worktree 创建 (子模块初始化 ~5-7 min)。

## Q2 done_when 通过情况

| # | done_when | 状态 | 说明 |
|---|---|---|---|
| 1 | lifecycle 从 assisted 升至 routine | ✅ | assisted→supervised (PR #3871) → supervised→routine (PR #3875) |
| 2 | activation 从 controlled 升至 allowed | ✅ | controlled→monitored→allowed (两步同步) |
| 3 | ≥ 6 条 trial records (3 assisted + 3 supervised) | ✅ | 9 条总计 (3 E2E + 3 assisted + 3 supervised), 每条 steps=7 |
| 4 | readiness 4 前置条件全绿 | ✅ | 2 次验证 (Step 1 前 + Step 2 前), 全绿 |

## Q3 打假 / 与 plan 不符的事实

- **scene-card-lifecycle.py transition 需要 --actor 参数**: spec 未提及，首次执行失败
- **journey_ref 已从 inbox-to-decision 改为 journey-document-review**: PR #3861 修复了声明与执行不一致问题，trial records 须用 journey-document-review
- **shadow-scene-trials.jsonl 在 gitignore 中**: `git add` 须用 `-f` 强制添加
- **completion_evidence 须用 4-key × 2-axes 格式**: 布尔 shorthand (code_landed: true) 会 FAIL，须 {key: {ref: '...'}} 结构 (BET-Y3H1-T7-02 踩坑实证)
- **T7-02 retro 中 Q5 建议**"若 assisted 稳定 → 可新建 BET 推进 routine" — 本 BET 即为该建议的执行

## Q4 净增减

- **新增代码**: 无 (纯配置/文档变更)
- **新增文档/资产**:
  - `docs/superpowers/specs/2026-09-17-t7-03-routine-promotion-design.md` — 3-step spec 设计文档
  - `.omo/_knowledge/retros/BET-Y3H1-T7-03.md` — retro (archived, Q1-Q5 全量填充)
- **新增治理资产**:
  - `shadow-scene-trials.jsonl` — 6 条新 trial 记录 (3 assisted + 3 supervised)
  - `completion_evidence` — completion-evidence-matrix/v1 三轴补全 (engineering VERIFIED, operational PROVEN, value NOT_PROVEN, overall_state=delivery_accepted)
- **修改**:
  - `.omo/_truth/scenarios/v3/scene-document-review.yaml` — lifecycle: assisted→routine, activation: controlled→allowed
  - `docs/plans/3y-bet-ledger.yaml` — status: in_progress→done, completion_evidence 补全

## Q5 下一个认领本 track 的 agent 需要知道什么

- 本 BET 基于 BET-Y3H1-T7-02 (assisted 升档) 的调研结论 — T7-02 retro Q5 建议
- document-review 场景卡 lifecycle 全链完成: draft→shadow→assisted→supervised→routine
- 限定范围: 仅格式类公文 (GB/T 9704-2012)，非格式类需另开 BET
- admin-notification-workflow 驱动 5-20 件/天，100% 兼容
- circuit_breaker: 连续 3 次校准 < 0.4 → 回退 supervised
- Y3H1-T7-01 / Y3H2-T7-01 维持 blocked 不复活
- lifecycle 升级路径: assisted→supervised→routine (不可跳步), 每步需 trial records + readiness 4 前置条件
- scene-card-lifecycle.py 完整命令: check (readiness) / transition (--tier, --actor) / validate (schema) / activate (激活)
- shadow-scene-trials.jsonl 在 gitignore 中，须 `git add -f`
