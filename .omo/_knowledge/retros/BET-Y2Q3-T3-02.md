---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y2Q3-T3-02 复盘
type: retro
---
# BET-Y2Q3-T3-02 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 1 小时（vs appetite 2 周）。drift 监控实现已在并发 agent 分支，本 bet 合入 main omo + 验证。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| calibration 滑动窗口监控 | ✅ `DRIFT_CONFIG.window_size=50` + `CapabilityAutonomy.recent_verdicts` + `windowed_calibration()` |
| 跌破阈值自动降级并产生事件 | ✅ `_check_drift` (分级阈值: L3<0.75/L2<0.50/L1<0.40) → `_apply_change` → `_emit_event` (autonomy.level_change) |
| 降级后需人工复核方可回升 | ✅ `requires_human_review` 门 + `clear_human_review` (复核后允许再晋升) |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **实现已在并发 agent 分支但未合入 main omo**: `omo_autonomy_level.py` 在 work/mof-sync 分支 (2389315f T3-01 + 6729b5ac T3-02 drift), 但 main omo 指针 b93cfa6b 不含 → **T3-01 留下的 test_autonomy_level.py 在 main omo 会 ImportError** (悬空测试)。
2. **T3-01 只提交了测试**: 我 T3-01 时提交了事件 emit 测试, 但实现文件 (omo_autonomy_level.py + adjudication 接线) 在并发分支未入库。main omo CI 测试实际是坏的。
3. **T3-02 真正价值 = 合入实现修复悬空**: 把 6729b5ac 的 omo_autonomy_level.py (含 drift) + adjudication 接线合入 main omo, 30 tests 恢复通过。
4. **test_release_script_exists pre-existing fail**: 检查 scripts/release.sh (scripts 子模块未检出), 环境性。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（omo 子模块 commit b46b2281）:
- `src/omo/omo_autonomy_level.py` (349L): drift 监控 + human review gate
- `src/omo/omo_adjudication.py` +12 行: _check_autonomy_ladder 接线

无新增 GaC 规则 / ADR / bin 脚本。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **autonomy 实现位置**: `omo/omo_autonomy_level.py` (AutonomyLadder + DRIFT_CONFIG), 接线在 omo_adjudication.py `_check_autonomy_ladder`。
2. **drift 参数**: window_size=50, 分级阈值 L3<0.75/L2<0.50/L1<0.40, human_review_required_after_demotion=True。
3. **PASW 提交**: omo 子模块改动走 projects/omo → .subtrees/omo → push → bump-pointer。
4. **并发分支协调**: work/mof-sync 分支含 autonomy 实现 (未合入 main), 本 bet 已合入。后续并发 agent 改 omo_autonomy_level.py 须基于 main (b46b2281)。
5. **待办**: 误降级率 > 10% → 放宽窗口 (circuit_breaker)。
