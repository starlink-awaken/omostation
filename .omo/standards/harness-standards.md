---
type: ssot
owner: governance-team
last-reviewed: 2026-09-05
---

# Harness 标准文档

## 1. 概述

Harness 是唯一 S 槽位收束点，负责治理全链路的执行。

SSOT: `.omo/_truth/registry/harness-policy.yaml`

## 2. 8 阶段 DAG

| 阶段 | 输入 | 输出 | 强制 |
|------|------|------|------|
| admission | BET ID | 准入结果 | ✅ |
| spec | BET ID | Spec 校验 | ✅ |
| grill | BET ID | 5Q 检查 | L2 强制 |
| dispatch | BET ID + Profile | Run ID | ✅ |
| execute | Run ID | 执行结果 | ✅ |
| verify | Run ID | 校验结果 | ✅ |
| audit | BET ID | 审计报告 | L2 强制 |
| accept | Run ID | 验收结果 | ✅ |

## 3. 7 探针定义

| 探针 | 命令 | 阈值 | Event Type |
|------|------|------|------------|
| arch_upgrade | architecture-check.py | drift>0 | harness:arch:upgrade |
| feature:add | bet-ledger.py status | new pitch | harness:feature:add |
| bug_fix | gac-validate.py --gate | blocking_fail>0 | harness:bug:fix |
| experience | ls PANORAMA.md | score<90 | harness:experience:optimize |
| doc_governance | doc-ssot-lint.py --json | stale>14d | harness:doc:governance |
| toolchain | tool-registry-audit.py | drift | harness:toolchain:update |
| business | check-capability-ownership.py | value_gap | harness:business:process |

## 4. 强制约束

### Hook 层 (6 个 exit 1 拦截点)
1. hygiene-check (advisory)
2. gac-local-gate (blocking)
3. ssot-guardian (blocking)
4. audit-engine (blocking)
5. submodule-guard (blocking)
6. mass-deletion-gate (blocking)
7. conflict-marker-check (blocking)

### GaC 规则层 (32 个强制规则)
- CR-HARNESS-STRUCTURE (X4)
- CR-HARNESS-MOF-INTEGRATION (X4)
- CR-HARNESS-OPERATIONS (X1)
- CR-HARNESS-GOVERNANCE (X1)

### Harness 策略层 (19 个强制约束)
- require_worktree_clean: true
- require_bet_claimable: true
- deny_concurrent_claim: same BET && same track
- require_grill: appetite>=1d || risk_level>=L2
- write_surfaces: strict (越权写直接 halt)
- halt_on_overrun: true
- loop_break: same_error x2 → halt + switch strategy

## 5. 验收级别

| 级别 | 风险 | 要求 |
|------|------|------|
| L0_self | L0 | lint + gac-validate |
| L1_tech | L1 | lint + gac-validate + test + evidence |
| L2_business | L2 | lint + gac-validate + test + evidence + attestation |

## 6. 参考文档

- 策略 SSOT: `.omo/_truth/registry/harness-policy.yaml`
- 感知注册: `.omo/_truth/registry/architecture-perception-registry.yaml`
- 合规预算: `.omo/standards/anti-corrosion-budget.yaml`
- 维度系统: `.omo/standards/dimension-system.yaml`
- Agent 约束: `.omo/standards/mof-agent-constraints.yaml`
- GaC 规则: `.omo/_truth/registry/governance-checks.yaml`
