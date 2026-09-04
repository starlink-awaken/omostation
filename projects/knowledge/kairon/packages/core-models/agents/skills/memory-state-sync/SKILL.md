---
title: SKILL
type: doc
---

# Skill: Memory State Sync

## When To Use

Use when a task creates or updates shared state, memory candidates, events,
decisions, reflections, or handoffs.

## Read First

1. `docs/20-operating-model/shared-coordination-space.zh-CN.md`
2. `coordination/state/conductor-state.md`
3. `coordination/timeline/events.jsonl`

## Classification

| Type | Destination |
|---|---|
| State | `coordination/state/` |
| Event | `coordination/timeline/events.jsonl` |
| Decision | `coordination/decisions/` |
| Reflection | `coordination/reflections/` |
| Handoff | `coordination/handoffs/` |
| Durable knowledge | `docs/` after review |

## Steps

1. Classify the content.
2. Write it to the correct destination.
3. Avoid mixing temporary state with canonical docs.
4. Add evidence or source path.
5. Update timeline for significant changes.

## Forbidden

- Do not rewrite timeline history.
- Do not promote reflection into policy without review.
- Do not store secrets in coordination files.

## Validation

Sync is valid when a future agent can distinguish temporary state, audit event, decision, and durable knowledge.

