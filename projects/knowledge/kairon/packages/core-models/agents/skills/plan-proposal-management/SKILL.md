---
title: SKILL
type: doc
---

# Skill: Plan Proposal Management

## When To Use

Use when a task involves roadmap, phase, wave, sprint, proposal, option
analysis, ADR, or plan-to-task conversion.

## Read First

1. `docs/20-operating-model/plan-proposal-management.zh-CN.md`.
2. `docs/20-operating-model/execution-taxonomy.zh-CN.md`.
3. Current roadmap or active plan.
4. Active work packet if execution is requested.

## Steps

1. Classify the object: roadmap, phase plan, wave plan, sprint plan, proposal,
   option analysis, ADR, work packet, or run.
2. Search for existing related plans.
3. Create or update the correct object.
4. Link upstream context and downstream work packets.
5. Mark status explicitly.
6. Record decision or timeline event.

## Outputs

- Plan/proposal/ADR/work packet update.
- Links between plan and execution.
- Status and next action.

## Forbidden

- Do not put draft proposals directly into ADR.
- Do not create work packets from rejected proposals.
- Do not let roadmap carry low-level tasks.

## Validation

Plan management is valid when every accepted plan has explicit downstream work
packets or a reason for deferral.

