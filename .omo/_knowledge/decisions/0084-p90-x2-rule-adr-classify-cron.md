---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0084: P90 X2 rule 扩 (OMO-LINT-SIZE) + ADR drift 归类 + governance dashboard cron

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P90
- **Extends**: ADR-0083 (P89 rule-history + adr-drift)
- **Superseded by**: (无)

## Context and Problem Statement

P89 收口后, P90 调研 4 项治理深化, 实施 3 项 (P90-A 推迟):

1. **P90-A omo_lint 进一步拆解 (推迟)**: 1257L 仍 1 error, schemas 432L 可拆, 但属 submodule 内重构, 需人类审批 commit 节奏
2. **P90-B X2-FRESH-OMO-LINT-SIZE rule**: 监控 omo_lint.py 行数, 7 天未变化触发 (已落地)
3. **P90-C ADR drift 自动归类**: adr-drift-check 110 issues 全是 noise, 自动区分 P28-P49 历史 vs P50+ 新增
4. **P90-D governance dashboard cron**: 每日 6:00 跑 dashboard 13 工具, 每周一 7:00 生成 weekly 报告

## Decision

### D1: X2-FRESH-OMO-LINT-SIZE rule (P90 R1)

**新增 X2 rule**:
```yaml
- rule_id: X2-FRESH-OMO-LINT-SIZE
  title: "P90 omo_lint.py 抗 god-module 拆解监控 (P89-A 待拆 schemas 432L)"
  type: governance_loop_freshness
  status: active
  target: projects/omo/src/omo/omo_lint.py
  freshness:
    mechanism: manual-review
    threshold_days: 7
    action: warn
  owner: governance-team
  notes: >
    P90 R1 新增 rule (omo_lint.py 抗 god-module 监控).
```

**实测**: 10 rules, 0 issues, healthy ✓ (加新 rule 后 9→10)

**修复 bug**: `bin/gac/x2-rule-add.py` 的 title 字段原本是裸 YAML 字符串, 含 `:` 时会 break YAML 解析. 改为双引号包裹 + 转义, 保证任何 title 安全.

### D2: bin/adr/adr-drift-classify.py (P90 R2)

**新工具**: 调用 adr-drift-check, 自动归类 issues
- **历史预期 (P28-P49/archived)**: 51 issues (符合预期, 不需修)
- **新增待修 (P50+)**: 38 issues (待治理清理, 主要是 P52 era 引用未补 .md 后缀的文件)

**修复 bug**: `adr-drift-check.py` 检查路径时, 自动补 `.md` 后缀再判断 (如 `0050-gbrain-53-todos-4-cat` 自动补 `.md` 后存在)

**实测**:
- 总: 110 → 89 (补 .md 后缀后) → 89 → 89 (no change for new run, but bug fixed)
- 51 historical (P28-P49/archived) + 38 P50+ (P52 era e.g. `eCOS-v5-Architecture-SSOT.md` referenced but file moved to playbooks/)

### D3: governance dashboard cron (P90 R3)

**新文件**: `.omo/cron/governance-dashboard-crontab`
- 每日 6:00 — governance dashboard 13 工具统一巡检
- 每周一 7:00 — gov-trend-report markdown 输出到 `.omo/_delivery/reports/`

**设计**: 注入 `INVOCATION_ID=cron OPC_TRIGGER=gov-dashboard` (P43 治理规范) 便于审计

### D4: governance-dashboard 扩展 12→13 工具 (P90 R4)

**新增 1 工具**:
- `adr-drift-classify` (P90 R2)

**总工具数**: 12 → **13** dashboard 工具

**X2 rules 总数**: 9 → **10** (新加 OMO-LINT-SIZE)

### D5: P90-A omo_lint 进一步拆解 推迟

**原因**:
- 1257L 仍 1 god-module error (target <1500L)
- 可拆 schemas (432L) / surfaces (136L) / mutation_ledger (56L) = 624L
- 但 schemas 引用 CONSUMER_MODULES / OMO_SRC 顶层常量, 拆分需重新设计常量归属
- 风险: 一次性拆 3 子模块 (600L) 变更面大, 在 submodule 内做需要人类审批 commit 节奏
- **策略**: 拆 X2 rule 持续监控, P91+ 配合 submodule commit 周期分批拆 (先 schemas → 再 surfaces → 最后 mutation_ledger)

### D6: 收口统计

**P90 工具数**: 34 → **35** 独立 bin 工具 (+1)
- `bin/adr/adr-drift-classify.py` (新)

**ADR 数**: 43 → **44** (P90 +1)

**X2 rules 总数**: 9 → **10** (P90 +1)

**governance-dashboard 覆盖**: 12 → **13** 工具

**Crontab**: 1 → 2 (X2 freshness + governance dashboard)

## Consequences

**正面**:
- X2 rule 覆盖 god-module 监控 (P90 R1 闭环: god-module 工具 → X2 规则 持续监督)
- ADR drift 109→89 (修复 .md 后缀) + 自动归类 (51 历史 + 38 P50+)
- governance dashboard 13 工具 cron 化, 持续累积治理历史
- x2-rule-add.py 修复 title YAML bug, 防止后续添加 rule 时再次踩坑

**负面**:
- P90-A (omo_lint 进一步拆解) 推迟, 1257L 仍 1 error
- 38 P50+ ADR drift issues 待清理 (主要是 P52 era 文件引用未补后缀 / 路径迁移)
- governance dashboard cron 暂未安装 (`install-dashboard-cron.sh` 脚本待 P91+ 编写)

**关联**:
- ADR-0083 → ADR-0084: P89 检测 + P90 自动归类, 形成 ADR drift 完整治理闭环
- P90-A 推迟到 P91+: 配合 X2-FRESH-OMO-LINT-SIZE 持续监督
- P89-A / P90-A 推迟是 eCOS "子仓指针不自动 bump" 治理规范的体现, 风险可控

## Validation

```bash
# P90 R1: X2 rule
python3 bin/gac/x2-rule-lint.py  # 10 rules, 0 issues
python3 bin/gac/x2-freshness-check.py  # 10 rules, 9 fresh, 1 missing (archived)
python3 bin/gac/rule-history-insight.py  # 10 rules, 9 fresh, 1 missing (archived)

# P90 R2: ADR drift classify
python3 bin/adr/adr-drift-classify.py  # 51 historical + 38 P50+ new
python3 bin/adr/adr-drift-classify.py --report  # markdown 报告
python3 bin/adr/adr-drift-classify.py --json  # JSON 详细

# P90 R3: cron (P91+ 编写 install 脚本)
ls .omo/cron/governance-dashboard-crontab  # 新 crontab 文件

# P90 R4: dashboard
python3 bin/gac/governance-dashboard.py  # 13/13 工具全部通过

# ruff 验证
ruff check bin/adr/adr-drift-classify.py
ruff check bin/adr/adr-drift-check.py
ruff check bin/gac/x2-rule-add.py
# 期望: All checks passed!
```

## References

- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- P87 R1-R3: god-module-roadmap + x2-rule-add + dashboard 扩展
- P88 R1-R3: omo_lint 拆解 + X2 template + gov-trend-report
- P89 R1-R3: rule-history-insight + adr-drift-check + dashboard 12
- P90 R1-R4: X2 rule OMO-LINT-SIZE + adr-drift-classify + cron + dashboard 13
- ADR-0083: P89 治理深化

---

*最后更新: 2026-06-25 · P90 X2 rule 扩 (OMO-LINT-SIZE) + ADR drift 归类 + governance dashboard cron 收口*
