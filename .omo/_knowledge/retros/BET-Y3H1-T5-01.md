---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y3H1-T5-01 复盘
type: retro
---
# BET-Y3H1-T5-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 1 小时（vs appetite 3 周）。journey-runner 已有完整状态机，本 bet 加模板化层。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| journey 模板可参数化实例化 | ✅ `_render_template` ({{param}} 占位符替换 + spec 覆盖合并), 3 个实例 (inbox/meeting/oversight) |
| 至少 3 个场景共用 >= 1 个模板 | ✅ `intake-review-deliver` 模板被 inbox/meeting/oversight 3 个 journey 引用 |
| 模板变更影响面可查 | ✅ `journey-runner.py templates` 命令 → scan_template_usage (模板→引用 journey 映射) |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **journey spec 结构高度相似**: 现有 5 个 specs 都是"入口→评审→决策→执行→沉淀"骨架 → 抽象为通用模板。
2. **Edit 错位 bug**: 添加 scan_template_usage 时把 `_find_entry_state` 函数体误插到 scan 后 (F821 Undefined spec), 修复为删除游离函数体 + 保留完整定义。
3. **ruff baseline 13 错误**: journey-runner.py 既有 BLE001/S112 等, 我的代码净增 0 (修复自己的 except-continue)。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（主仓 commit）:
- `bin/ssot/journey-runner.py` +~50 行: _render_template + scan_template_usage + templates 命令
- `docs/journey-templates/intake-review-deliver.yaml`: 通用模板
- `docs/journey-specs/intake-review-deliver-{inbox,meeting,oversight}.yaml`: 3 个实例
- `tests/integration/journey_runner/test_template_orchestration.py` (7 测试)

无新增 GaC 规则 / ADR。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **模板机制**: journey spec 加 `template: <id>` + `params: {key: val}`, 模板文件在 `docs/journey-templates/`, 占位符 `{{param}}`。
2. **影响面查询**: `python3 bin/ssot/journey-runner.py templates` 显示模板→journey 映射。
3. **测试**: `tests/integration/journey_runner/test_template_orchestration.py` (7 个: 渲染/共用/影响面/执行/回归)。
4. **非目标**: 任意 DAG / 动态分支数 (non_goals 排除)。
5. **待办**: 更多场景接入模板 (如 research-pipeline 可复用骨架)。
