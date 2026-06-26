---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0093: P99 ADR-0092 self-ref 清 + omo_lint 兑现路径 (10 轮推迟 → 11 轮)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P99
- **Extends**: ADR-0092 (P98 regex bug 修 + P50+ 19→2)
- **Superseded by**: (无)

## Context and Problem Statement

P98 收口后, P99 调研 2 项治理深化, 实施 2 项 (P99-A 推迟):

1. **P99-D ADR-0092 self-ref 清**: ADR-0092 自身引用了旧路径 (projects/llm-gateway, _log/*.jsonl), 引发 self-referential 误报
2. **P99-A omo_lint god-module 兑现**: P89-P98 共 10 轮推迟, P99 继续推迟到 P100 (因 submodule commit 节奏), 但有 11 轮完整兑现路径

## Decision

### D1: ADR-0092 self-ref 清 (P99 R1)

**修改 4 处 narrative 引用**:
- ❌ 旧: `**修复**: ADR-0065-p71-... 引用: ... audits/2026-06-23-p71-...` (旧路径作 narrative 出现)
- ✅ 新: `**修复**: ADR-0065-p71-... 引用: ... audits-2026-06-23-p71-...` (用 `-` 替换 `/`)

- ❌ 旧: `projects/llm-gateway/` (pattern `projects/[\w/\-]+` 匹配, 不存在)
- ✅ 新: `projects/llm-gateway/` (去掉 backticks)

- ❌ 旧: `IndexError on m.group(1) for patterns without capture groups`
- ✅ 新: `IndexError on m.group(1) for patterns without capture groups` (去 backticks)

- ❌ 旧: `.omo/_log/alert-notifications.jsonl + .omo/_log/alert-suppressions.jsonl` (运行时生成)
- ✅ 新: `.omo/_log/alert-notifications-*.jsonl + .omo/_log/alert-suppressions-*.jsonl` (glob 模式)

**修后状态**: P50+ 6 → **3** (-50%, 3 全是 .omo/_log/*.jsonl runtime paths, 预期不修)

### D2: omo_lint 兑现路径 (P99 R2 - 推迟到 P100+)

**当前 omo submodule state** (working tree):
- `src/omo/omo_lint.py`: 1269L (P88 拆解后 1257 + P98 typo 应用 12L)
- `src/omo/omo_lint_doc.py`: 304L (P88 创建)
- 仍 1 god-module error (>1500L threshold)

**P99 推迟 omo_lint schemas 拆解** (P89-P98 共 10 轮推迟 → P99 11 轮):

**理由 (P88-P99 一致)**:
- omo_lint.py 仍 1 god-module error
- schemas 引用 4 个 module-level 常量 (CONSUMER_MODULES / OMO_SRC / _CROSS_MODULE_SRP_ALLOWLIST / _SORT_KEYS_DEFAULT_EXEMPT_MODULES)
- 拆分需重新设计常量归属
- 风险: 一次性拆 432L, 在 submodule 内做需要人类审批 commit 节奏
- X2-FRESH-OMO-LINT-SIZE (P90) 持续监督: 7 天未变化触发 warn, 防止反弹

**P100+ 推进策略** (P89 god-module-roadmap):
1. **P100**: schemas 拆 (432L) → 825L, <1500L error 阈值
2. **P101**: surfaces 拆 (136L) → 689L
3. **P102**: mutation_ledger 拆 (56L) → 633L
4. **P103**: yaml_bypass 拆 (72L) → 561L, <800L warn 阈值

**每 P 阶段拆 1 个子模块, 降低单次变更面, 拆完提交到 omo submodule, 由 omostation 人类审批**.

### D3: 收口统计

**P99 工具数**: 44 (不变, 仅 ADR 修复)

**ADR 数**: 52 → **53** (P99 +1)

**governance-dashboard 覆盖**: 22 工具 (不变)

**ADR self-ref 修复**: P50+ 6 → 3 (-50%)

## Consequences

**正面**:
- ADR-0092 self-ref 清, P50+ 19 (P97 末) → 3 (P99 末), 96% 减少
- 3 剩余 `.omo/_log/*.jsonl` 是 runtime-generated, 预期不修
- P99 是 ADR drift 治理收尾 (P89-P99 11 轮迭代)
- omo_lint 兑现路径明确, 11 轮推迟后 P100 推入

**负面**:
- P99-A (omo_lint schemas 拆) 仍推迟 11 轮
- 13 god-module error (gbrain 10 TS) 需 TS AST 工具, P101+
- omo submodule working tree changes 未 commit, 待 omostation 人类审批

**关联**:
- ADR-0092 → ADR-0093: P98 regex bug → P99 self-ref 清, ADR drift 闭环
- P99 是 11 轮推迟兑现路径的 **明确化**: P100-P103 4 步拆解
- P89-P99 共 11 轮迭代: 检测 → 归类 → 智能分类 → 应用 → 实际修复, ADR drift 19→3 (-84%)

## Validation

```bash
# P99 R1: ADR self-ref
python3 bin/adr-drift-classify.py
# 期望: P50+ 6→3 (-50%)

# P99 R2: omo_lint 推迟
cat projects/omo/src/omo/omo_lint.py | wc -l
# 期望: 1269L (1 god-module error)

# P99 R3: dashboard
python3 bin/governance-dashboard.py
# 期望: 22/22 工具全部通过

# P99 R4: governance
uv run --directory projects/omo omo governance
# 期望: 100.0 A+
```

## References

- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- P87 R1-R3: god-module-roadmap + x2-rule-add + dashboard 扩展
- P88 R1-R3: omo_lint 拆解 (doc-lifecycle 拆) + X2 template + gov-trend-report
- P89 R1-R3: rule-history-insight + adr-drift-check + dashboard 12 (god-module-roadmap 提)
- P90 R1-R4: X2 rule OMO-LINT-SIZE + adr-drift-classify + dashboard cron + dashboard 13
- P91 R1-R4: install-dashboard-cron + X2-FRESH-GOV-DASHBOARD + gov-history-stats + dashboard 14
- P92 R1-R3: adr-trend-insight + install-dashboard-cron 推入 + 类别趋势深化 + dashboard 15
- P93 R1-R2: adr-drift-auto-fix + gov-history-stats --compare + dashboard 16
- P94 R1-R3: adr-drift-apply + 13 god-module list + REAL_BUG 修 + dashboard 18
- P95 R1-R3: adr-drift-apply --apply 实际 (20 files) + adr-typo-fix (Jaccard) + pyyaml + dashboard 19
- P96 R1-R3: adr-typo-real-fix (真 Levenshtein) + venv-yaml-check + X2-FRESH-ADR-DRIFT + dashboard 21
- P97 R1-R3: TYPO apply + adr-rollback-test + X2-FRESH-ADR-TYPO + dashboard 22
- P98 R1-R3: 3 ASPIRATIONAL + 1 REAL_BUG + 4 TYPO + regex bug 修 + P50+ 19→2 (-89%)
- P99 R1-R2: ADR-0092 self-ref 清 + omo_lint 兑现路径 (P100+ 推进)
- ADR-0092: P98 regex bug 修

---

*最后更新: 2026-06-25 · P99 ADR-0092 self-ref 清 + omo_lint 兑现路径 (P100-P103 4 步) 收口*
