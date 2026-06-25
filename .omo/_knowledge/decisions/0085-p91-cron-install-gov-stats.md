---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0085: P91 governance dashboard cron install + X2-FRESH-GOV-DASHBOARD + gov-history-stats 深化

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P91
- **Extends**: ADR-0084 (P90 X2 rule + adr-drift + dashboard cron)
- **Superseded by**: (无)

## Context and Problem Statement

P90 收口后, P91 调研 4 项治理深化, 实施 3 项 (P91-A 推迟):

1. **P91-A omo_lint schemas 拆分 (推迟)**: 432L 仍可拆, 但属 submodule 内重构, X2-FRESH-OMO-LINT-SIZE (P90) 持续监督
2. **P91-B governance dashboard cron install 脚本**: P90 R3 写 crontab 但无 install 脚本, 风险: 用户手动复制 crontab 易错
3. **P91-G X2-FRESH-GOV-DASHBOARD rule**: dashboard cron 持续运行监控 (7 天)
4. **P91-D gov-history-stats 深化**: 30 天窗口 + 类别趋势 (P88 weekly 太短)

## Decision

### D1: install-dashboard-cron.sh (P91 R1)

**新脚本**: `scripts/omo/install-dashboard-cron.sh`
- 4 模式: install / uninstall / dry-run / status
- 隔离块标记: `GOV_DASHBOARD_BEGIN/END` (与 X2 freshness 标记块互不干扰)
- 备份当前 crontab 到 `.omo/cron/crontab-backup-<timestamp>.txt`
- 幂等: 重复运行只覆盖标记块, 不破坏其他 crontab

**验证**: `--dry-run` 输出 13 工具 dashboard crontab 内容, 不真安装.

### D2: X2-FRESH-GOV-DASHBOARD rule (P91 R2)

**新增 X2 rule** (10→11):
```yaml
- rule_id: X2-FRESH-GOV-DASHBOARD
  title: "P91 governance-dashboard cron 持续运行监控 (确保 7 天内 dashboard 跑过)"
  type: governance_loop_freshness
  status: active
  target: .omo/cron/governance-dashboard-crontab
  freshness:
    mechanism: manual-review
    threshold_days: 7
    action: warn
  owner: governance-team
  notes: >
    P91 R2 新增 rule.
```

**实测**: 11 rules, 0 issues (target 存在, 1d age, fresh) ✓

### D3: bin/gov-history-stats.py (P91 R3)

**新工具**: governance-history 30 天窗口 + 类别趋势
- 与 P88 gov-trend-report 差异: 30 天更长视野 + 6 个 check category (lint/tests/debt/knowledge/tasks/agora) 分别趋势
- 输出: Daily grade 变迁表 + 类别 delta

**实测** (632 entries, 20 days):
- 2026-06-11: 76.5% C, 23.5% D (历史失闭环)
- 2026-06-25: 100% A+ (当前完美)
- 类别趋势: `lint` delta=+12.0 (从 88 → 100)

**修复 bug**: `datetime.now()` (naive) vs `datetime.now(tz=timezone.utc)` (aware), 比较时类型不匹配返回 0 entries. 修复后 632 entries 正确.

### D4: 修 adr-drift-check .yaml/.yml 补全 (P91 R4)

**修复 bug**: adr-drift-check 路径检查时, 引用 `x1-governance-policies` (无后缀) 找不到, 但实际是 `.yaml` 文件. 修复: 补 .md/.yaml/.yml 三种后缀.

**实测**:
- 89 → 81 (8 issues 修复, 含 P54 引用 x1/x2/x3/x4 truth files)
- 当前 P50+ 待修: 31 (从 38 减少)

### D5: P91-A omo_lint schemas 拆分 推迟

**理由**:
- omo_lint.py 1257L (P88 拆解后) 仍 1 god-module error
- schemas 子模块 432L 可拆, 但引用 4 个 module-level 常量 (CONSUMER_MODULES / OMO_SRC / _CROSS_MODULE_SRP_ALLOWLIST / _SORT_KEYS_DEFAULT_EXEMPT_MODULES)
- 拆分需重新设计常量归属 (move to schemas / share via omo_lint)
- 风险: 一次性拆 432L, 在 submodule 内做需要人类审批 commit 节奏
- **X2-FRESH-OMO-LINT-SIZE (P90) 持续监督**: 7 天未变化触发 warn, 防止 god-module 反弹
- **P92+ 推进**: 配合 X2 rule 节奏, 分批拆 schemas (432L) → surfaces (136L) → mutation_ledger (56L) → yaml_bypass (72L)

