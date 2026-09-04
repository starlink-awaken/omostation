---
type: ephemeral
created: 2026-09-03
---

# B2: Dormant Tool Evaluation — bin/ssot/ 94 tools audit

> 2026-08-07 | Path B (减法收敛) | Tool: `make tool-audit`

## Summary

- **Total**: 94 tools
- **Active**: 71 (referenced in Makefile/CI/scripts)
- **Dormant**: 23 → after wiring new tools: **19 remaining**

## Newly Wired (fixed this session)

| Tool | Fix | Status |
|------|-----|--------|
| scene-feedback-collector | `make scene-feedback` | ✅ active |
| scene-outcome-recorder | `make scene-outcome` | ✅ active |
| signal-poller | `make signal-poll` | ✅ active |

## Remaining Dormant (19 tools, evaluation)

### Keep — On-Demand Utilities (9 tools)
| Tool | Lines | Justification |
|------|-------|---------------|
| scene-card-review | 230 | Scene card review workflow, useful on-demand |
| mesh-stale-analyze | — | Mesh analysis, useful for debugging |
| n9-iris-coverage-scan | — | Iris coverage reporting, useful for audits |
| gen-ci-surfaces-triggers | — | CI trigger generator, useful for maintenance |
| gen-scene-card-lineage | — | Lineage graph generator, useful for docs |
| doc-claim-lint | — | Doc claim validation, useful for reviews |
| graphify-local-extract | — | Knowledge graph extraction, useful for research |
| task-archive | — | Task archival utility, useful for cleanup |
| verify-spaces | — | Space verification, useful for audits |

### Debt Candidates — Evaluate for Y1 Removal (10 tools)
| Tool | Lines | Risk | Action |
|------|-------|------|--------|
| capability-zombie-tasks | — | Low | Evaluate: if no recent use, mark for removal |
| check-alert-coverage | — | Low | Evaluate: superseded by HealthMonitorAgent? |
| check-dead-path-refs | — | Low | Evaluate: superseded by doc-link-check? |
| check-submodule-hygiene | — | Low | Evaluate: superseded by gac-local-gate? |
| cross-submodule-check | — | Med | Evaluate: may duplicate cross-submodule-events |
| cross-submodule-events | — | Med | Evaluate: may duplicate cross-submodule-check |
| gbrain-todo-scan | — | Low | Evaluate: gbrain specific, may be stale |
| git-health-hook | — | Low | Evaluate: superseded by gac checks? |
| management-categorize | — | Med | Evaluate: old migration tool, may be done |
| management-migrate | — | Med | Evaluate: old migration tool, may be done |
| sync-mcptool-impl | — | Low | Evaluate: may be superseded by sync-help-docs |

## Y1 Alignment

三年规划 Y1 判据: "零调用脚本" 清零。

本审计标记了 19 dormant tools, 其中:
- 9 个是 on-demand utilities (保留, 不算冗余)
- 10 个是 debt candidates (需 Y1Q2 前逐个评估)

**不是所有 dormant 都是冗余** — on-demand 工具不进 CI 但有使用价值。真正的冗余是 debt candidates 中被 superseded 的工具。
