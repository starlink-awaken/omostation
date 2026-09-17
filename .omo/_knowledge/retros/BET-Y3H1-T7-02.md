---
bet_id: BET-Y3H1-T7-02
date: 2026-09-17
lifecycle: history
last-reviewed: 2026-09-17
status: archived
owner: governance-team
title: BET-Y3H1-T7-02 Retro — 公文场景 assisted 升档
type: retro
---

# BET-Y3H1-T7-02 Retro — 公文场景 assisted 升档

> **状态**: archived (BET done, 2026-09-17 closeout)

## Q1 实际耗时 vs appetite

- appetite: 1 week
- 实际耗时: ~1 day (2026-09-17, 跨 4 PR)
- 偏差: 远快于预期。Phase 1 calibration 与 Phase 2 E2E 可复用现有 journey-runner 基础设施，Phase 3 lifecycle transition 为纯 CLI 操作。主要耗时在 Phase 2 脚本开发（e2e-verify-phase2.py + journey-runner JSON 解析）和 Phase 3 readiness 前置条件（trial_recorded 需写入 shadow-scene-trials.jsonl）。

## Q2 done_when 通过情况

| # | done_when | 状态 | 说明 |
|---|---|---|---|
| 1 | lifecycle 从 supervised 升至 assisted | ✅ | scene-card-lifecycle.py transition --tier assisted; lifecycle=assisted, activation=controlled |
| 2 | calibration >= 0.6 且连续 30 次无 rejected | ✅ | calibration=0.9 (≥0.6), 30/30 样本全通过, 0 rejected |
| 3 | ≥ 3 份 admin-notification 公文通过全链 | ✅ | 3/3 公文全链通过, 15/15 检查项达标 (full_chain, checkpoint, steps≥5, reflection, final_context) |
| 4 | Workflow Mesh 证据链完整 | ✅ | 3 份 trial 记录写入 shadow-scene-trials.jsonl (journey_id=inbox-to-decision, mode=dry_run, status=completed) |

## Q3 打假 / 与 plan 不符的事实

- **e2e-verify-phase2.py 需新开发**: spec 假设已有 E2E 验证能力，实际需新建脚本（journey-runner 无批量验证入口）
- **journey-runner JSON 输出含换行+空格**: `{` 后紧跟 newline+whitespace 再是 `"checkpoint"`，初始正则 `\{"checkpoint"` 匹配失败，须改为 `\{\s*"checkpoint"`
- **trial_recorded 前置条件**: lifecycle transition 要求 shadow-scene-trials.jsonl 中存在匹配 scene_id 的 trial 条目，非自动填充。Phase 3 执行前须手动追加 3 条 trial 记录
- **gitignore 阻碍**: .omo/state/ 和 .omo/_knowledge/workflow-mesh/ 均在 gitignore 中，`git add` 须用 `-f` 强制添加
- **script-registry 须同步**: 新增 bin/*.py 须同步注册到 bin/_registry/scripts/governance/<name>.yaml，否则 gac-gate script-registry-validate FAIL

## Q4 净增减

- **新增代码**:
  - `bin/e2e-verify-phase2.py` — Phase 2 E2E 验证脚本（run+resume 模式, 5 项检查）
  - `bin/_registry/scripts/governance/e2e-verify-phase2.yaml` — script-registry 注册
- **新增文档/资产**:
  - `.omo/state/e2e-phase2.json` — E2E 验证报告 (3/3 通过, 15/15 检查项)
  - `docs/superpowers/specs/2026-09-17-t7-02-assisted-escalation-design.md` — 3-phase spec 设计文档
- **新增治理资产**:
  - `.omo/_knowledge/workflow-mesh/shadow-scene-trials.jsonl` — 3 条 document-review trial 记录
  - `completion_evidence` — completion-evidence-matrix/v1 三轴补全 (engineering VERIFIED, operational PROVEN, value NOT_PROVEN, overall_state=delivery_accepted)
- **修改**:
  - `.omo/_truth/scenarios/v3/scene-document-review.yaml` — lifecycle: supervised→assisted, activation: active→controlled
  - `docs/plans/3y-bet-ledger.yaml` — status: in_progress→done, completion_evidence 补全, value_indicator_policy: false

## Q5 下一个认领本 track 的 agent 需要知道什么

- 本 BET 基于 T7-02 调研结论 (admin-notification-workflow 为最佳第二业务驱动, 100% 兼容)
- Y3H1-T7-01 / Y3H2-T7-01 维持 blocked 不应复活 — T7-02 已交付, 解冻须新建 BET
- 若 assisted 运行稳定 → 可新建 BET 推进到 routine (限定格式类公文场景)
- lifecycle 升级路径: draft→shadow→assisted→supervised→routine, 当前 assisted 为受控激活 (controlled tier)
- shadow-scene-trials.jsonl 是 readiness 硬性前置条件, 新场景升档前须先写入 trial 记录
- journey-runner 的 human_review checkpoint 机制: run 返回 run_id, resume 续行, 非同步阻塞
- scene-card-lifecycle.py 完整命令: check (readiness 4 前置条件) / transition (tier 变更) / validate (schema) / activate (激活)
