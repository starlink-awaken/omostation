---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0086: P92 ADR 趋势洞察 + install-dashboard-cron 推入 scripts/ 子模块

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P92
- **Extends**: ADR-0085 (P91 cron install + X2 rule + gov-history-stats)
- **Superseded by**: (无)

## Context and Problem Statement

P91 收口后, P92 调研 3 项治理深化, 实施 2 项 (P92-A 推迟):

1. **P92-A omo_lint schemas 拆分 (推迟)**: 仍 432L 待拆, 配合 X2-FRESH-OMO-LINT-SIZE 持续监督
2. **P92-F ADR 趋势洞察**: 41 ADRs 累积, 缺时间维度 (phase 分布, 增长曲线, 提交历史)
3. **P92-B install-dashboard-cron 推入 scripts/**: P91 R1 推迟到 P92 兑现, 配合 scripts/ 子模块 commit 周期

## Decision

### D1: bin/adr/adr-trend-insight.py (P92 R1)

**新工具**: ADR 时间维度洞察
- 加载所有 ADR (含 frontmatter) + git log (首次/最后 commit 时间)
- phase 分桶: P28 / P50-P59 / P60-P69 / P70-P79 / P80-P89 / P90+
- 按 status / lifecycle / year 统计
- frontmatter 完整度检查

**实测** (44 ADRs, 当前快照):
- 总数: 44
- frontmatter 完整度: **100.0%** (P85 R2 adr-coverage 工具持续监督成果)
- 按 phase: P28(8) / P50-P59(10) / P60-P69(10) / P70-P79(10) / P80-P89(6) / 暂无 P90+ (P90-92 阶段刚收口, 待 OMC commit)
- 按 status: active 36, archived 8
- 按年份: 全部 2026 (单一 project era)

### D2: install-dashboard-cron.sh 推入 scripts/ (P92 R2)

**P91 R1 推迟兑现**:
- 重新写入 `scripts/omo/install-dashboard-cron.sh` (P91 删过, 这次落子模块 working tree)
- chmod +x, dry-run 验证通过
- 待 scripts/ 子模块 commit 周期由人类审批

**scripts/ 子模块 commit 规范** (per CLAUDE.md):
- 根仓只 commit 元数据 (plan/doc/evidence)
- 子模块 commit 由 omostation 人类审批
- P92 ADR 记录: install-dashboard-cron 已落 scripts/ working tree, 留待 P93+ 提交

### D3: governance-history 类别趋势 (P92 D - 顺手深化)

**P91 R3 gov-history-stats 之前只显示 1 个类别** (lint). 实测 6 类别都在 governance-history 数据中.

**修复**: gov-history-stats 实际已能输出 6 类别 (lint/tests/debt/knowledge/tasks/agora), P91 R3 报告时是 1 类别是因数据未累积. 30 天 632 entries 完整覆盖 6 类别.

**P92 关键数据** (类别 delta):
| 类别 | avg | latest | delta |
|------|-----|--------|-------|
| lint | 86.3 | 100.0 | **+12.0** |
| tasks | 87.7 | 100.0 | **+10.7** |
| agora | 93.8 | 100.0 | +4.6 |
| tests | 99.8 | 100.0 | +3.6 |
| knowledge | 99.6 | 99.9 | +0.3 |
| debt | 99.7 | 100.0 | 0.0 |

**洞察**: lint +12.0 + tasks +10.7 是治理演进最大动力 (X2 rule lint 工具 + governance-task 工具持续完善).

### D4: 收口统计

**P92 工具数**: 36 → **37** 独立 bin 工具 (+1)
- `bin/adr/adr-trend-insight.py` (新)

**P92 Scripts**: install-dashboard-cron.sh 推入 scripts/ working tree (commit 待)

**ADR 数**: 45 → **46** (P92 +1)

**governance-dashboard 覆盖**: 14 → **15** 工具

**ADR 健康**: 44 ADRs, 100% frontmatter, 36 active + 8 archived

**governance 6 类别趋势**: lint +12.0 / tasks +10.7 / agora +4.6 / tests +3.6 / knowledge +0.3 / debt 0.0 (30 天)

## Consequences

**正面**:
- ADR 趋势有集中视图 (phase 分布 + 提交历史)
- install-dashboard-cron 落 scripts/ working tree, 待 P93+ 提交
- 6 类别治理趋势首次全部可见 (P91 R3 报告时只 1 类别)
- X2 rule 体系已扩到 11 rules, 治理成熟度量化
- adr-trend-insight 100% frontmatter 验证 P85 R2 adr-coverage 工具持续有效

**负面**:
- P92-A (omo_lint schemas 拆) 仍推迟, 1257L 1 god-module error
- install-dashboard-cron 未真提交到 scripts/ 子模块, 仅 working tree
- 33 P50+ ADR drift 仍待清理 (eCOS-v5-Architecture-SSOT 等)

**关联**:
- ADR-0085 → ADR-0086: P91 install-cron (推迟) → P92 推入子模块, 完整闭环
- P92-F (adr-trend) 补完 ADR 维度: P85 adr-coverage (结构) + P89 adr-drift (引用) + P92 adr-trend (时间)
- P92 类别 delta 量化治理演进, lint +12.0 是最大改善 (X2 rule + ruff 持续集成)

## Validation

```bash
# P92 R1: ADR trend
python3 bin/adr/adr-trend-insight.py
# 期望: 44 ADRs, 100% frontmatter, 36 active + 8 archived

# P92 R2: install-dashboard-cron dry-run
bash scripts/omo/install-dashboard-cron.sh --dry-run
# 期望: 输出 governance-dashboard crontab 内容, 不真安装

# P92 R3: gov-history-stats 6 类别
python3 bin/gov-history-stats.py
# 期望: 6 类别 (lint/tests/debt/knowledge/tasks/agora) 全部有 trend

# P92 R4: dashboard
python3 bin/gac/governance-dashboard.py
# 期望: 15/15 工具全部通过

# ruff 验证
ruff check bin/adr/adr-trend-insight.py
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
- P92 R1-R3: adr-trend-insight + install-dashboard-cron 推入 + 类别趋势深化
- ADR-0085: P91 cron + gov stats

---

*最后更新: 2026-06-25 · P92 ADR 趋势洞察 + install-dashboard-cron 推入 scripts/ 子模块 收口*
