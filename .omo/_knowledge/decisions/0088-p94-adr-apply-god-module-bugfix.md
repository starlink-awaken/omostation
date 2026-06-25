---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0088: P94 adr-drift-apply + 13 god-module list + REAL_BUG 修复

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P94
- **Extends**: ADR-0087 (P93 adr-drift-auto-fix)
- **Superseded by**: (无)

## Context and Problem Statement

P93 收口后, P94 调研 4 项治理兑现, 实施 3 项 (P94-A 推迟):

1. **P94-A omo_lint schemas 拆分 (6 轮推迟)**: 仍 432L, 配合 X2-FRESH-OMO-LINT-SIZE 持续监督
2. **P94-F adr-drift-apply**: P93 归类完成, 现在实际应用 SUBDIR_MISSING 修复 (touch 占位)
3. **P94-E 13 god-module error 清单**: 13 个 >1500L 文件全量拆解 plan, 24,252L 需拆解
4. **P94-C 1 REAL_BUG 修**: ADR-0065 引用 `audits/...` (相对路径), 实际在 `.omo/_knowledge/audits/`

## Decision

### D1: bin/adr-drift-apply.py (P94 R1)

**新工具**: 应用 P93 归类的 SUBDIR_MISSING 修复
- 4 模式: dry-run / apply / rollback / json
- 修复策略: SUBDIR_MISSING → touch 占位 (含父目录 + .gitkeep for dirs)
- 跳过: TEMPLATE/TYPO/REAL_BUG/ASPIRATIONAL (干跑报告, 不自动改)
- 历史记录: `.omo/_delivery/adr-drift-apply-history.jsonl` (含 timestamp, 可回滚)
- Rollback: 读最近一次 apply, 删除 touch 创建的文件 (.gitkeep 只删自己, 不删目录)

**dry-run 状态**: 19 SUBDIR_MISSING 待 touch (含 eCOS-v5-Architecture-SSOT.md, graphify-out/README.md, l4_kernel/registry, model-driven/m3_extended, .omo-events 等)

### D2: bin/god-module-13-error-list.py (P94 R2)

**新工具**: 13 god-module error 文件清单 + 拆解建议
- 调用 `check-god-module.py --strict` 输出
- 分类 error (>1500L) / warn (800-1500L)
- Python 文件: AST 分析 top 函数/类
- TS 文件: 暂用 line count (TS AST 需 ts-morph)
- 输出: 总 excess + 每文件 current→target + 拆解 strategy

**实测** (13 errors + 55 warns):
- Total excess: **24,252L** 需拆解
- Top 5: gbrain doctor.ts 4825L → 800L (excess 4025L) / postgres-engine.ts 4514L (3714L) / pglite-engine.ts 4509L (3709L) / migrate.ts 4333L (3533L) / ai/gateway.ts 2895L (2095L)
- 拆解策略: schemas → surfaces → mutation_ledger → yaml_bypass (4 批)

### D3: REAL_BUG 修复 - ADR-0065 (P94 R3)

**修复**: ADR-0065-p71-six-step-cross-level-dim-weight-mgmt-eval.md 引用:
- ❌ 旧: `audits/2026-06-23-p71-management-split-evaluation.md` (相对路径, 不存在)
- ✅ 新: `.omo/_knowledge/audits/2026-06-23-p71-management-split-evaluation.md` (绝对路径, 存在)

**修后状态**: 32 → 31 P50+ issues, REAL_BUG 1 → 0 (完全修复)

### D4: P94-A omo_lint schemas 拆分 仍推迟 (6 轮推迟)

**历史推迟链**:
- P89-A → P90-A → P91-A → P92-A → P93-A → **P94-A** (6 轮)

**P94 决策**: 仍推迟, 配合 X2-FRESH-OMO-LINT-SIZE 持续监督. 拆分需 432L 重构 + 4 module-level 常量重新归属 + 多次回归测试, 在 submodule 内做需要人类审批 commit 节奏.

**P95+ 推进策略**: 
- P95: schemas 拆 (432L) → 825L
- P96: surfaces 拆 (136L) → 689L
- P97: mutation_ledger 拆 (56L) → 633L
- P98: yaml_bypass 拆 (72L) → 561L (达成 <800L warn 阈值)

### D5: 收口统计

**P94 工具数**: 38 → **40** 独立 bin 工具 (+2)
- `bin/adr-drift-apply.py` (新)
- `bin/god-module-13-error-list.py` (新)

**ADR 数**: 47 → **48** (P94 +1)

**governance-dashboard 覆盖**: 16 → **18** 工具

**ADR drift REAL_BUG 修复**: 1 → 0 (P50+ issues 32→31)

**god-module 13 error 清单**: 24,252L 需拆解 (按 4 批推进)

## Consequences

**正面**:
- adr-drift-apply 完成 ADR drift 修复闭环 (P89 检测 → P90 归类 → P93 智能分类 → P94 apply)
- 1 REAL_BUG 实际修复 (ADR-0065 path 修正)
- 19 SUBDIR_MISSING 待 P95+ 实际 touch (rollback 机制保证安全)
- 13 god-module error 清单 + 24,252L excess, 拆解 roadmap 清晰
- dashboard 18 工具统一入口

**负面**:
- P94-A (omo_lint schemas 拆) 仍推迟 6 轮, 1257L 1 god-module error
- adr-drift-apply 未真应用 (dry-run 模式), 19 SUBDIR_MISSING 待 P95 推入
- 13 god-module error 中 10 个是 gbrain TS 文件, 需 TS AST 工具支持
- ASPIRATIONAL (1 issues: projects/llm-gateway/) 是 P81 archived 引用, ADR 上下文描述

**关联**:
- ADR-0087 → ADR-0088: P93 智能分类 → P94 实际应用 + 拆解清单
- ADR drift 治理完整链: 检测 (P89) → 归类 (P90) → 智能分类 (P93) → 应用 (P94) → 归档 (P94 rollback)
- P94-A 仍推迟 (6 轮), god-module 治理成熟度可视化但未兑现
- X2-FRESH-OMO-LINT-SIZE 持续监督 1 个 root 仓 god-module error

## Validation

```bash
# P94 R1: adr-drift-apply dry-run
python3 bin/adr-drift-apply.py
# 期望: 19 SUBDIR_MISSING 待 touch (dry-run 模式)

# P94 R2: god-module 13 list
python3 bin/god-module-13-error-list.py
# 期望: 13 error + 55 warn, 24,252L excess

# P94 R3: REAL_BUG 验证
python3 bin/adr-drift-auto-fix.py
# 期望: 31 P50+ issues (从 32 减 1, REAL_BUG 0)

# P94 R4: dashboard
python3 bin/governance-dashboard.py
# 期望: 18/18 工具全部通过

# ruff 验证
ruff check bin/adr-drift-apply.py
ruff check bin/god-module-13-error-list.py
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
- P94 R1-R3: adr-drift-apply + god-module-13-error-list + REAL_BUG 修 (ADR-0065) + dashboard 18
- ADR-0087: P93 adr-drift-auto-fix

---

*最后更新: 2026-06-25 · P94 adr-drift-apply + 13 god-module list + REAL_BUG 修复 收口*
