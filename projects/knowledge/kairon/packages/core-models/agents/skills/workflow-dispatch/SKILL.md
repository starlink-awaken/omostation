---
title: SKILL
type: doc
---

# Skill: Workflow Dispatch

## When To Use

Use when Conductor needs to assign work to one or more agents.

## Read First

1. `coordination/state/conductor-state.md`
2. `agents/registry/team.md`
3. `adapters/cli/registry.yaml`
4. active work packet

## Steps

1. Confirm objective and acceptance criteria.
2. Split work into disjoint tasks.
3. Select agent by role and risk.
4. Define mode: read-only or scoped-write.
5. Define allowed tools and forbidden actions.
6. Add dispatch entry.
7. Append timeline event.
8. Collect artifact path.

## Outputs

- Dispatch entry in `coordination/dispatch/active-dispatch.md`.
- Optional run record in `coordination/runs/`.
- Timeline event.

## Forbidden

- Do not assign overlapping write scopes.
- Do not give Copilot architecture decision ownership.
- Do not dispatch high-risk work without approval.

## Validation

Dispatch is valid when the task has owner, mode, risk level, output path, and completion criteria.

