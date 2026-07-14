---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0087: P93 ADR drift 自动归类 + governance 6 类别对比分析

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P93
- **Extends**: ADR-0086 (P92 adr-trend + scripts install)
- **Superseded by**: (无)

## Context and Problem Statement

P92 收口后, P93 调研 3 项治理深化, 实施 2 项 (P93-A 推迟):

1. **P93-A omo_lint schemas 拆分 (推迟)**: 仍 432L, 配合 X2-FRESH-OMO-LINT-SIZE 持续监督
2. **P93-E ADR drift 自动归类**: 32 P50+ issues 全是 noise (template/aspirational/typo), 需自动分类
3. **P93-D gov-history 6 类别 vs 90 天对比**: P91 只输出 30 天类别趋势, 缺前后对比分析

## Decision

### D1: bin/adr/adr-drift-auto-fix.py (P93 R1)

**新工具**: 调用 adr-drift-classify, 自动分类每个 P50+ issue 为:
- **TEMPLATE**: 路径含 YYYYMMDD/HHMM/TBD/XXX 等占位符 (7 issues)
- **SUBDIR_MISSING**: 父目录存在但文件缺失 (19 issues) - 可 touch 占位
- **TYPO**: 文件名接近已知文件 (4 issues) - 可 ADR 修正
- **REAL_BUG**: 路径本应存在但消失 (1 issue) - 需人工 review
- **ASPIRATIONAL**: 子项目根本不存在 (1 issue) - ADR 删除引用

**实测** (32 P50+ issues):
- SUBDIR_MISSING: 19 (60%) - touch 占位即可
- TEMPLATE: 7 (22%) - 模板路径, ADR 标注
- TYPO: 4 (12%) - ADR 字符级修正
- REAL_BUG: 1 (3%) - 人工 review
- ASPIRATIONAL: 1 (3%) - ADR 删引用
- **30/32 (94%) 可自动修复**

**关键洞察**: 真正需要治理修复的只有 1 个 (REAL_BUG), 其余 31 个是 noise. ADR drift 报告噪音 94%.

### D2: gov-history-stats --compare (P93 R2)

**深化 P91 R3 工具**: 加 `--compare` 模式, 拆 N/2 最近 vs 前 N/2
- 前半: count=317 avg=94.5
- 后半: count=318 avg=96.7
- **delta: +2.2** (governance 改进)

**实测** (635 entries, 30 天):
- 后半 96.7 vs 前半 94.5 = +2.2 持续改进
- 6 类别均 visible (P91 R3 报告时只 1 类别, P92 数据完整后全 6)

### D3: P93-A omo_lint schemas 拆分 仍推迟 (5 次推迟)

**历史推迟链**:
- P89-A: 首次提出
- P90-A: 拆 schemas (432L) 计划
- P91-A: install-dashboard-cron + schemas 拆
- P92-A: adr-trend + schemas 拆
- P93-A: adr-drift-auto-fix + schemas 拆 (本轮)

**理由 (每轮相同)**:
- 1257L 仍 1 god-module error
- schemas 引用 4 个 module-level 常量, 拆分需重新设计归属
- 风险: 一次性拆 432L, 在 submodule 内做需要人类审批 commit 节奏
- X2-FRESH-OMO-LINT-SIZE (P90) 持续监督: 7 天未变化触发 warn, 防止反弹

**P94+ 推进策略**: 配合 X2 rule 节奏, 拆 4 个子模块:
1. schemas (432L) → 825L, <1500L error 阈值
2. surfaces (136L) → 689L
3. mutation_ledger (56L) → 633L
4. yaml_bypass (72L) → 561L, <800L warn 阈值

### D4: 收口统计

**P93 工具数**: 37 → **38** 独立 bin 工具 (+1)
- `bin/adr/adr-drift-auto-fix.py` (新)

**ADR 数**: 46 → **47** (P93 +1)

**governance-dashboard 覆盖**: 15 → **16** 工具

**ADR drift 智能化**:
- P89 adr-drift-check: 109 issues (raw)
- P90 adr-drift-classify: 38 P50+ (历史 vs 新增归类)
- **P93 adr-drift-auto-fix: 32 P50+ (5 类自动归类, 30/32 可自动修复)**

**governance 6 类别对比**: 前半 94.5 vs 后半 96.7 (**+2.2**)

## Consequences

**正面**:
- ADR drift 智能化三阶段闭环: 检测 (P89) → 归类 (P90) → 修复建议 (P93)
- 32 P50+ issues 30/94% 可自动修复, 降低治理噪音
- governance-history 对比分析 (+2.2) 量化演进
- 真正需要修复的 REAL_BUG 只有 1 个, 治理精度提升

**负面**:
- P93-A (omo_lint schemas 拆) 仍推迟, 1257L 1 god-module error
- ASPIRATIONAL (1 issues: llm-gateway/) 是 P81 ARCHIVED 规则, ADR 引用需删
- adr-drift-auto-fix 用 Jaccard 简化 Levenshtein, typo 检测准确度有限

**关联**:
- ADR-0086 → ADR-0087: P92 adr-trend (时间维度) + P93 adr-drift-auto-fix (智能归类)
- ADR drift 治理完整链: 检测 (P89) → 归类 (P90) → 修复 (P93)
- P93-A 仍推迟, 配合 X2-FRESH-OMO-LINT-SIZE 持续监督 (6 轮推迟兑现策略)

## Validation

```bash
# P93 R1: ADR drift auto-fix
python3 bin/adr/adr-drift-auto-fix.py
# 期望: 32 P50+ issues, 30 auto-fixable, 5 类 (TEMPLATE/SUBDIR_MISSING/TYPO/REAL_BUG/ASPIRATIONAL)
python3 bin/adr/adr-drift-auto-fix.py --json  # JSON 输出

# P93 R2: gov-history compare
python3 bin/gov-history-stats.py --compare
# 期望: 前半 avg + 后半 avg + delta (+2.2 预期)
python3 bin/gov-history-stats.py --compare --days 60  # 60 天窗口

# P93 R3: dashboard
python3 bin/gac/governance-dashboard.py
# 期望: 16/16 工具全部通过

# ruff 验证
ruff check bin/adr/adr-drift-auto-fix.py
ruff check bin/gov-history-stats.py
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
- P93 R1-R2: adr-drift-auto-fix + gov-history-stats --compare
- ADR-0086: P92 ADR trend

---

*最后更新: 2026-06-25 · P93 ADR drift 自动归类 + governance 6 类别对比分析 收口*
