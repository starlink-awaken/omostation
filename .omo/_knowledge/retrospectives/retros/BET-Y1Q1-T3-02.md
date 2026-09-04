---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T3-02 复盘
type: retro
---
# BET-Y1Q1-T3-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 3 days。随 T3-01 三表落地后接入裁决与场景结果写面，约 2-3 天，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| scenewatcher.py 每次 evaluate_confidence 写一条 decision_outcome 到 MOS | ✅ 裁决写面在 omo_adjudication.py (decision_id do-NNNN) + scene-outcome-recorder.py (_write_mos_n) |
| 进程重启后可查询历史决策 | ✅ decision_outcome 表持久化 |
| docstring 与实现一致(无未兑现声称) | ✅ doc-claim-lint 校验 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **「决策日志入 MOS」曾是 docstring 声称但代码未做**（deep-review 实证）: ln.py 声称三处「决策日志入 bos://memory/mos/*」，实际无 MOS 调用。本 bet 通过 omo_adjudication + scene-outcome-recorder 把裁决/场景结果真写 decision_outcome 表闭环。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- omo_adjudication.py (AdjudicationRecorded 关联 decision_id)
- scene-outcome-recorder.py _write_mos_n 写面
- doc-claim-lint 校验接线
- 无新增 GaC 规则

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. 决策结果写 MOS 有两条路径: 裁决 (omo_adjudication) 与场景结果 (scene-outcome-recorder)。
2. 声称「写入 MOS」前先 doc-claim-lint 验证实现存在（deep-review 打假教训）。
3. decision_id 格式 do-NNNN，可关联回 decision_outcome 表。