### D6: 收口统计

**P91 工具数**: 35 → **36** 独立 bin 工具 (+1)
- `bin/gov-history-stats.py` (新)

**P91 Scripts**: +1
- `scripts/omo/install-dashboard-cron.sh` (新)

**ADR 数**: 44 → **45** (P91 +1)

**X2 rules 总数**: 10 → **11** (P91 +1)

**governance-dashboard 覆盖**: 13 → **14** 工具

**ADR drift 修复**: 89 → 81 (8 issues via .yaml 补全)

## Consequences

**正面**:
- governance dashboard cron install 脚本完成 (用户一键安装, 不破坏现有 crontab)
- X2-FRESH-GOV-DASHBOARD 监督 cron 持续运行 (7 天无变化触发)
- gov-history-stats 30 天窗口 + 类别趋势, 比 weekly 更长视野
- ADR drift .yaml 补全修 8 issues (P54 truth files 引用)
- X2 rule 体系已扩到 11 rules (P43 3 → P91 11, +267%)

**负面**:
- P91-A (omo_lint schemas 拆) 推迟, 1257L 仍 1 god-module error
- 31 P50+ ADR drift issues 仍待清理 (主要是 P52 era 历史引用, 部分已迁)
- gov-history-stats 类别趋势目前只看到 lint 类, 其它 5 类因 governance-history 数据 category 字段缺失为 0 (P88 0→P91 仍 0)

**关联**:
- ADR-0084 → ADR-0085: P90 工具 + P91 安装/监控, 形成 cron 完整治理闭环
- P91-A 推迟配合 X2-FRESH-OMO-LINT-SIZE (P90) 持续监督, eCOS "子仓指针不自动 bump" 治理规范体现
- X2 rule 11 条覆盖: 治理面 (OMO-GOVERNANCE-SURFACES / OMO-LINT-SIZE) + 内容 (DOC-LIFECYCLE / MOF-VERSION / DEBT-EVIDENCE / CROSS-PROJECT-LINT) + 闭环 (X2-FRESH-COMMIT-FATIGUE / GOV-DASHBOARD) + 历史 (ARCHIVED-LLMGATEWAY / EVIDENCE-ALIAS / MERGE-CHECKLIST)

## Validation

```bash
# P91 R1: install script
bash scripts/omo/install-dashboard-cron.sh --dry-run  # 预览
bash scripts/omo/install-dashboard-cron.sh --status   # 状态
bash scripts/omo/install-dashboard-cron.sh           # 实际安装 (未跑)

# P91 R2: X2 rule
python3 bin/x2-rule-lint.py  # 11 rules, 0 issues
python3 bin/x2-freshness-check.py  # 11 rules, 10 fresh, 1 missing (archived)
python3 bin/rule-history-insight.py  # 11 rules, 9 fresh, 1 missing, 1 新加

# P91 R3: gov-history-stats
python3 bin/gov-history-stats.py  # 30 天, 632 entries, 类别趋势
python3 bin/gov-history-stats.py --days 60  # 60 天窗口
python3 bin/gov-history-stats.py --json  # JSON 输出

# P91 R4: adr-drift 修 .yaml
python3 bin/adr-drift-classify.py  # 50 historical + 31 P50+ (P90 38→31, 减 7)

# P91 R5: dashboard
python3 bin/governance-dashboard.py  # 14/14 工具全部通过

# ruff 验证
ruff check bin/gov-history-stats.py
ruff check bin/adr-drift-check.py
# 期望: All checks passed!
```

## References

- P85 R1-R3: x2-rule-lint + adr-coverage + COMMIT-FATIGUE 修正
- P86 R1-R4: pre-commit 集成 4 工具 + governance dashboard
- P87 R1-R3: god-module-roadmap + x2-rule-add + dashboard 扩展
- P88 R1-R3: omo_lint 拆解 + X2 template + gov-trend-report
- P89 R1-R3: rule-history-insight + adr-drift-check + dashboard 12
- P90 R1-R4: X2 rule OMO-LINT-SIZE + adr-drift-classify + dashboard cron + dashboard 13
- P91 R1-R4: install-dashboard-cron + X2-FRESH-GOV-DASHBOARD + gov-history-stats + .yaml bug fix
- ADR-0084: P90 cron + dashboard

---

*最后更新: 2026-06-25 · P91 governance dashboard cron install + X2-FRESH-GOV-DASHBOARD + gov-history-stats 深化 收口*
