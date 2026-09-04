---
title: SKILL
type: doc
---

# Skill: Governance Review

## When To Use

Use when work affects permissions, external tools, data boundaries, destructive
operations, credentials, Git publish actions, production APIs, or multi-agent
execution.

## Read First

1. `docs/30-governance/governance-control-plane.zh-CN.md`
2. `docs/20-operating-model/shared-coordination-space.zh-CN.md`
3. active work packet
4. relevant dispatch records

## Steps

1. Identify risk level.
2. Check allowed tools and forbidden actions.
3. Check write scope.
4. Check whether human approval is required.
5. Check audit and rollback records.
6. Record findings.

## Outputs

- Governance findings.
- Required approval if any.
- Risk mitigation.

## Forbidden

- Do not downgrade risk to avoid approval.
- Do not allow external project writes without explicit scope.
- Do not allow high-risk tool calls without an approval receipt.

## Validation

Review is valid when risk, permission, approval, audit, and rollback are explicitly addressed.

