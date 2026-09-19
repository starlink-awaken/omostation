---
schema: bet-retro/v1
bet_id: A1-budget-auto-bump-generalize
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-19
type: ephemeral
completed_at: 2026-09-19
---

# Retro: A1 — auto-bump-doc-governance-budget.py v2 通用化

## Summary

扩展 `bin/ssot/auto-bump-doc-governance-budget.py` 从 v1 (单 budget 硬编码) 到 v2 (通用化):
按 (rule, surface) 二元组定位 budget exception, 兼容全部 9 个 budget 类型,
加 ABSOLUTE_MAX_BUMP=50 circuit breaker + `--strict` 模式 + 7 单元测试.

## What went well

- **二元组定位**: `find_exception(yaml_content, rule, surface)` 解耦 exception_id 硬编码,
  9 个 budget 类型 0 改动即支持 (legacy-*-enums/frontmatter + concurrent-plans-orphan-docs + accepted-specs-invalid-metadata)
- **circuit breaker**: ABSOLUTE_MAX_BUMP=50 + 越界自动缩为上限 + 警告, 防止单 PR 误操作
- **多层测试**: dry-run / 实际 bump / 多 budget 并发 / 单元测试全场景
- **rebase 干净**: 7 commit (#4046-4052) 后 rebase origin/main 无冲突

## What was learned

- **`doc-governance-check.py` 默认 EXIT 0**: budget_exceeded error 只在 `--no-new-warnings` 模式触发,
  v1 脚本漏了 `--no-new-warnings` flag → 检测不到超支, bug 实测发现并修复
- **skip-if-no-over-budget**: 默认 `count <= budget` 时跳过, 避免无意义 bump; `--strict` 反转
- **新 count 自适应**: `new_count = max(current + amount, count + amount)` — 当 count 已远超 budget,
  +20 不够时自动追加, 一次 PR 解决
- **pyright 提示 vs ruff 强制**: pyright 报 `i not used` 是 informational, ruff E501/E9 不强制,
  不阻断 pre-commit

## What to improve

- 缺端到端 fixture: 在 `tests/fixtures/` 加 `dg-overbudget.yaml` 模板供回归测试
- bump 行保留旧注释, 可加 parse 标记 + JSON 索引 (P106 候选)
- unit test 目前用 `tmp_path` 跑 subprocess 较少, 可加 integration fixture

## Metrics

- Files modified: 1 (bin/ssot/auto-bump-doc-governance-budget.py 156→221 LOC, +65)
- Files added: 1 (tests/bin/test_auto_bump_doc_governance_budget.py 130 LOC)
- Files updated: 1 (bin/_registry/scripts/governance/auto-bump-doc-governance-budget.yaml description)
- Tests: 7/7 pass in 0.20s
- Budget types supported: 9 (前 v1 仅 1)
- circuit_breaker: +20 → +50 max
- PR: TBD
- Total LOC delta: +195

## 完整 done_when 验收

| 项 | 状态 |
|---|---|
| `--no-new-warnings` flag 加入 (修 v1 bug) | ✅ |
| `find_exception(rule, surface)` 二元组定位 | ✅ |
| ABSOLUTE_MAX_BUMP=50 circuit breaker | ✅ |
| `--strict` 模式 (强制 bump count ≤ budget) | ✅ |
| 多 budget 并发 bump (dry-run 实测 2 个并发) | ✅ |
| 单元测试 7/7 pass | ✅ |
| script-registry 描述更新 (v2 + 9 个 budget + inputs) | ✅ |
| ruff check 0 errors | ✅ |
| doc-governance-check --no-new-warnings PASS | ✅ |
| script-registry validate 691 PASS | ✅ |