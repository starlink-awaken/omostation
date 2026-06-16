# Autopilot Spec: P44 W6 — 修 DEBT-OPC-P4-BUDGET (最后 1 真债务)

> **Date**: 2026-06-16
> **Stage**: Autopilot Phase 0 — Expansion

---

## 1. Problem

DEBT-OPC-P4-BUDGET-STRESS-TEST-BUDGET-042303: LLM Gateway blocked task `stress-test-budget-042303` because estimated cost 0.001183 USD exceeded budget 0.000001 USD.

**根因**: `_register_budget_debt` 函数**无去重**, 同一 task_id 每次 budget 失败都登记一次 debt(债务爆炸)。

**0.000001 实际是 test mock** (`tests/test_budget_enforcement.py:25`), 真实 deepseek/deepseek-chat cost 是 0.00027 USD/1k tokens。

---

## 2. Goals

### 🎯 Goal 1: 修 budget policy + 关闭最后 1 债务
- **验收**: `_register_budget_debt` 加去重 (同一 task_id 只登记 1 次)
- **关闭 DEBT-OPC-P4-BUDGET-STRESS-TEST-BUDGET-042303** (status=closed + evidence)
- **L0 验证**: llm-gateway tests 全过
- **X1-X4**: 全维度

---

## 3. Non-Goals

- 改 c2g / cockpit / omo
- 改 llm-gateway 其它模块 (除 budget.py 加去重)
- 改 debt YAML schema

---

## 4. Architecture (修)

```
[budget.py:check_budget_limit] (改)
  ├── _register_budget_debt (加 _reported_debts: set[str] 去重)
  │     └── 同 task_id 第二次失败时 return "" (不重复登记)
  └── 其他逻辑不动

[.omo/debt/items/DEBT-OPC-P4-BUDGET-STRESS-TEST-BUDGET-042303.yaml] (close)
  ├── status: open → closed
  ├── closed_at: 2026-06-16T06:00:00Z
  └── evidence: "budget.py _register_budget_debt 加去重; 0.000001 USD 是 test mock 不会触发真 production debt; test_budget_enforcement.py:25"
```

---

## 5. Acceptance

| Goal | 验收 |
|------|------|
| 1 | budget.py 加 _reported_debts: set + 去重逻辑 |
| 1 | llm-gateway tests 全过 (test_budget_enforcement.py 4 tests + 其它) |
| 1 | DEBT-OPC-P4-BUDGET-STRESS-TEST-BUDGET-042303.yaml 改 status=closed + closed_at + evidence |
| X1 | commit 含 evidence (修 + close) |
| X2 | budget.py mtime 新 |
| X3 | llm-gateway tests 0 violation |
| X4 | 0 已知真债务 (P44 全 6 phase 收口) |

---

## 6. Risks

| 风险 | 概率 | 影响 | 防御 |
|------|:---:|:---:|------|
| 去重 set 在多进程冲突 | 低 | 中 | 用 set() 单进程, 真实多进程应走持久化(本次范围外) |
| tests 失败 (改 budget.py) | 低 | 高 | 跑全部 llm-gateway tests, 0 violation 才 commit |
| DEBT close 漏 evidence | 低 | 中 | 模板强制 4 字段 (status/closed_at/evidence/reason) |

---

*Spec: 老王 · 2026-06-16 · P44 W6 · 1 目标 · 修最后 1 债务*
