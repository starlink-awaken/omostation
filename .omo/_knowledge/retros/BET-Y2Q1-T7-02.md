---
schema_version: retrospective/v1
type: retro
title: BET-Y2Q1-T7-02 Closeout Retro — shadow 试验记录机制
bet_id: BET-Y2Q1-T7-02
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y2Q1-T7-02 Closeout Retro

> **TL;DR**: PR #3215 已交付 journey-runner 落盘 + Check4 scene_id 精确匹配 (commit 8b8d2ab12)。本轮只做 ledger closeout: 补 spec binding (新写 spec, 因为 #3215 未含 spec)、加 CE matrix (含 4 文件 sha256)、写 retro、flip status candidate→done。verify 全绿: journey dry-run exit 0 + jsonl 追加 1 条 (含 admin-classify scene_id)、admin-classify scene-card check trial_recorded=true + ready=true、pytest 4/4 PASS。

## Deliverables (已 on tip via #3215)

- `bin/ssot/journey-runner.py` — completed run 追加 `.omo/_knowledge/workflow-mesh/shadow-scene-trials.jsonl`, mode 字段区分 dry_run/live, 失败 stderr 不阻断
- `bin/ssot/scene-card-lifecycle.py` Check4 — 从"文件级存在性"升级为"按 scene_id 精确匹配", 解析每个 jsonl 的 scene_ids 字段
- `tests/test_journey_runner_validate.py` — 4 单测覆盖 (empty / dry-run / live / 多 scene)
- `docs/plans/3y-bet-ledger.yaml` — T7-02 status done + CE matrix + spec binding
- `docs/superpowers/specs/2026-09-05-y2q1-t7-02-shadow-trial-record-design.md` — 本轮新写, 弥补 #3215 无 spec 的遗漏
- `.omo/_knowledge/retros/BET-Y2Q1-T7-02.md` — 本 retro

## Q1 实际耗时 vs appetite?

Appetite 1 day。实现已在 #3215 合入 (~30 min by another agent); 本轮 ledger closeout ~20 min (写 spec + CE + retro + flip status + PR)。

## Q2 done_when 是否全部通过?

| 条目 | 结果 |
|------|------|
| journey-runner 完成的 run 写入 shadow-scene-trials.jsonl (含 journey_id/run_id/mode/scene_ids) | PASS |
| Check4 按本卡 scene_id 精确匹配, 无试验记录的卡 trial_recorded=false | PASS (admin-classify trial_recorded=true; 其他未跑卡仍 false) |
| 实测 admin-notification-workflow 一次 dry-run 后 admin-classify readiness ready=true | PASS |

## Q3 过程中发现的与 plan 不符的事实（打假）?

1. **PR #3215 未含 spec**: 与 T1-10/HITL-01 模式相同 (实现先行 + closeout 后补)。本轮按 spec writing 标准补了 `docs/superpowers/specs/2026-09-05-y2q1-t7-02-shadow-trial-record-design.md`, digest 已写入 ledger CE matrix。
2. **`bet-ledger.py list --claimable` 崩溃**: #3223 引入的 BET-Y1Q4-T6-17/18/19 三个新条目使用新 schema (无 track/appetite/workflow 字段), `_claimable` 函数对所有候选做 `b["track"]` 访问时崩。本 bet 不修 (non_goal: 不修无关债); 但绕过方法是用 yaml 直读筛掉缺字段条目后定位本 bet。
3. **shadow-scene-trials.jsonl 是 gitignored 还是 tracked?**: 检查发现它在 `.gitignore` 里 (`*.jsonl` 模式 + `.omo/_knowledge/workflow-mesh/` 例外), 但实际 git ls-files 跟踪了 — 看来 workflow-mesh 例外接管。当前 jsonl 内容是 worktree 中 dry-run 生成的, CE matrix 的 sha256 是这一刻的快照, push 后别人 worktree 重新 dry-run 会变 hash, 但这是 operational evidence 的正常现象 (live_canary 必须为当下时刻)。
4. **run 单步 7 个 scene_ids 全覆盖**: 实测 dry-run admin-notification-workflow 一次, jsonl 记录的 scene_ids 列表 7 条 (admin-inbox/classify/forward/collect/compile/review/submit), 与该 journey 的真实 scene 拓扑完全一致。这证明 journey-runner 的 scene_ids 推导逻辑正确, 无遗漏。

## Q4 净增减

- 新文件 +2: spec (40 行), retro (本文件)
- 改文件 1: docs/plans/3y-bet-ledger.yaml (+CE matrix + binding + status flip)
- 实现面 0 改动 (#3215 已在 tip)

## Q5 下一个认领本 track 的 agent 需要知道什么?

1. **shadow→assisted 升卡前必须确认 jsonl 里有 scene_id**: 用 `grep "$scene_id" .omo/_knowledge/workflow-mesh/shadow-scene-trials.jsonl` 快速核对 (或依赖 scene-card-lifecycle Check4 自动校验)。
2. **mode 字段诚实**: 区分 dry_run 与 live 是 v1.1 候选; 当前已有字段但聚合统计未做, 后续 dashboard 可暴露 dry_run vs live ratio。
3. **三类试验日志**: shadow-scene-trials + internal-scene-trials + external-scene-trials; Check4 任一含 scene_id 即过, 不要假设只查第一类。
4. **.omo/_knowledge/workflow-mesh/ 是 gitignore 例外**: 该目录入仓, 但其下 `*.jsonl` 模式被 `.gitignore` 默认忽略; 这是有意的 (高 churn event 流) 但当前 shadow-scene-trials.jsonl 被跟踪, 是因为它是 shadow 升级的证据面。后续如果 jsonl 变成"快照式"而非"事件流", 可以脱离跟踪。
5. **T7-03 (场景卡存储归一) 是姊妹 bet**: 三套存储 (.omo/_truth/scenarios + scene-cards/ + workflow-mesh derived) 对账, human_gate=true; 本 bet 只覆盖其中一个写入方 (workflow-mesh 派生), 不解决归一。
6. **依赖**: 无上游依赖。**被依赖**: T7-03 / 未来的 readiness dashboard v2 可能引用本机制。

## Closeout refs

- run: `20260905T124127Z-project-code-change-b43973f0`
- branch: `work/bet-y2q1-t7-02`
- spec: `docs/superpowers/specs/2026-09-05-y2q1-t7-02-shadow-trial-record-design.md` (新写)
- prior delivery: PR #3215 (commit 8b8d2ab12) by another agent
- verify: journey-runner dry-run exit 0; admin-classify scene-card check trial_recorded=true + ready=true; pytest 4/4 PASS
- CE merged_reachable: `git://origin/main@8b8d2ab126a787a8790207f848a46e4fb17fb719`
