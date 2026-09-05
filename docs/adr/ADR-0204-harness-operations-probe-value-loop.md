---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-04
last_updated: 2026-09-04
type: ssot
---

# ADR-0204: Harness 运营 (Probe + 价值循环)

## Status

Accepted (CR-HARNESS-OPERATIONS, governance-rule requirement, 2026-09-04)

## Context

Harness 运营包含两个子系统：Probe（探针标准化）和 Value Loop（价值循环 DAG）。
两条独立规则 (CR-HARNESS-PROBE-STANDARDIZATION, CR-HARNESS-VALUE-LOOP)
各自检查不同方面，需要统一为运营完整性检查。

## Decision

1. **7 类 Event 声明**：harness probes 必须声明全部 7 类 Event 类型。
2. **统一 bus**：所有 probe 通过统一事件总线通信。
3. **5 阶段 DAG**：value_loop 必须声明 5 阶段 DAG（感知→分类→执行→记录→反馈）。
4. **bus + store**：价值循环必须配置 bus 接入和持久化 store。
5. **统一检查入口**：合并为 CR-HARNESS-OPERATIONS。

## Consequences

- Probe 和 Value Loop 的配置变更受统一约束。
- 运营完整性可通过单一规则审计。
- 缺少任何子系统配置会阻塞 gate。

## References

- Rule: CR-HARNESS-OPERATIONS
- Merged from: CR-HARNESS-PROBE-STANDARDIZATION, CR-HARNESS-VALUE-LOOP
- Target: `.omo/_truth/registry/harness-policy.yaml`
