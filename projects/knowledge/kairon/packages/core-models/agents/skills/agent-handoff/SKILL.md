---
title: SKILL
type: doc
---

# Skill: Agent Handoff

## When To Use

Use when one Agent finishes work and another Agent or the Conductor must
continue from it.

## Read First

1. Active work packet.
2. `docs/20-operating-model/agent-handoff-contract.zh-CN.md`.
3. Source artifact.
4. Current dispatch entry.

## Steps

1. Identify source agent and target agent.
2. Summarize completed scope.
3. Summarize remaining scope.
4. Link all artifacts.
5. List decisions needed.
6. List risks and validation evidence.
7. Recommend the next action.
8. Store handoff in `coordination/handoffs/` when non-trivial.

## Outputs

- Handoff note.
- Optional timeline event.
- Updated dispatch entry.

## Forbidden

- Do not hide unresolved risks.
- Do not expand write scope.
- Do not treat unreviewed output as canonical.

## Validation

Handoff is valid when a new Agent can continue without reading the whole chat
history.

