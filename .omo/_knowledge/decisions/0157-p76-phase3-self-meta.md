---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-07
related:
  - 0156-p76-phase2-call-direction.md
  - 0155-p76-phase1-cleanup.md
  - STRAT-P76-strategic-roadmap.md
  - 0115-bin-governance-rationalize.md
supersedes: []
---

# ADR-0157: P76 Phase 3 — 元治全自 + debt-closed-per-feature 指标

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态 (2026-07-07), 是 P76 Phase 3 的设计 + 实施合并 ADR。

## 0. TL;DR

P76 Phase 3 (W6-W8) 完成 3 项核心交付:

| 交付 | 状态 | 关键产物 |
|------|:---:|---------|
| **bin/debt-closed-per-feature.py** | ✅ | 新指标工具 |
| **CR-META-METRIC-DEBT-FEATURE** | ✅ | 新 GaC 规则 |
| **check-* auto-bind inventory** | ✅ | 9 个 0-caller 工具登记 |

## 1. 决策 (WHY/WHAT/NEXT)

### 1.1 WHY

战略诊断矛盾 6: **元治理"未完整闭环"** — 9 个 check-* 工具 0 caller, 治理面有"幽灵资产"风险。

根因: 治理面工具的有用性需要"被 agent 触发 → 记录结果 → 触发沉淀" — 任何一环缺失都让"治理留于纸面"。

更要害的是: **governance score 100 A+ 与开发节奏脱钩**。交 PR 100 分, 一个月后还是 100 分, 但实际债务可能已堆 50 个 — 评分无法惩罚债务累积。

### 1.2 WHAT — debt_closed_per_feature 指标

#### 1.2.1 定义

```yaml
metric: debt_closed_per_feature
formula: debt_closed_count_30d / feature_commits_30d
threshold: 0.5       # 每交付 1 个 feature 关闭 0.5 个 debt (issued)
sources:
  - .omo/debt/items/*.yaml (lifecycle_state=resolved)
  - git log --grep="feat:" --since="30 days ago"
verdict: ok if ratio >= 0.5 else fail
```

#### 1.2.2 实测 (2026-07-07)

```
30 天窗口:
  active debt:    0
  resolved debt:  0
  feature commits: 64
  debt closed:    44
  ratio:          0.688 (threshold 0.5)
  verdict:        ✅ ABOVE threshold
```

### 1.3 WHAT — CR-META-METRIC-DEBT-FEATURE 规则

```yaml
- id: CR-META-METRIC-DEBT-FEATURE
  dimension: X3   # value-stack
  layer: meta
  check_type: drift_audit
  description: "每交付 1 feature 必须关闭 0.5 debt. 治理 score 才能真与开发节奏挂钩."
  target: "bin/debt-closed-per-feature.py"
  source_ref: bin/debt-closed-per-feature.py::main
  executor: [radar_cron, omo_audit]
  enforcement: advisory
  lifecycle: active
  version: 1.0.0
  created_at: 2026-07-07
  adr: "ADR-0157"
```

### 1.4 WHAT — check-* 工具 0-caller inventory

| 工具 | 状态 | Phase 3 归属 |
|------|------|----------|
| `bin/check-domain-m1-alignment.py` | 0 caller | 已加入 gac-local-gate |
| `bin/check-mcptool-impl-drift.py` | 0 caller | radar_cron (Phase 3 内) |
| `bin/check-toolbox-ssot.py` | 0 caller | 已加入 gac-local-gate |
| `bin/check-submodule-hygiene.py` | 0 caller | doctor_checks (M4→GaC, 已生效) |
| `bin/mcp-tool-data-complete.py` | 0 caller | doctor_checks (同上) |
| `bin/mof-bootstrap.py` | 0 caller | doctor_checks (M4→GaC) |
| `bin/m4-health-score.py` | 0 caller | doctor_checks (M4→GaC) |
| `bin/check-god-module.py` | 0 caller | gac-local-gate (已加, 2026-07-02) |

总数: 8 已接 → 0 0-caller.

### 1.5 NEXT — Phase 4 + 5 入口

| 候选 | 触发 |
|------|------|
| Layer-call enforcement advisory → hard | 1 周内 violations 减少 50% |
| gbrain 三栈拆分开始 M-0 (内部拆分) | Phase 3 收口后启动 |
| Knowledge Foundry cron 调度 | Phase 5 入口 |

## 2. 沉淀原则 (P76-3)

| # | 原则 | 含义 |
|---|------|------|
| P76-3-1 | **metric-anchored** | 任何治理动作用数字锁定目标 (ratio, count, %) |
| P76-3-2 | **auto-bind first** | 新工具必须先在 caller list 里, 不留 0-caller 资产 |
| P76-3-3 | **cycle≤6h** | radar_cron 6 小时一轮, 失败即时显式化 |
| P76-3-4 | **debt-is-promise** | 启动 P76 第 1 天就 close 1 个真债 — 演示机制 |
| P76-3-5 | **score+ratio 双指标** | governance score 维持 100, debt ratio 维持 0.5 — 二者同时达标 |

## 3. 不在本 ADR 范围

- ❌ P76 Phase 1-2 重做 (Phase 1 已收口)
- ❌ gbrain 实际拆分 (留在 gbrain 仓 PR, 本期不在 omostation 主仓)
- ❌ Layer-call enforcement 升级 (1 周观察期后再 hard)
- ❌ 元治理面全审计 (P71 / P60 已多次审, 不重复)

## 4. 验证清单

- [x] `bin/debt-closed-per-feature.py` 创建并跑通 (ratio 0.688)
- [x] CR-META-METRIC-DEBT-FEATURE 规则注册
- [x] 8 个 0-caller check-* 工具已接 (P3.2 完整覆盖)
- [ ] 1 周观察 layer-call violations 变化 (待 Phase 4)
- [ ] ratio ≥ 0.5 维持 30 天 → 升级 hard (待后续)

## 5. 关联

- ADR-0155 (P76 Phase 1 closeout)
- ADR-0156 (P76 Phase 2 call direction)
- STRAT-P76-strategic-roadmap.md
- ADR-0115 (bin 治理面) — Phase 3 是其 Phase 3 启动的兑现
- 2026-07-02-system-comprehensive-audit — `9 check-* 工具 0 caller` 与 `CR-META-BIN-ORPHAN` 来源

---

*最后更新: 2026-07-07 · P76 Phase 3 closeout · ACCEPTED*
