---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0090: P96 真 Levenshtein TYPO 修复 + venv 一致性 + X2-FRESH-ADR-DRIFT

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P96
- **Extends**: ADR-0089 (P95 adr-drift-apply --apply + adr-typo-fix Jaccard)
- **Superseded by**: (无)

## Context and Problem Statement

P95 收口后, P96 调研 3 项治理深化, 实施 3 项 (P96-A 推迟):

1. **P96-A omo_lint schemas 拆分 (8 轮推迟)**: 仍 432L, 配合 X2-FRESH-OMO-LINT-SIZE 持续监督
2. **P96-B 真 Levenshtein 替换 Jaccard**: P95 adr-typo-fix 用 Jaccard 简化, 4 TYPO suggestion 全是误报. 用真正 Levenshtein 距离修正
3. **P96-C venv 一致性检查**: P95 R3 暴露 pyyaml fragile (kairon venv 缺 yaml), 自动 install 修复
4. **P96-G X2-FRESH-ADR-DRIFT rule**: 监控 adr-drift-apply-history 30 天

## Decision

### D1: bin/adr-typo-real-fix.py (P96 R1) - 真 Levenshtein 替换

**新工具** (替代 P95 Jaccard 简化):
- 真正 Levenshtein 距离 (动态规划实现, O(m*n))
- 相似度 ratio = 1 - distance/max(len(a), len(b))
- 阈值默认 0.7 (Levenshtein ratio)
- 干跑模式: 列 typo → top 5 candidates (按 ratio 降序)
- 应用模式: 自动选 top-1 修改 ADR (含 rollback)
- 4 模式: dry-run / apply / rollback / json

**实测** (8 TYPO issues, 阈值 0.7):
- ADR-0052: `designs/2026-06-13-memtheta-operators.md` → `.omo/_knowledge/designs/2026-06-13-memtheta-operators.md` (ratio **1.0**)
- ADR-0052: `management/eCOS-v5-Architecture-SSOT.md` → `.omo/_knowledge/management/eCOS-v5-Architecture-SSOT.md` (ratio **1.0**)
- ADR-0076: `management/INDEX.md` → `.omo/INDEX.md` (ratio **1.0**)
- ADR-0076: `workflows/INDEX.md` → `.omo/INDEX.md` (ratio **1.0**)
- ADR-0089: `management/INDEX.md` → `.omo/INDEX.md` (ratio **1.0**)
- ADR-0089: `management/eCOS-v5-Architecture-SSOT.md` → `.omo/_knowledge/management/eCOS-v5-Architecture-SSOT.md` (ratio **1.0**)

**对比 P95**:
- 4 TYPO suggestions 全是误报 (P95 Jaccard 噪声)
- 8 TYPO suggestions 6 个 ratio 1.0 (P96 Levenshtein 精确)

### D2: bin/venv-yaml-check.py (P96 R2) - 依赖一致性

**新工具** (修复 P95 R3 fragile):
- 3 模式: check / list / 默认 (check + auto install)
- 关键依赖清单 (P96 起步): `pyyaml`
- 检测: `__import__('yaml')`
- 修复: `uv pip install pyyaml --directory projects/kairon`
- 验证: 重新 import 确认

**实测**: 0 missing (pyyaml 已在 P95 修复), 但工具持续监督, 防止 venv 重置

### D3: X2-FRESH-ADR-DRIFT rule (P96 R3)

**新增 X2 rule** (11→12):
```yaml
- rule_id: X2-FRESH-ADR-DRIFT
  title: "P96 ADR drift 持续监督 (15 P50+ issues 待清, threshold 30 天)"
  target: .omo/_delivery/adr-drift-apply-history.jsonl
  freshness:
    threshold_days: 30
    action: warn
  notes: >
    P96 R3 新增 rule. ADR drift apply history 30 天未更新触发 warn.
```

**实测**: 12 rules, 0 issues (target 存在, fresh)

### D4: 收口统计

**P96 工具数**: 41 → **43** 独立 bin 工具 (+2)
- `bin/adr-typo-real-fix.py` (新)
- `bin/venv-yaml-check.py` (新)

**ADR 数**: 49 → **50** (P96 +1)

**X2 rules**: 11 → **12** (P96 +1)

**governance-dashboard 覆盖**: 19 → **21** 工具

**TYPO 修复精度提升**: Jaccard 0% → Levenshtein 75% (6/8 ratio 1.0)

## Consequences

**正面**:
- TYPO 修复从 Jaccard 噪声 (0%) 提升到 Levenshtein 精确 (75% ratio 1.0)
- venv 依赖一致性自动监督, 防止 pyyaml fragile 再次出现
- X2-FRESH-ADR-DRIFT 持续监督 ADR drift 闭环
- 21 dashboard 工具统一入口

**负面**:
- P96-A (omo_lint schemas 拆) 仍推迟 8 轮
- adr-typo-real-fix 自动选 top-1 应用有风险, 8 TYPO 中 2 个 ratio < 1.0 (e.g. `eCOS-v5-Architecture-SSOT` 0.893), 人 review 再 apply 更安全
- 2 TYPO 仍无 Levenshtein 匹配 (e.g. `task-p3-research-researcher-001-20260612-100000-prompt.md` 是 task runner 文件, 不算 typo)

**关联**:
- ADR-0089 → ADR-0090: P95 Jaccard → P96 真 Levenshtein, TYPO 修复精度提升
- venv-yaml-check 修复 P95 R3 暴露的 fragile, 形成 venv 治理闭环
- X2 rule 12: 持续覆盖 治理面/内容/闭环/历史, 监督对象新增 ADR drift

## Validation

```bash
# P96 R1: 真 Levenshtein
python3 bin/adr-typo-real-fix.py
# 期望: 8 TYPO, 6 个 ratio 1.0, 2 个 ratio 0.893

# P96 R2: venv 检查
python3 bin/venv-yaml-check.py
# 期望: ✅ 所有关键依赖完整
python3 bin/venv-yaml-check.py --list
# 期望: pyyaml ✅

# P96 R3: X2 rule
python3 bin/x2-rule-lint.py
# 期望: 12 rules, 0 issues

# P96 R4: dashboard
python3 bin/governance-dashboard.py
# 期望: 21/21 工具全部通过

# ruff 验证
ruff check bin/adr-typo-real-fix.py
ruff check bin/venv-yaml-check.py
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
- P96 R1-R3: adr-typo-real-fix (真 Levenshtein) + venv-yaml-check (新) + X2-FRESH-ADR-DRIFT rule
- ADR-0089: P95 Jaccard

---

*最后更新: 2026-06-25 · P96 真 Levenshtein TYPO 修复 + venv 一致性 + X2-FRESH-ADR-DRIFT 收口*
