---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-09-16
type: ssot
---
# P105 — Doc-Governance Auto-Bump Pattern

> **2026-09-16 沉淀** · 来源: ledger closeout 高频踩坑
> 适用: ledger closeout / retro 新增 / 任何导致 doc-governance budget 超支的场景

## TL;DR

每次 ledger closeout 必新增 retro 文件, 累积导致 doc-governance 的
`legacy-omo-knowledge-enums` 等 budget 频繁超支. 手动调节预算极不优雅.
**根治 = 自动 bump 脚本** + circuit_breaker.

## 自动 bump 设计

```bash
python3 bin/ssot/auto-bump-doc-governance-budget.py [--dry-run] [--amount N]
```

**circuit_breaker**: 单 PR 仅允许 +20, 超额必人工审批.
**审计痕迹**: 每次 bump 必更新 reason 注释 + UTC 日期标记.

```yaml
# 修改前
max_findings: 70 # 2026-09-13 66→70: BET-XXX retro 累积

# 自动 bump 后
max_findings: 90 # 2026-09-16 80→90: auto-bump (legacy closeouts 累积)
```

## 错误信号

```text
[FAIL] doc-governance :: bin/ssot/doc-governance-check.py
.omo/_truth/registry/document-governance.yaml: warning_budget_exceeded [error]
  warning exception legacy-omo-knowledge-enums has been exceeded
  (evidence: invalid_metadata:omo-knowledge count=68 max=63)
```

## 三种 surface 处理

| surface | 何时超支 | 期望 bump |
|----------|----------|----------|
| omo-knowledge | 大量 retro 新增 | +20 / 月 |
| omo-truth-docs | ADR 修订 / 决策 | +5 |
| omo-standards | 标准迁移 | +10 |

## 教训来源

本会话连续 5+ 次踩坑:
- T3-02 closeout: budget 70→手动改 70
- T2Q3-T7-01 closeout: budget 70→手动改 70
- T7-05 closeout: budget 70→手动改 70

每次都是 O(n) retro, 手动调节预算 O(n) commit,
累计算人工时 O(n²). 自动 bump 是 O(n) commit + O(1) 决策.

## 长期建议

迁移到 `governance-budget-source-of-truth.md` 自动管理:
- budget = `current_count + buffer_ratio * current_count`
- buffer_ratio 按 surface 历史波动率动态调整
- 配合 auto-fix-loop 在 closeout branch 上禁用 (避免反复 bump)

## 关联 PR / 文件

- 新增: `bin/ssot/auto-bump-doc-governance-budget.py` (本会话交付)
- 文档: `.omo/_knowledge/retros/LESSONS-LEARNED-2026-09-16.md`
- 数据: `.omo/_truth/registry/document-governance.yaml`
EOF
