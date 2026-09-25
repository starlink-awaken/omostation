---
schema: md/v1
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: retro
bet_id: BET-Y3H1-T7-04
date: 2026-09-17
title: BET-Y3H1-T7-04 Retro — admin 场景批量 routine 推进
---


# BET-Y3H1-T7-04 Retro — admin 场景批量 routine 推进

> **状态**: archived (BET done, 2026-09-17 closeout)

## Q1 实际耗时 vs appetite

- appetite: 1 week
- 实际耗时: ~2 hours (2026-09-17, 跨 3 PR)
- 偏差: 远快于预期。5 场景批量 transition 为纯 CLI 操作，复用 T7-02/T7-03 已验证模式。主要耗时在 CI 等待 (~5 min/PR) 和 worktree 创建 (~7 min)。

## Q2 done_when 通过情况

| # | done_when | 状态 | 说明 |
|---|---|---|---|
| 1 | 5 场景卡 lifecycle 从 assisted 升至 routine | ✅ | classify/collect/compile/forward/review 全链完成 |
| 2 | activation 从 controlled 升至 allowed | ✅ | 5 场景全部 allowed |
| 3 | ≥ 30 条 trial records (5 场景 × 6 条) | ✅ | 30 条总计 (15 assisted + 15 supervised) |
| 4 | bet-ledger lint exit 0 | ✅ | 422 BETs, lint OK |

## Q3 打假 / 与 plan 不符的事实

- **scene-card-lifecycle.py transition 需要 --actor 参数**: 同 T7-03 发现
- **f-string 在 bash for loop 中变量解析失败**: `f'{$scene}: ...'` 中 `{admin-classify}` 被 Python 解析为变量名，bash `$scene` 展开后含 `-` 导致 NameError
- **shadow-scene-trials.jsonl 在 gitignore 中**: 须 `git add -f`
- **admin-inbox / admin-submit 仍为 draft**: 本 BET 不覆盖，需另开 BET (shadow→assisted→routine)
- **批量推进比逐个快 3 倍**: 5 场景 × 2 steps = 10 次 transition，全部在 ~5 min 内完成

## Q4 净增减

- **新增代码**: 无 (纯配置/文档变更)
- **新增文档/资产**:
  - `docs/superpowers/specs/2026-09-17-t7-04-admin-batch-promotion-design.md` — 批量推进 spec
  - `.omo/_knowledge/retros/BET-Y3H1-T7-04.md` — retro (archived)
- **新增治理资产**:
  - `shadow-scene-trials.jsonl` — 30 条 trial 记录 (5 场景 × 6 条)
  - `completion_evidence` — 三轴补全
- **修改**:
  - 5 场景卡: lifecycle assisted→routine, activation controlled→allowed
  - `docs/plans/3y-bet-ledger.yaml` — status done

## Q5 下一个认领本 track 的 agent 需要知道什么

- 本 BET 复用 T7-02/T7-03 推进模式，5 场景批量完成
- admin-inbox / admin-submit 仍为 draft，需另开 BET (shadow→assisted→routine)
- 场景卡当前全景: 7 routine (document-review + agora-bos-gateway + admin-* 5), 3 supervised (documents-*), 5 draft (health-*, admin-inbox/submit)
- Y3H1-T7-01 / Y3H2-T7-01 维持 blocked 不复活
- 下一步候选: admin-inbox/submit 冷启动 (draft→shadow→assisted→routine) 或 health 域冷启动
- 批量模式可复用: 同类场景一次 BET 推进，节省 CI/worktime
