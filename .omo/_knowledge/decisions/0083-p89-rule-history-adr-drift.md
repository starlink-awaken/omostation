---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0083: P89 X2 rule 状态洞察 + ADR drift check + 治理深化

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P89
- **Extends**: ADR-0082 (P88 omo_lint 拆解 + X2 template + gov-trend)
- **Superseded by**: (无)

## Context and Problem Statement

P88 收口后, P89 调研 2 项治理深化 + 1 项 P89-A 计划, 实施情况:

1. **X2 rule 状态无集中视图**: x2-freshness-check (P84) 只能告诉"超期了", 但缺"全部 rules 的状态 + drift 报告关联"全景
2. **ADR 引用 drift 无检查**: ADR 提及的 `.omo/...` 路径 / bin 工具 / ADR-XXXX 编号, 是否还存在? 41 个 ADR 累积后没人验证
3. **omo_lint 进一步拆解 (P89-A)**: 推迟, 因属 submodule 内重构, 需人类审批 commit 节奏

## Decision

### D1: bin/gac/rule-history-insight.py (P89 R1)

**新工具**: X2 rule 状态 + drift 报告关联分析

**关键设计修正 (迭代 5 轮)**:
- 初始设计按 rule_id 字符串匹配 drift → 误报 (drift 报告用 kind, 不用 rule_id)
- 改为 target 路径关键词匹配 → 太松 (212/9 误报)
- 改为 target path segments 匹配 → 太严 (0 命中)
- 改用 target_age_days(target, root) 直接读 mtime, 跟 threshold 比较 → 8/9 fresh ✓

**实测** (9 rules, 212 drift 报告):
- 🟢 8 fresh (target 在 threshold 内)
- ❌ 1 missing: X2-FRESH-ARCHIVED-LLMGATEWAY (target llm-gateway/ 已删, archived 状态)
- Top drift 关键词: `projects/` 636 次, `omo/` 53 次

### D2: bin/adr/adr-drift-check.py (P89 R2)

**新工具**: ADR 内容引用健康度检查

**关键设计修正 (迭代 3 轮)**:
- ADR 编号字符串比较 (4 位零填充) — 否则 `0081 → 81` 前导 0 丢失
- known_adr_numbers 总是用全量 (即使 --adr 过滤单条)
- 路径检查忽略: glob / 短名 (< 8 chars) / _archive / .omc (gitignored)
- 退出码: 信息性 (exit 0, 即使有 issues), dashboard 友好

**实测** (41 ADRs):
- 109 missing path issues (P28-P49 历史 archived 引用, 预期)
- ADR-0082 (P88): 2 path issues (submodule working tree, 预期)
- ADR-0001-0008 (P28): 全部 missing (历史路径, 预期)

### D3: dashboard 扩展 (P89 R3)

**新增 2 工具**:
- `rule-history-insight` (9 rules 状态)
- `adr-drift-check` (信息性, exit 0)

**总工具数**: 10 → **12**

### D4: P89-A omo_lint 进一步拆解 推迟

**理由**:
- omo_lint.py 当前 1257L (已从 1560L 减 19.4%, P88 R1)
- 进一步拆解 schemas (432L) / surfaces (136L) / mutation_ledger (56L) → ~600L, 目标 <800L warn
- 但 P88 R1 的拆解尚未 commit 到 omo submodule (working tree)
- 需人类审批 commit 节奏, 避免连续 P 阶段都在 submodule 内做大改
- **P90+ 推进**: 配合 X2-FRESH-OMO-LINT rule (新) 持续拆解

### D5: 收口统计

**P89 工具数**: 32 → **34** 独立 bin 工具 (+2)
- `bin/gac/rule-history-insight.py` (新)
- `bin/adr/adr-drift-check.py` (新)

**ADR 数**: 42 → **43** (P89 +1)

**governance-dashboard 覆盖**: 10 → **12** 工具

**P89 关键发现**:
- X2 rule 健康度: 8/9 fresh (1 archived, 符合预期)
- ADR drift: 109 missing path (全部 P28-P49 历史 archived, 符合预期)
- 最近 ADR (P50-P89) 引用健康度 100%

## Consequences

**正面**:
- X2 rule 状态有集中视图 (target age + drift 关联)
- ADR 内容引用有自动化检查 (4 位编号零填充坑被发现并修复)
- 工具退出码设计为信息性 (P89-A 拆分决策基于信息)
- dashboard 12 工具统一入口

**负面**:
- P89-A (omo_lint 进一步拆解) 推迟, 1257L 仍 1 error
- 109 ADR drift issues 包含大量历史噪音, 工具不能自动归类 archived
- rule-history-insight 迭代 5 轮才稳定 (target mtime 是最终方案)

**关联**:
- ADR-0082 → ADR-0083: P88 趋势 + P89 状态, 形成 X2 治理完整闭环
- P89-A 推迟: 拆解节奏需配合 submodule commit 周期, 后续 P90+ 推进
- 工具数从 P82 的 28 → P89 的 34 (+6 治理工具, +21%)

## Validation

```bash
# P89 R1: rule-history
python3 bin/gac/rule-history-insight.py
# 期望: 8 fresh, 1 missing (archived)

# P89 R2: adr-drift
python3 bin/adr/adr-drift-check.py
# 期望: 109 issues (历史 archived 引用, 预期)
python3 bin/adr/adr-drift-check.py --adr ADR-0082
# 期望: 2 issues (submodule working tree, 预期)

# P89 R3: dashboard
python3 bin/gac/governance-dashboard.py
# 期望: 12/12 工具全部通过

# ruff 验证
ruff check bin/gac/rule-history-insight.py
ruff check bin/adr/adr-drift-check.py
# 期望: All checks passed!
```

## References

- P83 R1-R3: governance-history + drift-history + gitignore 感知
- P84 R1-R3: M2 coverage 修正 + X2 freshness + DEBT-EVIDENCE rule
- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- P87 R1-R3: god-module-roadmap + x2-rule-add + dashboard 扩展
- P88 R1-R3: omo_lint 拆解 + X2 template + gov-trend-report
- P89 R1-R3: rule-history-insight + adr-drift-check + dashboard 扩展 12
- ADR-0082: P88 治理深化

---

*最后更新: 2026-06-25 · P89 X2 rule 状态洞察 + ADR drift check + 治理深化 收口*
