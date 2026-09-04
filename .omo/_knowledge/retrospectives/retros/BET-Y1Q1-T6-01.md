---
lifecycle: history
owner: governance-team
bet: BET-Y1Q1-T6-01
last_updated: 2026-08-15
title: BET-Y1Q1-T6-01 复盘
type: retro
---

# BET-Y1Q1-T6-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
Appetite 3 days。本轮在隔离 worktree `work/bet-y1q1-t6-01` 一次落地 grill 已锁项，未超 3 天。

## Q2 done_when 是否全部通过？哪条没过，为什么？
- Plan 主线 + Panorama superseded：是（ADR-0410）
- STRATEGY-INDEX 北极星/主方案：是
- ADR-0410 登记：是
- research-pipeline ID 只留 scene-card：是（_truth 改为 research-pipeline-legacy）
- 场景卡顶层 status 不再对 preview 声称 active：是
- 悬空 journey_id：已改 document-review/unified-inbox/research-pipeline；knowledge-curation 与 engineering-delivery 无对应文件，标 `journey_unresolved` 而非伪造 journey-spec

## Q3 过程中发现的与 plan 不符的事实（打假）？
- 落地包建议的 `BET-Y1Q1-T6-DOC-CONVERGE` 与台账数字编号不合，已改为 `BET-Y1Q1-T6-01`。
- `docs/project-registry.yaml` 的 196 vs 200 都过时；2026-08-15 读 `bos-services.yaml` 实为 223（active 191）。
- 既有 `docs-strategy-convergence-2026-08` worktree 已 prunable，不能复用。
- T6-SUBTRACT exclusive 当时无 in_progress，可登记。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
- ADR +1（0410）
- 总纲+落地包入库 +2
- _truth scenario 改名 1（非净增权威 ID）
- 未新增 GaC 规则、未新增脚本
- 跟踪 BET-Y1Q1-T6-02 仅 candidate，映射表未写（Q6=A）

## Q5 下一个认领本 track 的 agent 需要知道什么？
- 不要把 T6-02 标 done，除非真有 `docs/architecture/wave-gate-bet-map.md`。
- D3/D5 未授权。
- `status: stale` 的四份二代文档需要内容级重读，不是再打 metadata-only。
