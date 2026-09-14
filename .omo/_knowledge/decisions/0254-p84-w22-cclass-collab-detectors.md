---
id: ADR-0254
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-07-28
related:
  - 0253-p84-collab-mode-routing-after-k4.md
  - .omo/_knowledge/audits/2026-07-28-p84-w2-27fail-retry-triage.md
supersedes: []
amends: []
type: ssot
---

# ADR-0254: P84 W2.2 C/S 类协作检测器落地

## Context

能力基线 27 失败三分类 (K2): **C 类 15**（double_claim / partial_failure / starvation）
+ **S 类 12**（orphan / unauthorized / audit_reject）。此前 runner 未实现对应检测。

## Decision

在 `bin/collab/scenario_lib.py` 实现:

| 类 | 事件 | 机制 |
|----|------|------|
| C | `double_claim_detected` | 双角色分歧写同 key |
| C | `partial_failure_handled` | 成功+失败 或 冲突+双认领 → 降级 |
| C | `starvation_resolved` | ≥2 写者冲突 → 轮询授予 |
| S | `orphan_detected` | 启动扫描 value 在无 writer |
| S | `unauthorized_detected` | role ∉ setup.roles 拒写 |
| S | `audit_reject_handled` | inject `audit_reject` |

对抗集进化: 修 C/S 后新增 **ADV13/15/17**（collusion / priority_inversion / cascade）保持 ≥3 失败。

## Status

**ACCEPTED**（2026-07-28）。入回归: `tests/test_collab_scenario_runner.py::test_cclass_detectors_pass`.
