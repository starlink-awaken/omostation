---
title: SKILL
type: doc
---

# Skill: Conductor Hot Start

## When To Use

Use at the start of every non-trivial DigitalBrainOS task or when a new agent
session resumes ongoing work.

## Read First

1. `README.zh-CN.md`
2. `AGENTS.md`
3. `coordination/state/conductor-state.md`
4. `coordination/dispatch/active-dispatch.md`
5. active work packets under `work-packets/active/`

## Steps

1. Run or emulate `scripts/hot_start.sh`.
2. Identify current phase.
3. Identify active work packet.
4. Read recent timeline events.
5. Confirm guardrails.
6. State the next action before editing.

## Outputs

- Short context summary.
- Active task and write scope.
- Any blockers or missing authorization.

## Forbidden

- Do not modify external projects during hot start.
- Do not create new scope without a work packet.
- Do not treat stale state as canonical if it conflicts with current files.

## Validation

Hot start is valid when active state, active dispatch, recent events, and active work packets are visible.

