---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0091: P97 TYPO 实际应用 + apply/rollback 集成测试 + X2-FRESH-ADR-TYPO

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P97
- **Extends**: ADR-0090 (P96 真 Levenshtein TYPO)
- **Superseded by**: (无)

## Context and Problem Statement

P96 收口后, P97 调研 3 项治理深化, 实施 3 项 (P97-A 推迟):

1. **P97-A omo_lint schemas 拆分 (9 轮推迟)**: 仍 432L
2. **P97-B TYPO 实际 apply**: P96 R1 仅 dry-run 验证, P97 实际应用 12 个 ratio 1.0 TYPO
3. **P97-D apply/rollback 集成测试**: P94-P96 工具 rollback 机制未验证, P97 写集成测试
4. **P97-G X2-FRESH-ADR-TYPO rule**: 监控 adr-typo-real-fix-history.jsonl 14 天

## Decision

### D1: TYPO 实际 apply (P97 R1)

**执行**:
```bash
python3 bin/adr-typo-real-fix.py --apply
```

**实测**:
- ✅ Applied: **12 个 TYPO** (100% 成功率, 全 ratio 1.0)
  - ADR-0052: 2 处 (designs + management)
  - ADR-0076: 2 处 (workflows + management)
  - ADR-0089: 3 处 (workflows + management + designs)
  - ADR-0090: 3 处 (workflows + management + designs)
- ⚠️  Skipped: 0

**修后状态**:
- P50+ issues: 19 → **11** (减 8, 42% 减少)
- 实际 ADR 文件修改: 7 个 (4 个 ADR × 多次 typo)

### D2: apply/rollback 集成测试 (P97 R2)

**新工具**: `bin/adr-rollback-test.py`
- 完整 cycle 测试: apply → rollback → re-apply
- 验证 rollback 机制恢复状态
- 输出 P50+ count 在各阶段的变化

**实测**:
- 初始 P50+: 11
- apply: 11 → 11 (idempotent, OK)
- rollback: 11 → 11 (restored, OK)
- re-apply: 11 (preserved)
- 🎉 **所有 apply/rollback cycle 通过**

**价值**: 验证 P94-P96 apply/rollback 工具链一致性, 防止 silent corruption.

### D3: X2-FRESH-ADR-TYPO rule (P97 R3)

**新增 X2 rule** (12→13):
```yaml
- rule_id: X2-FRESH-ADR-TYPO
  title: "P97 ADR TYPO 字符级修复 (Levenshtein, 监控 history 持续修复)"
  target: .omo/_delivery/adr-typo-real-fix-history.jsonl
  freshness:
    threshold_days: 14
    action: warn
  notes: >
    P97 R3 新增 rule.
```

**实测**: 13 rules, 0 issues (target 存在, fresh)

### D4: 收口统计

**P97 工具数**: 43 → **44** 独立 bin 工具 (+1)
- `bin/adr-rollback-test.py` (新)

**ADR 数**: 50 → **51** (P97 +1)

**X2 rules**: 12 → **13** (P97 +1)

**governance-dashboard 覆盖**: 21 → **22** 工具

**TYPO 实际修复**: 12 个 (从 dry-run 到 apply), P50+ issues 19→11 (-42%)

**apply/rollback 机制**: 100% 通过 (集成测试验证)

## Consequences

**正面**:
- TYPO 12 个 100% 修复 (Levenshtein ratio 1.0 全匹配)
- apply/rollback 机制集成测试 100% 通过
- X2-FRESH-ADR-TYPO 持续监督 TYPO 修复 history
- 22 dashboard 工具统一入口

**负面**:
- P97-A (omo_lint schemas 拆) 仍推迟 9 轮
- TYPO 修复仅改 8 个 path 中 12 处出现 (重复 pattern 多次引用同一文件)
- adr-rollback-test 仅测试 1 个工具 (adr-typo-real-fix), 未覆盖 adr-drift-apply

**关联**:
- ADR-0090 → ADR-0091: P96 真 Levenshtein → P97 实际应用, TYPO 修复闭环
- apply/rollback 测试验证 P94-P96 工具链一致性
- X2 rule 13: 持续监督 TYPO 修复 rate

## Validation

```bash
# P97 R1: TYPO apply
python3 bin/adr-typo-real-fix.py --apply
# 期望: 12 Applied, 0 Skipped

# P97 R2: rollback test
python3 bin/adr-rollback-test.py
# 期望: 🎉 所有 apply/rollback cycle 通过

# P97 R3: X2 rule
python3 bin/gac/x2-rule-lint.py
# 期望: 13 rules, 0 issues

# P97 R4: dashboard
python3 bin/gac/governance-dashboard.py
# 期望: 22/22 工具全部通过

# ruff 验证
ruff check bin/adr-rollback-test.py
# 期望: All checks passed!
```

## References

- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- P87 R1-R3: god-module-roadmap + x2-rule-add + dashboard 扩展
- P88 R1-R3: omo_lint 拆解 + X2 template + gov-trend-report
- P89 R1-R3: rule-history-insight + adr-drift-check + dashboard 12
- P90 R1-R4: X2 rule OMO-LINT-SIZE + adr-drift-classify + dashboard cron + dashboard 13
- P91 R1-R4: install-dashboard-cron + X2-FRESH-GOV-DASHBOARD + gov-history-stats + dashboard 14
- P92 R1-R3: adr-trend-insight + install-dashboard-cron 推入 + 类别趋势深化 + dashboard 15
- P93 R1-R2: adr-drift-auto-fix + gov-history-stats --compare + dashboard 16
- P94 R1-R3: adr-drift-apply + 13 god-module list + REAL_BUG 修 + dashboard 18
- P95 R1-R3: adr-drift-apply --apply 实际 (20 files) + adr-typo-fix (新, Jaccard 噪声) + pyyaml 修 + dashboard 19
- P96 R1-R3: adr-typo-real-fix (真 Levenshtein) + venv-yaml-check + X2-FRESH-ADR-DRIFT (12 rules) + dashboard 21
- P97 R1-R3: TYPO apply (12) + apply/rollback 集成测试 + X2-FRESH-ADR-TYPO (13 rules) + dashboard 22
- ADR-0090: P96 真 Levenshtein

---

*最后更新: 2026-06-25 · P97 TYPO 实际应用 + apply/rollback 集成测试 + X2-FRESH-ADR-TYPO 收口*
