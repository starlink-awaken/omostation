---
title: SKILL
type: doc
---

# Skill: Workflow Closeout

## When To Use

Use before ending a substantial task, after an agent run, or when a work packet
reaches review/done state.

## Read First

1. active work packet
2. `coordination/dispatch/active-dispatch.md`
3. `coordination/timeline/events.jsonl`
4. produced artifacts

## Steps

1. Confirm outputs exist.
2. Run validation.
3. Update work packet validation evidence.
4. Update dispatch status.
5. Append timeline event.
6. Record decision or reflection if needed.
7. Write or update handoff.
8. Produce a structured project status report for the user.

## Outputs

- Validation evidence.
- Timeline event.
- Updated handoff.
- Structured project status report for the user.

## User Report Format

Every substantial task closeout must include a concise project-level report,
not only a list of completed edits.

Use this structure:

```text
项目状态:
- Current Phase / Wave / Sprint
- Readiness level
- Current SSOT

本次完成:
- Work packet / scope
- Key artifacts

对整体项目的影响:
- Product / architecture / governance / agent collaboration impact

校验结果:
- Commands/checks passed

风险与缺口:
- Remaining risks
- Open gaps

下一步:
- Recommended next work packet or wave action
```

## Forbidden

- Do not mark a packet done without validation.
- Do not silently ignore failed validation.
- Do not bury unresolved risks in the final response.
- Do not only say what task was completed; always report the current overall
  project state.

## Validation

Closeout is valid when another agent can continue from the recorded state.
