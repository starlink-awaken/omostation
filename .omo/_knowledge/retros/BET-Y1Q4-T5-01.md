---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q4-T5-01 复盘
type: retro
---
# BET-Y1Q4-T5-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 1.5 小时（vs appetite 2 周）。核心状态机已存在，本 bet 扩展 parallel fork/join。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| journey.type 支持 parallel, 含 fork/join 节点 | ✅ journey-runner.py 状态机扩展: fork 状态 (`parallel.branches`) 分叉多分支, join 状态 (`join.sources`) 汇聚 |
| join 策略可配置(全部完成 / 多数 / 任一) | ✅ `_join_satisfied(strategy, completed, total)`: all (≥total) / majority (>total/2) / any (≥1) |
| 集成测试覆盖三种策略 | ✅ test_parallel_fork_join.py 7 测试 (三种策略端到端 + fork/join 解析 + 线性回归) |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **状态机是单指针遍历**: journey-runner 原用单一 `current_state_name` 顺序推进。parallel 需多 active 状态 → 改用 `active_states` 队列。
2. **join 重复执行 bug**: 三个分支各推进一次 join_point → join 满足后 approved 被执行 3 次。修复: join 满足时从队列移除所有 join_point 副本, 只执行一次。
3. **journey spec 路径是 docs/journey-specs/**: 非 docs/journeys/ (最初找错)。
4. **ruff 基线 14 错误**: journey-runner.py 已有 14 个 pre-existing ruff 错误 (BLE001/S110/S112), 我的修改净增 0。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（主仓 commit）:
- `bin/ssot/journey-runner.py` +~60 行: parallel fork/join 支持 (helper 函数 + 主循环扩展)
- `docs/journey-specs/parallel-approval-test.yaml` (测试 spec)
- `tests/integration/journey_runner/test_parallel_fork_join.py` (7 测试)

无新增 GaC 规则 / ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **parallel spec 格式**: fork 状态加 `parallel: {branches: [b1, b2]}`, join 状态加 `join: {strategy: all|majority|any, sources: [b1, b2]}`。
2. **执行语义**: fork 分叉到 branches (不执行 fork 自身), join 按策略等待 sources 完成 (completed_states 集合追踪), join 只执行一次。
3. **测试**: `tests/integration/journey_runner/test_parallel_fork_join.py` 覆盖三种策略。
4. **非目标**: 任意 DAG / 动态分支数 (non_goals 排除)。
5. **待办**: 真实公文场景接入 parallel journey (如 multi-party approval)。
