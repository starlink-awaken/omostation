---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0082: P88 omo_lint 拆解 + X2 rule template standard + governance 趋势报告

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P88
- **Extends**: ADR-0081 (P87 god-module roadmap + X2 rule add)
- **Superseded by**: (无)

## Context and Problem Statement

P87 收口后, P88 调研 3 项治理深化 + 1 项 god-module 兑现, 全部实施:

1. **omo_lint.py 1560L 拆解**: 14 god-module error 文件之一, 实际 1560L (>1500L error 阈值). 含 doc-lifecycle 子模块 (300L) 可独立
2. **X2 rule 缺乏标准文档**: P87 R2 的 x2-rule-add.py 让添加 rule 零手写 YAML, 但缺一个"什么是 X2 rule"的权威规范
3. **governance 趋势无报告工具**: governance-history 624 entries, P83 governance-history-insight 是单文件分析, 缺周/月聚合 + 趋势检测

## Decision

### D1: omo_lint.py 拆解 (P88 R1)

**目标**: 把 doc-lifecycle 子模块从 omo_lint.py 提取到独立 `omo_lint_doc.py`

**执行**:
- 创建 `projects/omo/src/omo/omo_lint_doc.py` (304L)
  - 包含: `_DOC_LIFECYCLE_PATTERNS`, `_DOC_LIFECYCLE_NEED_FRONTMATTER`, `_classify_doc`, `_parse_frontmatter`, `_check_doc_referenced`, `cmd_lint_doc_lifecycle`, `cmd_lint_doc_archival_suggestions`
- 从 `omo_lint.py` 删除原代码 (303L)
- 在 `omo_lint.py` 顶部 re-export 7 个公共符号 (含 `_classify_doc` 等内部 helper, 因为 omo_audit.py 也 import)
- omo_lint.py: **1560L → 1257L** (-303L, 19.4%)

**验证**:
- `omo lint doc-lifecycle`: 100/100 score, 🟢 HEALTHY
- `omo lint doc-archival-suggestions`: 输出正常
- `omo governance`: 100.0 A+ (omolint-doc 子模块被 audit 也调用, 重新导出保证 backward compat)

**未提交到 omo submodule**: per CLAUDE.md "子仓指针不自动 bump, 根仓只 commit 元数据". 重构 change 留 submodule working tree, 后续 submodule bump 时由 omostation 人类审批.

### D2: X2 rule template standard (P88 R2)

**新文件**: `.omo/standards/x2-rule-template-standard.md` (lifecycle: contract)

**包含**:
- 必填字段表 (9 字段)
- 添加 rule 工作流 (交互式 / 非交互式 / 模板)
- 校验工具说明 (x2-rule-lint, x2-freshness-check, x2-rule-add, governance-dashboard)
- 编号规则 (X2-FRESH-NNN 临时 / 正式)
- 5 类反模式 (action 复合字符串, target 0 匹配, threshold 非正整数, type 乱写, rule_id 重复)
- 集成 (pre-commit + dashboard)
- 8 条 references (P84-P88 ADR 链)

### D3: bin/gov-trend-report.py (P88 R3)

**新工具**: governance-history 趋势报告
- 按 daily/weekly/monthly 窗口聚合
- 输出: 总条目 / 窗口数 / 趋势信号 (stable / improving / regressing)
- 最近 5 窗口: count / avg/min/max score / grade 分布 / avg watchlist
- Top 失败 check 频率
- 趋势检测算法: 最近 3 窗口 vs 之前 3 窗口 avg score 比较 (阈值 ±2)
- Markdown 输出 (可贴 ADR)

**实测发现** (629 条 / 4 窗口 weekly):
- W23 (2026-06-02~08): avg 91.9, **14 F** (治理早期失闭环)
- W24 (2026-06-09~15): avg 94.6
- W25 (2026-06-16~22): avg 98.6
- W26 (2026-06-23~29): avg 99.6, **125/132 = 94.7% A+**
- 趋势: **improving** (W23 91.9 → W26 99.6, +7.7)
- watchlist avg: 2.10 → 0.05 (98% 下降)
- Top 失败: agora health 94 次, ruff lint 81 次, task consistency 55 次

### D4: 收口统计

**P88 工具数**: 31 → **32** 独立 bin 工具 (+1)
- `bin/gov-trend-report.py` (新)

**Standards 新增**: 1
- `.omo/standards/x2-rule-template-standard.md`

**governance-dashboard 覆盖**: 9 → **10** 工具 (+gov-trend-report)

**omo_lint.py 减重**: 1560L → 1257L (-303L, 19.4%)

**ADR 数**: 41 → **42** (P88 +1)

## Consequences

**正面**:
- omo_lint.py 减重 19.4%, doc-lifecycle 子模块独立可单独测试/演进
- X2 rule 添加有完整标准 (字段/工作流/反模式) 永久沉淀
- governance 趋势 4 周数据可视化: W23 91.9 → W26 99.6 (+7.7), 治理方法论确实在改善
- Top 失败 check 频率排名 → 治理优化优先级 (agora health / ruff lint / task consistency)
- dashboard 10 工具统一入口, 单次跑看全治理健康

**负面**:
- omo submodule 内有 working tree change (未提交), 需后续人类审批 commit
- omo_lint.py 仍有 1257L (>800L warn, <1500L error), 拆解只去掉了 doc-lifecycle 部分, 后续 P89+ 可继续拆 schemas / surfaces / mutation-ledger
- gov-trend-report 趋势检测阈值 (2.0) 是启发式, 后续可基于实际波动校准

**关联**:
- ADR-0081 → ADR-0082: 工具 (P87) → 工具 + 标准 + 趋势 (P88)
- P88 god-module 兑现: 14 error 文件之一 (omo_lint.py) 减重, 仍 1 error (1257L)
- governance 趋势 4 周演进可视化, 是 P50-P82 治理方法论验证的**最强证据**

## Validation

```bash
# P88 R1: omo_lint 拆解验证
cd projects/omo && uv run omo lint doc-lifecycle  # 100/100 score
cd projects/omo && uv run omo governance  # 100.0 A+

# P88 R2: X2 standard 存在
ls .omo/standards/x2-rule-template-standard.md  # 必填字段 + 工作流 + 反模式

# P88 R3: governance 趋势
python3 bin/gov-trend-report.py  # 4 窗口, improving 趋势
python3 bin/gov-trend-report.py --markdown  # markdown 报告
python3 bin/gov-trend-report.py --window monthly  # 月度窗口

# governance dashboard
python3 bin/gac/governance-dashboard.py  # 10/10 工具全部通过

# ruff 验证
ruff check bin/gov-trend-report.py
# 期望: All checks passed!
```

## References

- P84 R1-R3: M2 coverage + X2 freshness + DEBT-EVIDENCE rule
- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- P87 R1-R3: god-module-roadmap + x2-rule-add + dashboard 扩展
- P88 R1-R3: omo_lint 拆解 + X2 template standard + gov-trend-report
- omo_lint.py: 1560L → 1257L (-303L, 19.4%)
- governance W23 → W26: 91.9 → 99.6 (+7.7, improving)
- ADR-0081: P87 governance UX

---

*最后更新: 2026-06-25 · P88 omo_lint 拆解 + X2 template standard + governance 趋势报告 收口*
