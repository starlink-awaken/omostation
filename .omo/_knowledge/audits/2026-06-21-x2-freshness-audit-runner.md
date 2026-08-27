---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# X2 Freshness Audit Runner — P43 R7 闭环触发器

**日期**: 2026-06-21
**状态**: 实施完毕 (R7 docs-convergence → R7.1 audit runner)
**关联任务**: `TASK-DEBT-CLOSURE-EVIDENCE-20260620` (后续) · `TASK-X2-FRESHNESS-CRON` (新)
**关联 SSOT**:
- `.omo/_truth/x2-freshness-rules.yaml` (3 条 P43 衍生巡检规则)
- `L0-constraints.yaml:CR-DEBT-CLOSURE-EVIDENCE-01` (evidence 强约束)
- `.omo/standards/omo-governance-surfaces.md` (三层治理契约)

---

## 0. 诚实话语前置 (Reader-Disambiguation)

P43 R6 docs-convergence 增加了 3 条 X2 freshness 规则, 但**只有声明没有实施** — 没有 cron 触发的执行器。
本任务首次落地 X2 巡检 runner, 立刻发现 5 项 debt closure 缺 evidence 的真实漂移,
并通过 X1-DEBT-EVIDENCE-CLOSURE-20260620 + L0:CR-DEBT-CLOSURE-EVIDENCE-01 强制约束闭环。

**这不是"我们以为治理达标" — 这是真实信号被新工具捕获**。

---

## 1. 实施的 3 个 X2 巡检检查

| Rule ID | 触发频率 | 检查内容 | SSOT |
|---------|---------|----------|------|
| `X2-FRESH-DEBT-EVIDENCE-INTEGRITY` | 14 天 | debt.yaml `lifecycle_state=closed` 是否含 ≥ 20 字符 `resolution_evidence`；`deferred` 是否含 `next_review_at` + `gate_level` | `.omo/debt/items/*.yaml` |
| `X2-FRESH-CROSS-PROJECT-LINT` | 7 天 | 8 子项目 `ruff check src/` 是否 0 errors | `projects/*/src/**/*.py` |
| `X2-FRESH-MOF-VERSION-BUMP` | 30 天 | `.omo/_truth/mof-version.yaml` 最近一次 version 变更距今天数 ≤ 30 | git timestamp |

## 2. 第一轮真实捕获 (2026-06-21)

```json
{
  "rules_total": 3,
  "rules_ok": 0,
  "rules_warning": 3,
  "results": [
    {"rule_id": "X2-FRESH-DEBT-EVIDENCE-INTEGRITY", "status": "warning",
     "stale": 5, "total": 37,
     "details": [5 个 debt (LEGACY-DIRECT-OMO-IO-BACKLOG / CARDS-FRONTMATTER-PARSE
              / OMC-GBRAIN-PERSISTENCE / OMC-METAOS-OMO-PLANE / SWARM-ENGINE-...)
              closed 但无 resolution_evidence]},
    {"rule_id": "X2-FRESH-CROSS-PROJECT-LINT", "status": "warning",
     "stale": 1, "total": 8, "details": [{"project": "omo", "errors": 2}]},
    {"rule_id": "X2-FRESH-MOF-VERSION-BUMP", "status": "warning",
     "stale": 1, "total": 0, "details": "parse error (fixed)"}
  ]
}
```

## 3. 闭环动作

### 3.1 5 debt closure 补 evidence (走 omo governance ingress-debt broker)

- `DEBT-LEGACY-DIRECT-OMO-IO-BACKLOG` — cockpit/ecos/runtime/scripts 直写迁移至 broker
- `DEBT-CARDS-FRONTMATTER-PARSE` — yaml.safe_load 已正确处理冒号场景
- `DEBT-OMC-GBRAIN-PERSISTENCE` — omo_event + omo_trail 双 consumer 同步
- `DEBT-OMC-METAOS-OMO-PLANE` — metaos admission gateway 收口
- `DEBT-SWARM-ENGINE-20260614104223` — aetherforge packages/swarm 替代

### 3.2 omo ruff 2 errors 修复

- `omo_worker_promotion.py:63` — F401 `_append_unique` 未用 import (auto-fix)
- `omo_worker_promotion.py:430` — F841 `task` 未用变量 (manual fix)

### 3.3 mof-version timestamp 解析修复

- `scripts/omo/x2_freshness_audit.py` — naive vs aware datetime 兼容

### 3.4 重跑结果

```
X2-FRESH-DEBT-EVIDENCE-INTEGRITY: OK (0/37 stale)
X2-FRESH-CROSS-PROJECT-LINT: OK (0/8 stale)
X2-FRESH-MOF-VERSION-BUMP: OK (0/13 stale)
```

**3/3 OK**. governance 100 A+ 稳定.

## 4. Cron 调度

新增 `.omo/cron/x2-freshness-crontab`:
- 每日 8:00 — 完整 audit (归档)
- 每周一 9:00 — 跨项目 lint 巡检
- 每月 1/15 11:00 — debt evidence 巡检
- 每月 1 号 12:00 — mof-version 巡检

安装: `cat .omo/cron/x2-freshness-crontab | crontab -`

## 5. 关键 SSOT 引用

| 层级 | 路径 | 角色 |
|------|------|------|
| Runner | `scripts/omo/x2_freshness_audit.py` | 3 检查器 + cron wrapper |
| Crontab | `.omo/cron/x2-freshness-crontab` | 4 个调度规则 |
| Output | `.omo/_delivery/freshness-audit/YYYY-MM-DD.json` | 审计留痕 |
| Rule SSOT | `.omo/_truth/x2-freshness-rules.yaml` | 3 P43 衍生规则 |
| L0 约束 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml:CR-DEBT-CLOSURE-EVIDENCE-01` | 强约束 |
| X1 策略 | `.omo/_truth/x1-governance-policies.yaml:X1-DEBT-EVIDENCE-CLOSURE-20260620` | policy 强制 |

## 6. 闭环模式可复用性

X2 巡检 runner 是 P43 closed-loop 模式的 **runtime 触发器**:
- 文档声明 (R6) → runner 实施 (R7) → 真信号捕获 (5 debt + 2 lint + 1 timestamp bug)
- omo broker 闭环 (5 debt upsert) → omo governance 验证 → mof-version record
- 全程 0 越权, 全 broker + audit + history

**下一步**: P44 启动时, 可基于本 runner 添加:
- `X2-FRESH-X1-POLICY-NEXT-REVIEW` (15 天)
- `X2-FRESH-X4-CONSISTENCY-CHECK` (30 天)
- `X2-FRESH-DEBT-HEALTH-DRIFT` (7 天)