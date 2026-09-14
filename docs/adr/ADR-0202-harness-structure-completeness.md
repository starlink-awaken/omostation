---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-04
last_updated: 2026-09-04
type: ssot
---

# ADR-0202: Harness 结构完整性 (章节 + 维度 + 实现率)

## Status

Accepted (CR-HARNESS-STRUCTURE, governance-rule requirement, 2026-09-04)

## Context

Phase 8 引入 Harness 系统后，harness-policy.yaml 成为运营契约的 single source of truth。
三条独立规则 (CR-HARNESS-SECTION-COMPLETENESS, CR-HARNESS-DIMENSION-COVERAGE,
CR-HARNESS-IMPL-RATE) 各自检查不同方面，需要统一为结构完整性检查。

## Decision

1. **12 必现章节**：harness-policy.yaml 必须包含全部 12 个规范章节。
2. **12 维度全量挂载**：每个维度必须有对应的检查项定义。
3. **entry 指向脚本存在且调用 agent-workflow**：所有 executor entry 必须指向实际存在的脚本。
4. **统一检查入口**：合并三条规则为 CR-HARNESS-STRUCTURE 单一检查。

## Consequences

- harness-policy.yaml 结构变更需同时满足三方面要求。
- 检查从三条减为一条，降低维护成本。
- 结构不完整会阻塞 CI gate。

## References

- Rule: CR-HARNESS-STRUCTURE
- Merged from: CR-HARNESS-SECTION-COMPLETENESS, CR-HARNESS-DIMENSION-COVERAGE, CR-HARNESS-IMPL-RATE
- Target: `.omo/_truth/registry/harness-policy.yaml`
