---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-04
last_updated: 2026-09-04
type: ssot
---

# ADR-0203: Harness MOF 集成 (S 槽位 + MOF 约束)

## Status

Accepted (CR-HARNESS-MOF-INTEGRATION, governance-rule requirement, 2026-09-04)

## Context

Harness 作为 DFSQ 架构的 S 槽位（调度器），必须遵守 MOF 约束体系。
两条独立规则 (CR-HARNESS-SFOP-SLOT, CR-HARNESS-MOF-CONSTRAINT) 分别检查
槽位声明和 MOF 文件约束，需要合并为统一的 MOF 集成检查。

## Decision

1. **sfop_slot 必须为 S**：Harness 的 SFOP 槽位声明必须为 `S`，controller 为 `COMP-WS-omo`。
2. **编辑 MOF 文件前必须影响分析**：修改 MOF 约束文件前需运行 `ecos-constraint explain`。
3. **编辑后 schema 校验**：MOF 文件修改后必须通过 `arcnode validate --all`。
4. **统一检查入口**：合并为 CR-HARNESS-MOF-INTEGRATION。

## Consequences

- Harness 不能偏离 S 槽位角色。
- MOF 文件变更受双重保护（事前分析 + 事后校验）。
- 检查从两条减为一条。

## References

- Rule: CR-HARNESS-MOF-INTEGRATION
- Merged from: CR-HARNESS-SFOP-SLOT, CR-HARNESS-MOF-CONSTRAINT
- Target: `.omo/_truth/registry/harness-policy.yaml`
