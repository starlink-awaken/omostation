---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0079: P85 X2 rule lint + ADR coverage check + COMMIT-FATIGUE 修正

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P85
- **Extends**: ADR-0078 (P84 M2 coverage + X2 freshness)
- **Superseded by**: (无)

## Context and Problem Statement

P84 收口后, P85 调研 2 项治理闭环工具 + 1 项 X2 rule 修正, 全部实施:

1. **X2 rule 自身无 lint**: `.omo/_truth/x2-freshness-rules.yaml` 9 rules, 缺乏 schema 健康度检查 (必填字段 / 合法 action / 必填 freshness 子字段). P84 仅修了 DEBT-EVIDENCE-INTEGRITY target 错配, 但其他字段错误无法自动捕获
2. **ADR 治理无 coverage 工具**: `.omo/_knowledge/decisions/` 37 个 ADR, 缺工具检查编号连续性 / frontmatter 完整性 / INDEX 引用一致性
3. **COMMIT-FATIGUE rule action 错配**: 写 `warn (100 files) / escalate (500 files)` 复合字符串, 不符合 action enum 规范

## Decision

### D1: bin/gac/x2-rule-lint.py (P85 R1)

**新工具** (`bin/gac/x2-rule-lint.py`):
- 必填字段检查: rule_id, target, freshness.threshold_days, freshness.action
- 类型检查: threshold_days 是正整数, action ∈ {warn, escalate, error}
- target glob 至少匹配一个真实文件/目录 (archived 豁免)
- rule_id 格式: `X2-FRESH-XXX`
- 重复 rule_id 检测

**实测发现** (P85 R1):
- 9 rules, 1 error
- ❌ `X2-FRESH-COMMIT-FATIGUE.freshness.action = "warn (100 files) / escalate (500 files)"` 复合字符串非法

### D2: X2-FRESH-COMMIT-FATIGUE 修正 (P85 R2)

**修正**: action 改为 `escalate` (单一 action, 复合描述放 notes)
- notes 标注: "P85 R1 修正: action 改为 'escalate' (warn@100files / escalate@500files 拆为 freshness 子字段, 单一 action)"
- threshold_count 字段保留 (用于机制内部细分)

**重测**: 9 rules, 9 ok, 0 issues ✓

### D3: bin/adr/adr-coverage.py (P85 R3)

**新工具** (`bin/adr/adr-coverage.py`):
- 编号连续性检查 (排除 P28-P49 历史 gap 命名约定 0009-0049)
- frontmatter 完整性 (status, lifecycle, owner, last-reviewed)
- INDEX 引用 vs 实际文件双向一致 (markdown 链接 + 表格纯文本)
- 重复编号检测

**实测**:
- 37 ADRs, 编号 0001-0078 (排除 0009-0049 命名约定 gap)
- ✅ 编号连续 (78 范围无意外 gap)
- ✅ 所有 frontmatter 完整
- ✅ INDEX 引用与文件 100% 一致

### D4: 收口统计

**P85 工具数**: 26 → **28** 独立 bin 工具 (+2)
- `bin/gac/x2-rule-lint.py` (新)
- `bin/adr/adr-coverage.py` (新)

**ADR 数**: 38 → **39** (P85 +1)

**X2 rules 修正**: +1 (COMMIT-FATIGUE action enum)

## Consequences

**正面**:
- X2 rule schema 自身健康可自动验证, 字段错配不再静默逃逸
- ADR 治理三维度 (编号 / frontmatter / INDEX 一致) 自动巡检
- COMMIT-FATIGUE rule 现在符合 action enum 规范
- P85 治理闭环补全: X2 freshness (P84) + X2 rule lint (P85) = X2 全栈自检

**负面**:
- X2 rule lint 未集成到 pre-commit hook (P86+ 可加)
- ADR coverage 编号 gap 检测采用硬编码 P28-P49 范围, 命名约定变更需手动更新
- mof-schema-validate alias 根因 (P84 提出) 仍未修, 因在 submodule 需谨慎

**关联**:
- ADR-0078 → ADR-0079: X2 freshness (运行时检查) → X2 rule lint (schema 静态检查) → 完整闭环
- ADR coverage 工具是 governance-history-insight (P83) 的 ADR 维度对应
- P86+ 候选: mof-m2-coverage 集成 pre-commit, X2 rule lint 集成 pre-commit

## Validation

```bash
# P85 R1: X2 rule lint
python3 bin/gac/x2-rule-lint.py
# 期望: 9 rules, 0 issues, "🎉 所有 X2 rules 健康!"

# P85 R2: COMMIT-FATIGUE rule 修正后
python3 bin/gac/x2-freshness-check.py
# 期望: 9 rules, 9 ok, 0 触发

# P85 R3: ADR coverage
python3 bin/adr/adr-coverage.py
# 期望: 37 ADRs, 编号连续, frontmatter 完整, INDEX 100% 一致

# ruff 验证
ruff check bin/gac/x2-rule-lint.py
ruff check bin/adr/adr-coverage.py
# 期望: All checks passed!
```

## References

- P84 R1-R3: mof-m2-coverage + x2-freshness-check + DEBT-EVIDENCE rule 修正
- P85 R1-R3: x2-rule-lint + COMMIT-FATIGUE 修正 + adr-coverage
- `.omo/_truth/x2-freshness-rules.yaml`: 9 X2 rules (全部健康)
- `.omo/_knowledge/decisions/`: 37 ADRs (0001-0078, 排除命名约定 gap)
- ADR-0078: P84 X2 freshness

---

*最后更新: 2026-06-25 · P85 X2 rule lint + ADR coverage check + COMMIT-FATIGUE 修正 收口*
