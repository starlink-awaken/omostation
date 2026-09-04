---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q4-T3-01 复盘
type: retro
---
# BET-Y1Q4-T3-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 30 分钟（vs appetite 2 周）。实现已由并发 agent 完成（omo_autonomy_level.py），本 session 验证 done_when + 补事件 emit 显式测试。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 四级判据按硬门实现 (L1:20次观察 / L2:calibration>=0.6+30连 / L3:>=0.85+100连) | ✅ `PROMOTION_CRITERIA` 完整定义 (L0:20obs / L1:0.6+30 / L2:0.85+100), `_check_promotion` 硬门校验 |
| 升降级各产生一条 OMO 事件 | ✅ `_emit_event` 发 `autonomy.level_change` 事件; 本 session 补显式测试验证 (promotion/demotion 各触发一次) |
| 降级触发条件生效可测(注入 rejected 即降级) | ✅ 实测 L2→L0 (rejected) + requires_human_review=True; 测试覆盖 |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **实现已由并发 agent 完成**: main 上已有 `omo_autonomy_level.py` (338 行) + `omo_adjudication.py` 接线 (L197) + registry + 19 测试。本 bet 的实际缺口 = 事件 emit 的显式测试 (done_when 第 2 项), 现有测试只断言 level_changed 未验证 OMO 事件。
2. **额外有 drift 监控**: 实现还含 BET-Y2Q3-T3-02 的 drift monitoring (sliding window + human_review gate) — 超范围但已有。
3. **PASW 提交**: omo 子模块改动需走 projects/omo (detached) → .subtrees/omo → push → bump-pointer。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（omo 子模块 commit）:
- `tests/test_autonomy_level.py` +28 行: 2 个事件 emit 测试 (promotion/demotion) + 修复 1 个未使用变量

实现层 (omo_autonomy_level.py/omo_adjudication.py/registry) 由并发 agent 提供, 已在 main。无新增 GaC 规则 / ADR / bin 脚本。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **自主性阶梯位置**: `omo/omo_autonomy_level.py` (AutonomyLadder), 接线在 `omo_adjudication.py` `record_adjudication`, registry 在 `.omo/_truth/registry/autonomy-levels.yaml`。
2. **判据**: L0→L1 (20obs) / L1→L2 (cal≥0.6+30连) / L2→L3 (cal≥0.85+100连); rejected 立即降级 L0 + human_review。
3. **drift 监控**: BET-Y2Q3-T3-02 已实现 (sliding window 50 + demotion thresholds + human_review gate)。
4. **PASW 提交**: omo 子模块改动走 projects/omo → .subtrees/omo → push → bump-pointer。
5. **待办**: 实际放权某个场景属 T7-01 (non_goals 排除)。
