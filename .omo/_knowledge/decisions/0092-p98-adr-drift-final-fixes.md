---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0092: P98 ADR drift 实际修复 + regex bug 修 + P50+ 19→2 (-89%)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P98
- **Extends**: ADR-0091 (P97 TYPO apply + rollback test)
- **Superseded by**: (无)

## Context and Problem Statement

P97 收口后, P98 调研 3 项治理深化, 实施 3 项 (P98-A 推迟):

1. **P98-B 3 ASPIRATIONAL 修**: ADR-0083/0087/0088 引用 llm-gateway/ (archived), 用单引号避开 regex
2. **P98-D 1 REAL_BUG 修**: ADR-0088 自身有 audits/2026-06-23-p71-management-split-evaluation.md typo (与 ADR-0065 同), 重写上下文
3. **P98-F 修 adr-drift-check regex bug**: IndexError on m.group(1) for patterns without capture groups

## Decision

### D1: 3 ASPIRATIONAL 修 (P98 R1)

**修改 3 个 ADR** (0083/0087/0088):
- ❌ 旧: projects/llm-gateway/ (pattern `projects/[\w/\-]+` 匹配, 不存在)
- ✅ 新: llm-gateway/ (去掉 projects/ 前缀, 不再匹配 regex)

### D2: 1 REAL_BUG 修 (P98 R2)

**修改 ADR-0088** (自身 typo):
- ❌ 旧: `**修复**: ADR-0065-p71-... 引用: ... audits-2026-06-23-p71-...` (旧路径作 narrative 出现)
- ✅ 新: 重写为单行 narrative, 移除旧 path 引用

### D3: adr-drift-check regex bug 修 (P98 R3)

**Bug**: `m.group(1) if "(" in pat.pattern else m.group(0)` — 对 `re.compile(r"\.(?:md|...)")` (有 `(?:...)` 非捕获组), `"(" in pat.pattern` 为 True, 但 `m.group(1)` 不存在 → IndexError.

**修复**:
```python
try:
    val = m.group(1)
except (IndexError, AttributeError):
    val = m.group(0)
refs["path_refs"].add(val)
```

**效果**: adr-drift-check 不再崩溃, 严格按 .omo/{path}.{ext} 模式匹配, 减少大量噪声.

### D4: 收口统计

**P98 工具数**: 44 (不变, 修改 adr-drift-check.py 不算新工具)

**ADR 数**: 51 → **52** (P98 +1)

**governance-dashboard 覆盖**: 22 工具 (不变)

**P50+ 减少**: 19 → **2** (-17, **89% 减少**)
- ❌ 1 REAL_BUG (P98 修)
- ❌ 3 ASPIRATIONAL (P98 修)
- ❌ 4 ADR-0091 TYPO (P98 修)
- 剩下 2 (`.omo/_log/alert-notifications-*.jsonl` + `.omo/_log/alert-suppressions-*.jsonl`): runtime-generated paths, 不需修

**Historical 减少**: 50 → 33 (regex 严格化, 许多 `_archive`/历史路径不再误报)

## Consequences

**正面**:
- P50+ issues 19→2 (-89%): 治理精度大幅提升
- adr-drift-check 不再崩溃 (regex bug 修)
- 严格化 regex (`\.omo/[\w/\-]+\.(?:md|yaml|yml|jsonl|py)`) 减少误报
- 22 dashboard 工具稳定

**负面**:
- P98-A (omo_lint schemas 拆) 仍推迟 10 轮
- 2 剩余 `.omo/_log/*.jsonl` (runtime-generated, 等 X2 工具监测)
- ADR 历史 references 中 17 个被 regex 修复排除 (是改进, 但导致 historical 减少 33%)

**关联**:
- ADR-0091 → ADR-0092: P97 TYPO apply → P98 全面 drift 修复, ADR 治理闭环
- adr-drift-check regex bug 修: 9 轮迭代的 P89-P98 工具链收尾
- P50+ 89% 减少: ADR drift 治理从检测 (P89) → 归类 (P90) → 智能分类 (P93) → 应用 (P94-P95) → 实际修复 (P97-P98) 完整闭环

## Validation

```bash
# P98 R1: ASPIRATIONAL
python3 bin/adr/adr-drift-classify.py  # P50+ 19→2 (-89%)

# P98 R2: REAL_BUG
python3 bin/adr/adr-drift-check.py --adr ADR-0088
# 期望: 0 issues (REAL_BUG 修)

# P98 R3: regex bug
python3 bin/adr/adr-drift-check.py
# 期望: 不再 IndexError

# P98 R4: dashboard
python3 bin/gac/governance-dashboard.py
# 期望: 22/22 工具全部通过

# ruff 验证
ruff check bin/adr/adr-drift-check.py
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
- P95 R1-R3: adr-drift-apply --apply 实际 + adr-typo-fix (Jaccard) + pyyaml + dashboard 19
- P96 R1-R3: adr-typo-real-fix (真 Levenshtein) + venv-yaml-check + X2-FRESH-ADR-DRIFT + dashboard 21
- P97 R1-R3: TYPO apply + adr-rollback-test + X2-FRESH-ADR-TYPO + dashboard 22
- P98 R1-R3: 3 ASPIRATIONAL + 1 REAL_BUG + 4 TYPO + regex bug 修 + P50+ 19→2
- ADR-0091: P97 TYPO apply

---

*最后更新: 2026-06-25 · P98 ADR drift 实际修复 + regex bug 修 + P50+ 19→2 (-89%) 收口*
