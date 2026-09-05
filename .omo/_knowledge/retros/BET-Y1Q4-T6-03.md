---
schema_version: retrospective/v1
type: retro
title: BET-Y1Q4-T6-03 Closeout Retro — gitlink drift guard + sync SOP
bet_id: BET-Y1Q4-T6-03
status: archived
lifecycle: contract
owner: governance-agent
created: 2026-09-05
last-reviewed: 2026-09-05
---

# BET-Y1Q4-T6-03 Closeout Retro

> **TL;DR**: 交付物已在 tip（`#3115` / `cb8570627`）：gate 具备 `--drift-check` / `--auto-fast-forward`，SOP 已落盘。本 closeout 仅登记 `delivery_accepted`、补 retro，并把 ledger `write_surfaces` 扩到 ledger+retro。accepted spec 的 done_when 是 gate+SOP；ledger 文案里的 pre-commit hook 接线未做，记为 follow-up。

## Deliverables (already on tip)

- `bin/ssot/submodule-reachability-gate.py` — `--drift-check` + `--auto-fast-forward`
- `docs/architecture/submodule-sync-sop.md` — submodule 同步 SOP
- `docs/superpowers/specs/2026-09-04-submodule-gitlink-drift-guard-spec.md` — accepted spec（gate+SOP）
- `docs/plans/3y-bet-ledger.yaml` — closeout：status=done + completion_evidence + write_surfaces 扩权

## Q1 实际耗时 vs appetite？

Appetite 1 day。实现已在此前合入 tip；本会话仅为 closeout（workflow / claim / retro / evidence bind），约 0.5–1h。

## Q2 done_when 是否全部通过？

| 条目（权威面） | 结果 |
|------|------|
| accepted spec：gate 增加 gitlink drift 快速检测 | PASS（`--drift-check` 已在 tip） |
| accepted spec：auto fast-forward 到 gitlink SHA | PASS（`--auto-fast-forward` 已在 tip；失败即停） |
| accepted spec：文档记录 submodule 同步 SOP | PASS（`docs/architecture/submodule-sync-sop.md`） |
| verify：`python3 bin/ssot/submodule-reachability-gate.py --source index` | PASS（exit 0） |
| ledger 文案：pre-commit hook 增加 gitlink drift 快速检测 | **DEFERRED**（相对 accepted spec 更宽；未接线，见 Q5） |

说明：spec 合同（accepted）优先于 ledger `done_when` 松散表述；本 bet 按 spec 的 gate+SOP 验收关闭。

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **交付已在 tip**：`feat(submodule): gitlink drift防护 + sync-check强化 (BET-Y1Q4-T6-03) (#3115)`，无需再改 gate/SOP 本体。
2. **ledger `done_when` 比 spec 更宽**：提到 pre-commit hook 接线；spec 只要求 gate 能力 + SOP。按用户约束不扩 scope。
3. **初始 `write_surfaces` 缺 ledger/retro**：claim 触发 `WORK_PACKET_SCOPE_MISMATCH`。先扩 write_surfaces 再 restart run，才能 claim closeout 写面。
4. **value 轴保持 `NOT_PROVEN`**：本 bet 无 value indicator 证明义务；`overall_state=delivery_accepted`。

## Q4 净增减

- 本 closeout 新增：1 份 retro；ledger 状态/证据/write_surfaces 更新
- gate / SOP：0 行功能增量（已在 tip）
- pre-commit / GaC 规则：0（故意不扩）

## Q5 下一个认领本 track 的 agent 需要知道什么？

1. **不要**再以 T6-03 名义重做 `--drift-check` / SOP；它们已在 main tip。
2. **Follow-up bet 候选（勿在本 closeout 发明 ledger id）**：将 gitlink drift 检测真正接到 **pre-commit / sync-check hook**（ledger 原 `done_when` 的 hook 接线缺口）。可按 `BET-Y1Q4-T6-04` 风格单独立项；需新 accepted spec + write_surfaces（`.pre-commit-config.yaml` / hook 脚本）。
3. SOP 已写明 pre-push/CI 用法；hook 常态化属于下一棒，不是本 bet 返工。
4. 任何再改 gate/SOP/retro 的后续 bet，必须刷新引用它们的 `completion_evidence` digest。

## Closeout refs

- run: `20260905T000636Z-project-code-change-fabf5ccb`
- branch: `work/bet-y1q4-t6-03`
- delivery_on_tip: `cb857062748c60cc7aa48d370e077cfb464cdb13` (#3115)
- prior_run_closed: `20260905T000242Z-project-code-change-e4d3fad2`（write_surfaces 扩权重启）
