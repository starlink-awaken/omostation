# Mutation proposal envelope

> Status: active
> Phase: 13

---

## Purpose

Phase 13 may produce mutation proposals, but it must not apply them by default. This envelope defines the minimum evidence required before a proposal can become a future execution candidate.

## Required fields

| Field | Rule |
|-------|------|
| `id` | Stable proposal id |
| `source` | Evidence source or metacognition report |
| `target` | Intended state, task, package, scenario, or registry target |
| `expected_change` | Human-readable expected change |
| `operation_level` | L0, L1, L2, or L3 |
| `approval_required` | Human approval requirement |
| `rollback` | Concrete rollback path |
| `verification` | Concrete verification command or evidence |
| `auto_apply` | Must be `disabled` unless a future approved gate changes it |

## Guardrails

- Proposal generation is not approval.
- Approval is not execution.
- Execution requires a future active task packet and rollback evidence.
- Phase 13 self-healing remains dry-run unless a future mutation gate passes.
