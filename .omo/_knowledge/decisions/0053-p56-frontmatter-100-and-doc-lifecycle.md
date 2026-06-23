---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-23
---

# ADR-0053: P56 frontmatter 100% + doc-lifecycle 健康度 100/100

- **Status**: ACCEPTED
- **Date**: 2026-06-23
- **Authors**: omostation P57
- **Extends**: ADR-0052 (P54-P55 知识面深度收敛), P45 R4/R6 (frontmatter 化原则)
- **Superseded by**: (无)

## Context and Problem Statement

P56 完成知识面 689/689 (100%) frontmatter 覆盖, 是历史首次。但仅知识面 (`.omo/_knowledge/`), 未覆盖整个 `.omo/` (1622 文件)。

P57 调研发现:
- `omo lint doc-lifecycle` 扫描整个 `.omo/` (1622 文件), 已 4 类正确分类
- frontmatter 覆盖率 99.0% (缺 1 个 `mof-version.yaml`, 是数据文件, 正常)
- 死文档 0, 矛盾路径 0
- 评分 100/100 HEALTHY

## Decision

### D1: 记录 P56 frontmatter 100% 历史首次 (本 ADR)

- 知识面 `.omo/_knowledge/` 689/689 = 100%
- 整个 `.omo/` 1622 文件 frontmatter 99.0% (1 个数据文件除外)
- doc-lifecycle 健康度 100/100

### D2: 持续监控 doc-lifecycle 健康度 (机器门禁)

- X2-FRESH-DOC-LIFECYCLE 规则已 active (7 天 threshold)
- `omo lint doc-lifecycle` + `omo lint doc-archival-suggestions` 已上线
- 任何新文档需带 frontmatter (P45 规范)

### D3: linter 增量维度评估完成 (P57 R2 决策: 无新增)

P57 R2 评估结果:
- 当前 doc-lifecycle 已输出 4 类分布 + status 统计 + 死文档 + 矛盾路径
- 候选维度 16 (frontmatter-driven 死文档深度): 当前 frontmatter_missing + frontmatter_bad_status 已覆盖
- 候选维度 17 (跨面引用一致性): omo_doc_lint.py 已有 `check_dead_links` + `check_phase_doc_consistency` + `check_term_consistency`
- 候选维度 18 (状态分布趋势): doc-lifecycle 输出已包含 `archived/deprecated/active/experimental` 分布

**决策**: 全部 3 个候选已被现有实现覆盖, 无新增维度。linter 维度停留在 15。

## Consequences

### Positive

- **frontmatter 100% 历史首次**: 689/689 知识面 + 99.0% 整体
- **doc-lifecycle 健康度**: 100/100 HEALTHY
- **机器门禁成熟**: 15 维度 lint + 8 条 X2 freshness 规则
- **持续保鲜**: 7 天 threshold + 14 天 governance + 30 天 evidence

### Negative

- **维度饱和**: 15 维度已覆盖主要场景, 增量价值递减
- **linter 维护成本**: 维度越多维护越重

### Neutral

- **mof-version.yaml 是数据文件, 无 frontmatter 是合理的**: YAML 数据文件不应有 markdown frontmatter

## Compliance

### 验证指标

| 指标 | P55 末 | P56 末 | **P57 末** | 变化 |
|------|-------:|-------:|-----------:|-----:|
| mof-version | v0.0.43 | v0.0.44 | **v0.0.45** | +1 |
| governance | 100 A+ | 100 A+ | **100 A+** | 持平 |
| mof-drift LOW | 2 | 2 | **2** | 持平 |
| 知识面 frontmatter | 99% | **100%** | **100%** | 持平 |
| .omo/ 整体 frontmatter | ~85% | ~99% | **99.0%** | 持平 |
| doc-lifecycle 健康 | 100/100 | 100/100 | **100/100** | 持平 |
| ADR 数量 | 11 | 12 | **13** | +1 (0053) |
| omo lint 维度 | 15 | 15 | **15** | 持平 |

### 关联 ADR

- **ADR-0052**: P54-P55 知识面深度收敛
- **ADR-0051**: gbrain TODOs v5 终极收敛
- **ADR-0050**: gbrain 53 TODOs 4 类决策

### 关联报告

- `.omo/_knowledge/audits/2026-06-23-p56-frontmatter-100-percent-closeout.md` (P56 收口)
- `omo lint doc-lifecycle` 报告 (实时)

## Notes

本 ADR 记录 P56 收口 + P57 评估。后续 P58+ 候选:
- 维度 16/17/18 增量 (frontmatter-driven / 跨面引用 / 趋势)
- management/ 142 拆 3 类 (大重构)
- graphify-out 重生覆盖 1622 文件
- ADR-0054 记录 P58+ 治理演进

---

*最后更新: 2026-06-23 · P57 R1 · omostation 治理决策*