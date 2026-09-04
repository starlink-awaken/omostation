---
schema_version: specification/v1
spec_version: 1.0.0
title: Documents terminal rollback receipt guard
bet_id: BET-Y1Q3-T10-65
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-08-29
last_updated: 2026-08-29
type: ssot
last_updated: 2026-09-03
---

# Documents terminal rollback receipt guard

## Intent

Make the Documents content-plane migration checker fail closed when a family
claims `verified` or `retired` but its rollback receipt cannot be resolved.
This protects the physical-purification boundary from a false terminal state.

## Contract

- A terminal family must retain all existing evidence fields.
- Its `rollback_ref` must resolve to a regular, non-symlink file from the
  current workspace or from an explicitly supplied test registry root.
- Relative repository references are resolved against the repository root;
  absolute references are checked as given.
- Pending, in-progress, and blocked families remain valid without a terminal
  receipt.
- The checker remains read-only and does not inspect, move, delete, or restore
  Documents content.

## Acceptance

- A missing terminal rollback receipt produces a deterministic error naming the
  family and reference.
- A real receipt passes, including the existing registry sample suite.
- The current main registry remains valid because root-oneoff is pending there.
- The live observation that the old root-oneoff receipt is missing is recorded
  as an evidence gap; no physical completion is claimed.
