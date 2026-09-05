---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-04
last_updated: 2026-09-04
type: ssot
---

# ADR-0205: Harness 治理 (已知债 + OMO 同步 + 防腐)

## Status

Accepted (CR-HARNESS-GOVERNANCE, governance-rule requirement, 2026-09-04)

## Context

Harness 治理涉及三个子领域：已知债管理、OMO 状态同步、防腐预算控制。
三条独立规则 (CR-HARNESS-KNOWN-DEBT, CR-HARNESS-OMO-SYNC, CR-HARNESS-ANTI-CORROSION)
各自检查不同方面，需要统一为治理完整性检查。

## Decision

1. **known_debt.growth_policy=shrink_only**：已知债只允许减少，不允许新增。
2. **escape 收口**：所有 escape hatch 必须有明确的收口条件和时间线。
3. **Harness 状态同步 OMO system.yaml**：Harness 运行状态必须同步到 OMO state plane。
4. **脚本配额遵守 anti-corrosion-budget**：新增脚本必须在防腐预算内。
5. **统一检查入口**：合并为 CR-HARNESS-GOVERNANCE。

## Consequences

- 已知债增长会被 gate 阻断。
- OMO 同步延迟会触发告警。
- 防腐预算为硬约束，超出需人工审批。

## References

- Rule: CR-HARNESS-GOVERNANCE
- Merged from: CR-HARNESS-KNOWN-DEBT, CR-HARNESS-OMO-SYNC, CR-HARNESS-ANTI-CORROSION
- Target: `.omo/_truth/registry/harness-policy.yaml`
