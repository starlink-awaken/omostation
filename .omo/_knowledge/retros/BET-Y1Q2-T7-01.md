---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-12
---
# BET-Y1Q2-T7-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
本次 session 约 10 分钟，仅恢复配置，未完整交付。appetite 1 week。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| engineering-delivery 场景 lifecycle=shadow | ✅ 已恢复 (shadow/allowed/bet=Y1Q2) |
| 每周产出 >= 20 条 decision_outcome | ❌ 未验证。shadow 化后未经过足够观察周期，无法确认周产达标 |
| 明确标注"本场景产出永不计入价值指标" | ✅ value_indicator_policy 已标注 |

**不宣称 done**：周产20条条件未验证通过，需继续观察。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **merge regression**: commit e6a0fde1d 完成 shadow 配置后，后续 commit 将 lifecycle/activation 改回 active/active，并把 bet 从 Y1Q2 降回 Y1Q1。这是配置回退，不是有意变更。
2. **本次只恢复配置**：本次只恢复 shadow/allowed/bet=Y1Q2 + value_indicator_policy，不补周产20条的验证证据。
3. **verify 路径错误**: 台账 verify 指向 `docs/scene-cards/v2/engineering-delivery.yaml`，实际文件是 `docs/scene-cards/engineering-delivery-dogfood.yaml` (无 v2/ 子目录)。已修正。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本次净增:
- `docs/scene-cards/engineering-delivery-dogfood.yaml` 恢复 shadow/allowed + bet=Y1Q2 + value_indicator_policy + note
- `docs/plans/3y-bet-ledger.yaml` verify 路径修正 + notes
- `.omo/_knowledge/retros/BET-Y1Q2-T7-01.md` 本文件

无新增脚本 / GaC 规则 / ADR / 文件。最小配置恢复。

## Q5 下一个认领本 track 的 agent 需知道什么？
1. **shadow 配置已恢复**：lifecycle=shadow, activation=allowed, bet=BET-Y1Q2-T7-01, value_indicator_policy 已标注。
2. **周产20条未验证**：这是当前唯一未通过的 done_when。需要在 shadow 期间持续观察 decision_outcome 产出。
3. **不要把 lifecycle 改回 active**：上次就是这样被 regression 的。shadow 是当前正确状态。
4. **verify 路径已修正**: `docs/scene-cards/engineering-delivery-dogfood.yaml` (非 v2/ 子目录)。
